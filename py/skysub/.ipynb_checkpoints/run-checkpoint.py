import os, sys, time, subprocess
from copy import deepcopy
import bokeh.plotting as bk
import numpy as np
import fitsio
import desispec.io
from desispec.sky import subtract_sky
from desispec.fiberflat import apply_fiberflat
from desispec.calibfinder import findcalibfile
from desitarget.targetmask import desi_mask
from bokeh.layouts import row, column, gridplot
from bokeh.models import ColumnDataSource
from bokeh.embed import file_html
from bokeh.resources import Resources

def pick_sky_fibers(frame, fiberflat, nsky=100):
    '''
    Updates frame in-place with a new set of sky fibers
    
    The particular cuts here only work for early commissioning observations
    where we randomly point the telescope and hope that most fibers don't
    hit a star or galaxy.
    '''
    tmpframe = deepcopy(frame)
    apply_fiberflat(tmpframe, fiberflat)
    
    #- select fibers whose flux is between 1 and 90th percentile
    sumflux = np.sum(tmpframe.flux, axis=1)
    sumivar = np.sum(tmpframe.ivar, axis=1)
    fluxlo, fluxhi = np.percentile(sumflux, [5, 85])
    iisky = (fluxlo < sumflux) & (sumflux < fluxhi) & (sumivar>0) & (sumflux > 0)

    #- Pick a random subset for calling "SKY" fibers
    skysubset = np.random.choice(np.where(iisky)[0], size=nsky, replace=False)

    #- everything is a target unless told otherwise
    frame.fibermap['OBJTYPE'] = 'TGT'
    
    #- Flag the too-bright or too-faint as "BAD" so we know not to use them
    #- for sky subtraction studies
    frame.fibermap['OBJTYPE'][~iisky] = 'BAD'
    
    #- Flag the subset as "SKY"
    frame.fibermap['OBJTYPE'][skysubset] = 'SKY'
    
    
def get_new_frame(night, expid, camera, basedir, nsky, rep=0):
    '''For a given frame file, returns an updated frame file to the basedir with a certain number of sky fibers.
    Args:
        night: YYYYMMDD (float)
        expid: exposure id without padding zeros (float)
        camera: examples are b3, r4, z2, etc. (string)
        basedir: path to directory you want new frame to be written
        nsky: number of fibers flagged sky in new frame fibermap
    Options:
        rep: number of different frame files you want (with same number of sky fibers), default is 5
    Writes a new frame file with desispec.io.write_frame().'''
    
    framefile = desispec.io.findfile('frame', night, expid, camera=camera)
    print(framefile)
    header = fitsio.read_header(framefile)
    fiberflatfile = findcalibfile([header,], 'FIBERFLAT')
    frame = desispec.io.read_frame(framefile)
    fiberflat = desispec.io.read_fiberflat(fiberflatfile)
    print(fiberflatfile)
    pick_sky_fibers(frame, fiberflat, nsky=nsky)

    #- output updated frame to current directory
    newframefile = basedir+'/frame-{}-{:08d}-{}-{}.fits'.format(camera, expid, nsky, rep)
    desispec.io.write_frame(newframefile, frame)
    
def get_new_frame_set(night, expid, cameras, basedir, nsky_list, reps=None):
    '''For a given frame file, returns an updated set of frame files to the basedir, given a list of different numbers of sky fibers.
    Args:
        night: YYYYMMDD (float)
        expid: exposure id without padding zeros (float)
        cameras: list of cameras you want the files generated for, example ['r3', 'z3', 'b3'] (list or array)
        basedir: path to directory you want new frame files to be written
        nsky_list: list with different numbers of fibers you want frame files to be generated with.
    Options:
        rep: number of different frame files you want for each camera and nsky combination. Default is 5
    Writes new frame files with desispec.io.write_frame(), frames are named according to the convention frame-{camera}-{expid (padded to 8 digits)}-{number of fibers}-{rep}.fits'.'''

    if reps == None:
        reps = 5
        
    for cam in cameras:
        for N in range(reps):
            for n in nsky_list:
                get_new_frame(night, expid, cam, basedir, n, rep=N)
                
def run_compute_sky(night, expid, cameras, basedir, nsky_list, reps=None):
    '''Generates sky models for new frame files, using --no-extra-variance option, which doesn't inflate the output errors for sky subtraction systematics.
    Args:
        night: YYYYMMDD (float)
        expid: exposure id without padding zeros (float)
        cameras: list of cameras corresponding to frame files in given directory, example ['r3', 'z3', 'b3'] (list or array)
        basedir: where to look for frame files
        nsky_list: list with different numbers of fibers frame files were generated with.
    Options:
        rep: number of different frame files for each camera and nsky combination. Default is 5
    '''
    
    if reps == None:
        reps = 5
    
    for cam in cameras:
        framefile = desispec.io.findfile('frame', night, expid, camera=cam)
        header = fitsio.read_header(framefile)
        fiberflatfile = findcalibfile([header,], 'FIBERFLAT')
        for N in range(reps):
            for n in nsky_list:
                newframefile = basedir+'/frame-{}-{:08d}-{}-{}.fits'.format(cam, expid, n, N)
                skyfile = basedir+'/sky-{}-{:08d}-{}-{}.fits'.format(cam, expid, n, N)
                cmd = 'desi_compute_sky -i {} --fiberflat {} -o {} --no-extra-variance'.format(
                    newframefile, fiberflatfile, skyfile)
                print('RUNNING {}'.format(cmd))
                err = subprocess.call(cmd.split())
                if err:
                    print('FAILED')
                else:
                    print('OK')

def run_sky_subtraction(night, expid, cameras, basedir, nsky_list, reps=None):
    '''Runs sky subtraction with new sky models and frame files.
    Args:
        night: YYYYMMDD (float)
        expid: exposure id without padding zeros (float)
        cameras: list of cameras corresponding to frame and sky files in given directory, example ['r3', 'z3', 'b3'] (list or array)
        basedir: where to look for frame files
        nsky_list: list with different numbers of fibers frame files and sky files were generated with.
    Options:
        rep: number of different frame/sky files for each camera and nsky combination. Default is 5
    '''
    if reps == None:
        reps = 5
    
    for cam in cameras:
        framefile = desispec.io.findfile('frame', night, expid, camera=cam)
        header = fitsio.read_header(framefile)
        fiberflatfile = findcalibfile([header,], 'FIBERFLAT')
        fiberflat = desispec.io.read_fiberflat(fiberflatfile)
        for N in range(reps):
            for n in nsky_list:
                newframefile = basedir+'/frame-{}-{:08d}-{}-{}.fits'.format(cam, expid, n, N)
                skyfile = basedir+'/sky-{}-{:08d}-{}-{}.fits'.format(cam, expid, n, N)
                sframe = desispec.io.read_frame(newframefile)
                sky = desispec.io.read_sky(skyfile)
                apply_fiberflat(sframe, fiberflat)
                subtract_sky(sframe, sky)

                sframefile = basedir+'/sframe-{}-{:08d}-{}-{}.fits'.format(cam, expid, n, N)
                desispec.io.write_frame(sframefile, sframe)

def rms(x):
    return np.sqrt(np.sum(x**2)/len(x))

def get_rms_array(expid, cam, rep, basedir, nsky_list, wave_filter, title=None):
    '''For a given camera for a given exposure, calculates the rms '''
    basedir = os.path.expandvars(basedir)
    RMS = []
    for N in nsky_list:
        if os.path.isfile(basedir+'/sframe-{cam}-{expid:08d}-{n}-{m}.fits'.format(expid=expid, cam=cam, n=str(N), m=str(rep))):
            frame = desispec.io.read_frame(basedir+'/sframe-{cam}-{expid:08d}-{n}-{m}.fits'.format(expid=expid, cam=cam, n=str(N), m=str(rep)))
            isSky = frame.fibermap['OBJTYPE'] == 'SKY'
            rmss = []
            for i in np.where(frame.fibermap['OBJTYPE'] == 'TGT')[0]:
                r = rms(frame.flux[i][wave_filter])
                rmss.append(r)
            RMS.append(np.average(np.array(rmss)))
        else:
            continue
    return RMS

def write_rms_dict(night, expid, cam, basedir, nsky_list, wave_filter, reps=None):
    
    if reps == None:
        reps = 5
    
    data = dict()
    skyfile = desispec.io.findfile('sky', night, expid, camera=cam)
    sky = desispec.io.read_sky(skyfile)

    for N in nsky_list:
        M_dict = {}
        for M in range(reps):
            if os.path.isfile(basedir+'/sframe-{cam}-{expid:08d}-{n}-{m}.fits'.format(expid=expid, cam=cam, n=str(N), m=str(M))):
                frame = desispec.io.read_frame(basedir+'/sframe-{cam}-{expid:08d}-{n}-{m}.fits'.format(expid=expid, cam=cam, n=str(N), m=str(M)))
                rmss = []
                sums = []
                for i in np.where(frame.fibermap['OBJTYPE'] == 'TGT')[0]:
                    r = rms(frame.flux[i][wave_filter])
                    rmss.append(r)
                    y_sum = np.sum(frame.flux[i][wave_filter])
                    sums.append(y_sum)
                fiber_dict = dict({'fiber_RMS': rmss, 'integrated_flux': sums})
                M_dict[M] = fiber_dict      
            else:
                continue
        data[N] = M_dict
    return data
        
def write_dict_to_json(night, expid, cameras, basedir, jsondir, nsky_list, wave_filters, reps=None):
    
    import json
    
    if reps == None:
        reps = 5

    filename = jsondir + '/data-{}-{:08d}.json'.format(night, expid)
    data = dict()
    for cam in cameras:
        data[cam] = write_rms_dict(night, expid, cam, basedir, nsky_list, wave_filters[cam], reps=reps)
    
    with open(filename, 'w') as outfile:
        json.dump(data, outfile)
        
    print ('wrote {}'.format(filename))

def get_wave_filters(night, expid, cameras):
    wave_filters = dict()
    for cam in cameras:
        skyfile = desispec.io.findfile('sky', night, expid, camera=cam)
        sky = desispec.io.read_sky(skyfile)
        if cam == 'r3':
            wave_filters[cam] = (5500 < sky.wave) & (sky.wave < 8000)
        if cam == 'b3':
            wave_filters[cam] = (5000 < sky.wave) & (sky.wave < 6000)
        if cam == 'z3':
            wave_filters[cam] = (7500 < sky.wave) & (sky.wave < 9900)
    return wave_filters

def plot_rms_mean_scatter(file, cam, basedir, nsky_list, wave_filter, title=None, reps=None):

    import json
    colors = {'r3': 'red', 'b3': 'blue', 'z3': 'black'}
    scales = {'r3': {'min':50, 'max':250}, 'b3': {'min':50, 'max':200}, 'z3': {'min':50, 'max':250}}
    if reps == None:
        reps = 5
    
    #file = basedir + 'data-{}-{:08d}.json'.format(night, expid)
    
    with open(file) as json_file:
        data = json.load(json_file)
     
    cam_data = data[cam]
    
    rms_data = []
    nsky_data = []
    line_avg = []
    line_std = []
    for nsky in nsky_list:
        n_data = cam_data[str(nsky)]
        line = []
        for key in n_data.keys():
            fiber_data = np.array((n_data[key]['fiber_RMS']))
            rms_data.append(np.average(fiber_data))
            line.append(np.average(fiber_data))
            nsky_data.append(nsky)
        line_avg.append(np.average(line))
        line_std.append(np.std(line))
        
    source = ColumnDataSource(data = {
        'nsky_data' : nsky_data,
        'rms_data' : rms_data,
    })
    
    source1 = ColumnDataSource(data = {
        'nsky' : nsky_list,
        'line_std': line_std,
        'line_avg': line_avg,
    })
    
    if np.max(rms_data) >= scales[cam]['min']:
        y_range = scales[cam]['max']
    else:
        y_range = scales[cam]['min']
    
    fig = bk.figure(title='Model Quality vs. Number of Fibers', width=350, height=350, y_range=(0, y_range))
    fig.circle('nsky_data', 'rms_data', source=source, color=colors[cam], alpha=0.65, size=5, legend="per-realization")
    fig.line('nsky', 'line_avg', source=source1, color=colors[cam], alpha=1, legend='mean')
    fig.xaxis.axis_label = 'Number of Sky Fibers Used in Model'
    fig.yaxis.axis_label = 'Q for non-model fibers'
    #fig.legend
    
    y_range1 = max(2.5, np.max(line_std))
    fig1 = bk.figure(title='Standard deviation across realizations', width=350, height=350, y_range=(0, 1.05*y_range1))
    fig1.circle('nsky', 'line_std', source=source1, color=colors[cam], alpha=1)
    fig1.xaxis.axis_label = 'Number of Sky Fibers Used in Model'
    fig1.yaxis.axis_label = 'Standard deviation'
    
    return [fig, fig1]

def run_analysis(night, expid, cameras, basedir, nsky_list, reps=5):
    '''Generates all new files (frame, sky, and subtracted frame) for a given exposure on a given night, for a given set of cameras.
    Arguments:
        night: 
        expid:
        cameras:
        basedir:
        nsky_list:
    Options:
        reps:
    Writes all files to given base directory.'''
    
    get_new_frame_set(night, expid, cameras, basedir, nsky_list, reps=reps)
    run_compute_sky(night, expid, cameras, basedir, nsky_list, reps=reps)
    run_sky_subtraction(night, expid, cameras, basedir, nsky_list, reps=reps)
    
def plot_data(file, night, expid, cameras, basedir, nsky_list, wave_filters, reps=5):   
    '''Plots given file (must be json with correct data format)'''
    cam_figs = []
    cam_rms = []
    for cam in cameras:
        figs = plot_rms_mean_scatter(file, cam, basedir, nsky_list, wave_filters[cam], title='Night: {} Exp: {:08d} Cam: {}'.format(night, expid, cam), reps=reps)
        cam_figs.append(figs[0])
        cam_rms.append(figs[1])
    
    both_figs = []
    for i in range(len(cam_figs)):
        both_figs.append(row(cam_figs[i], cam_rms[i]))#cam_avgs[i], cam_rms[i]))
    return column(both_figs)
    
def full_analysis(night, expid, cameras, basedir, json_dir, nsky_list, reps=5):
    
    run_analysis(night, expid, cameras, basedir, nsky_list, reps=reps)
    
    wave_filters = get_wave_filters(night, expid, cameras)
    write_dict_to_json(night, expid, cameras, basedir, json_dir, nsky_list, wave_filters, reps=reps)
    file = basedir + '/data-{}-{:08d}.json'.format(night, expid)
    
    cam_fig = plot_data(file, cameras, basedir, nsky_list, wave_filters, reps=reps)
    return cam_fig
    
def plot_unsubtracted_sky(night, expid, cam, nsky, rep, basedir, wave_filter, title, height=200, width=200):
    
    frame = desispec.io.read_frame(basedir + '/frame-{cam}-{expid:08d}-{nsky}-{rep}.fits'.format(cam=cam, expid=expid, nsky=nsky, rep=rep))
    fig = bk.figure(width=width, height=height, title=title)
    for i in np.where(frame.fibermap['OBJTYPE'] == 'TGT')[0]:
        fig.line(frame.wave[wave_filter], frame.flux[i][wave_filter], alpha=0.5)
    return fig

def plot_subtracted_sky(night, expid, cam, nsky, rep, basedir, wave_filter, title, height=200, width=200):
    
    sframe = desispec.io.read_frame(basedir + '/sframe-{cam}-{expid:08d}-{nsky}-{rep}.fits'.format(cam=cam, expid=expid, nsky=nsky, rep=rep))
    fig = bk.figure(width=width, height=height, title=title)
    for i in np.where(sframe.fibermap['OBJTYPE'] == 'TGT')[0]:
        fig.line(sframe.wave[wave_filter], sframe.flux[i][wave_filter], alpha=0.5)
    return fig
