"""
skysub command line script
"""

import os, sys, time, glob
import argparse
import traceback
import subprocess
from . import run

os.environ['DESI_SPECTRO_REDUX'] = '/project/projectdirs/desi/spectro/redux'
os.environ['SPECPROD'] = 'daily'

def print_help():
    print("""USAGE: skysub <command> [options]

Supported commands are:
    full     Generate frame, sky, and sframe files and plot results 
    run      Generate frame, sky, and sframe files for different models
    json     Generate json file with subtraction quality data for given night, exposure
    plot     Given a pregenerated json file, generate plots
    skyplot  Given a set of files, plot unsubtracted vs. subtracted sky spectra
    
Run "skysub <command> --help" for detailed options about each command
""")
    
def main():
    if len(sys.argv) == 1 or sys.argv[1] in ('-h', '--help', '-help', 'help'):
        print_help()
        return 0

    command = sys.argv[1]
    if command == 'full':
        main_full()
    if command == 'run':
        main_run()
    elif command == 'json':
        main_json()
    elif command == 'plot':
        main_plot()
    elif command == 'skyplot':
        main_skyplot()
    else:
        print('ERROR: unrecognized command "{}"'.format(command))
        print_help()
        return 1
    
def main_full(options=None):
    parser = argparse.ArgumentParser(usage = "{prog} run [options]")
    parser.add_argument("-n", "--night", type=int,  help="night of corresponding exposure YEARMMDD")
    parser.add_argument("-e", "--expid", type=int,  help="exposure to analyze, expid without padding zeroes")
    parser.add_argument("-c", "--cameras", nargs='*', type=str, help="comma separated list of cameras, ex. --cameras r3 b3 z3")
    parser.add_argument("-bdir", "--basedir", type=str, help="directory to write output frame, sky, sframe files")
    parser.add_argument("odir", "--outdir", type=str, help="directory to write plots (HTML files) ")
    parser.add_argument("--nsky_list", nargs='*', type=int, default="1 2 5 10 20 30 40 50 60 70 80", help="list of numbers of sky fibers to use for different models. ex. --nsky_list 1 2 3 4")
    parser.add_argument("-r", "--reps", type=int, default=5, help="number of realizations for each model (default 5)")

    if options is None:
        options = sys.argv[2:]

    args = parser.parse_args(options)
    
    cam_fig = run.full_analysis(args.night, args.expid, args.cameras, args.basedir, args.basedir, args.nsky_list, reps=args.reps)
    bk.output_file(outdir + 'cam_plots-{}-{:08d}.html'.format(night, expid))
    bk.save(cam_fig)
    
def main_run(options=None):
    parser = argparse.ArgumentParser(usage = "{prog} run [options]")
    parser.add_argument("-n", "--night", type=int,  help="night of corresponding exposure YEARMMDD")
    parser.add_argument("-e", "--expid", type=int,  help="exposure to analyze, expid without padding zeroes")
    parser.add_argument("-c", "--cameras", nargs='*', type=str, help="comma separated list of cameras, ex. --cameras r3 b3 z3")
    parser.add_argument("-bdir", "--basedir", type=str, help="directory to write output files")
    parser.add_argument("--nsky_list", nargs='*', type=int, default="1 2 5 10 20 30 40 50 60 70 80", help="list of numbers of sky fibers to use for different models. ex. --nsky_list 1 2 3 4")
    parser.add_argument("-r", "--reps", type=int, default=5, help="number of realizations for each model (default 5)")

    if options is None:
        options = sys.argv[2:]

    args = parser.parse_args(options)
    
    run.run_analysis(args.night, args.expid, args.cameras, args.basedir, args.nsky_list, reps=args.reps)
    
def main_json(options=None):
    parser = argparse.ArgumentParser(usage = "{prog} run [options]")
    parser.add_argument("-n", "--night", type=int,  help="night of corresponding exposure YEARMMDD")
    parser.add_argument("-e", "--expid", type=int,  help="exposure to analyze, expid without padding zeroes")
    parser.add_argument("-c", "--cameras", nargs='*', type=str, help="comma separated list of cameras, ex. --cameras r3 b3 z3")
    parser.add_argument("--basedir", type=str, help="where to look for frame, sky, sframe files")
    parser.add_argument("--jsondir", type=str, help="directory to write output files")
    parser.add_argument("--nsky_list", nargs='*', type=int, default="1 2 5 10 20 30 40 50 60 70 80", help="list of numbers of sky fibers to use for different models. ex. --nsky_list 1 2 3 4")
    parser.add_argument("--reps", type=int, default=5, help="number of realizations for each model (default 5)")

    if options is None:
        options = sys.argv[2:]

    args = parser.parse_args(options)
    
    wave_filters = run.get_wave_filters(args.night, args.expid, args.cameras)
    
    run.write_dict_to_json(args.night, args.expid, args.cameras, args.basedir, args.jsondir, args.nsky_list, wave_filters, reps=args.reps)
    
def main_plot(options=None):
    parser = argparse.ArgumentParser(usage = "{prog} run [options]")
    parser.add_argument("-n", "--night", type=int,  help="night of corresponding exposure YEARMMDD")
    parser.add_argument("-e", "--expid", type=int,  help="exposure to analyze, expid without padding zeroes")
    parser.add_argument("-c", "--cameras", nargs='*', type=str, help="comma separated list of cameras, ex. --cameras r3 b3 z3")
    parser.add_argument("--jsondir", type=str, help="where to look for json file with data to be plotted")
    parser.add_argument("--outdir", type=str, help="where to write output plot HTML files")
    parser.add_argument("--nsky_list", nargs='*', type=int, default="1 2 5 10 20 30 40 50 60 70 80", help="list of numbers of sky fibers to use for different models. ex. --nsky_list 1 2 3 4")
    parser.add_argument("--reps", type=int, default=5, help="number of realizations for each model (default 5)")

    if options is None:
        options = sys.argv[2:]

    args = parser.parse_args(options)
    
    wave_filters = run.get_wave_filters(args.night, args.expid, args.cameras)
    
    cam_fig = run.plot_data(args.file, args.night, args.expid, args.cameras, args.jsondir, args.nsky_list, wave_filters, reps=args.reps)
    
    bk.output_file(args.outdir + "cam_plots-{}-{:08d}".format(args.night, args.expid))
    bk.save(cam_fig)
    
def main_skyplot(options=None):
    parser = argparse.ArgumentParser(usage = "{prog} run [options]")
    parser.add_argument("-n", "--night", type=int,  help="night of corresponding exposure YEARMMDD")
    parser.add_argument("-e", "--expid", type=int,  help="exposure to analyze, expid without padding zeroes")
    parser.add_argument("-c", "--cam", type=str, help="single camera to plot data for")
    parser.add_argument("--nsky", default=50, type=int, help='number of fibers used in model')
    parser.add_argument("--rep", default=0, type=int, help="realization to use (for help locating right file)")
    parser.add_argument("--basedir", type=str, help="where to look for frame, sky, sframe files")
    parser.add_argument("--outdir", type=str, help="where to output skyplot HTML files")
    parser.add_argument("--nsky_list", nargs='*', type=int, default="1 2 5 10 20 30 40 50 60 70 80", help="list of numbers of sky fibers to use for different models. ex. --nsky_list 1 2 3 4")
    parser.add_argument("--reps", type=int, default=5, help="number of realizations for each model (default 5)")

    if options is None:
        options = sys.argv[2:]

    args = parser.parse_args(options)
    
    wave_filters = run.get_wave_filters(args.night, args.expid, list(args.cam))
    
    fig1 = plot_unsubtracted_sky(args.night, args.expid, args.cam, args.nsky, args.rep, args.basedir, wave_filters[args.cam], 'Frame {}'.format(args.cam), height=350, width=400)
    fig2 = plot_subtracted_sky(args.night, args.expid, args.cam, args.nsky, args.rep, args.basedir, wave_filters[args.cam], 'S-Frame'.format(args.cam), height=350, width=400)
    sky_fig = row([fig1, fig2])
    
    bk.output_file(args.outdir + "sky_plots-{}-{:08d}".format(args.night, args.expid))
    bk.save(sky_fig)
    
if __name__ == "__main__":
    main()
    