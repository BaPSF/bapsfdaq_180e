# -*- coding: utf-8 -*-
"""
 The main data acquisition routine is in this file

 function Acquire_Scope_Data_3D()  - see below
    Uses user-provided callback functions (given as args) to:
        specify the output HDF5 filename and whether duplicates should be overwritten
        specify the positions array, and
        specify the individual channel descriptions (c = 'C1', 'C2', 'C3', 'C4')
    the fourth arg is the scope_ip_address
 this function
    Creates the HDF5 file,
    Creates the various groups and datasets,
    Adds metadata
    Iterates through the positions array (see "MAIN ACQUISITION LOOP"):
        calls Motor_Control_2D -> move_to_position(x,y,z)
        Waits for the scope to average the data, as per scope settings
        Writes the acquired scope data to the HDF5 output file
    Closes the HDF5 file when done
"""

import numpy
import h5py as h5py
import time
import os.path
import sys

from LeCroy_Scope import LeCroy_Scope, WAVEDESC_SIZE
from Motor_Control_2D import Motor_Control_2D
#from wavegen_control import wavegen_control

#----------------------------------------------------------------------------------------

def acquire_displayed_traces(scope, datasets, hdr_data, pos_ndx):
    """ worker for below :
        acquire enough sweeps for the averaging, then read displayed scope trace data into HDF5 datasets
    """
    timeout = 2000 # seconds
    timed_out, N = scope.wait_for_max_sweeps(str(pos_ndx)+': ', timeout)  # leaves scope not triggering

    if timed_out:
        print('**** averaging timed out: got '+str(N)+' at %.6g s' % timeout)

    traces = scope.displayed_traces()

    for tr in traces:
        NPos,NTimes = datasets[tr].shape
        datasets[tr][pos_ndx,0:NTimes] = scope.acquire(tr)[0:NTimes]    # sometimes for 10000 the scope hardware returns 10001 samples, so we have to specify [0:NTimes]
        #?# datasets[tr].flush()
        hdr_data[tr][pos_ndx] = numpy.void(scope.header_bytes())    # valid after scope.acquire()
        #?# hdr_data[tr].flush()
        #?# are there consequences in timing or compression size if we do the flush()s recommend for the SWMR function?

    scope.set_trigger_mode('NORM')   # resume triggering

#----------------------------------------------------------------------------------------

def create_sourcefile_dataset(grp, fn):
    """ worker for below:
        create an HDF5 dataset containing the contents of the specified file
        add attributes file name and modified time
    """
    fds_name = os.path.basename(fn)
    fds = grp.create_dataset(fds_name, data=open(fn, 'r').read())
    fds.attrs['filename'] = fn
    fds.attrs['modified'] = time.ctime(os.path.getmtime(fn))

#----------------------------------------------------------------------------------------

def Acquire_Scope_Data_2D(get_hdf5_filename, get_positions, get_channel_description, get_ip_addresses):
    # The main data acquisition routine
    #
    # 	Arguments are user-provided callback functions that return the following:
    # 		get_hdf5_filename()          the output HDF5 filename,
    # 		get_positions()              the positions array,
    # 		get_channel_description(c)   the individual channel descriptions (c = 'C1', 'C2', 'C3', 'C4'),
    # 		get_ip_addresses()           a dict of the form {'scope':'10.0.1.122', 'x':'10.0.0.123', 'y':'10.0.0.124', 'z':''}
    # 		                                  if a key is not specified, no motion will be attempted on that axis
    #
    # 	Creates the HDF5 file, creates the various groups and datasets, adds metadata (see "HDF5 OUTPUT FILE SETUP")
    #
    # 	Iterates through the positions array (see "MAIN ACQUISITION LOOP"):
    # 	    calls motor_control.set_position(pos)
    # 	    Waits for the scope to average the data, as per scope settings
    # 	    Writes the acquired scope data to the HDF5 output file
    #
    # 	Closes the HDF5 file when done
    #
    #============================
    # list of files to include in the HDF5 data file
    src_files = [sys.argv[0],
                __file__,           # ASSUME this file is in the same directory as the next two:
                os.path.dirname(__file__)+os.sep+'LeCroy_Scope.py',
                os.path.dirname(__file__)+os.sep+'Motor_Control_2D.py'
               ]
    #for testing, list these:s
    print('Files to record in the hdf5 archive:')
    print('    invoking file      =', src_files[0])
    print('    this file          =', src_files[1])
    print('    LeCroy_Scope file  =', src_files[2])
    print('    motor control file =', src_files[3])

    #============================
    # position array given by Data_Run_GUI_2D.py:
    positions, xpos, ypos = get_positions()

    # Create empty position arrays
    if xpos is None:
        xpos = numpy.array([])
    if ypos is None:
        ypos = numpy.array([])

    #============================

    ip_addresses = get_ip_addresses

    mc = Motor_Control_2D(x_ip_addr = ip_addresses['x'], y_ip_addr = ip_addresses['y'])


    ######### HDF5 OUTPUT FILE SETUP #########

    # Open hdf5 file for writing (user callback for filename):

    ofn = get_hdf5_filename()      # callback arg to the current function

    f = h5py.File(ofn,  'w')  # 'w' - overwrite (we should have determined whether we want to overwrite in get_hdf5_filename())
    # f = h5py.File(ofn,  'x')  # 'x' - no overwrite

    #============================
    # create HDF5 groups similar to those in the legacy format:

    acq_grp    = f.create_group('/Acquisition')              # /Acquisition
    acq_grp.attrs['run_time'] = time.ctime()                                       # not legacy
    scope_grp  = acq_grp.create_group('LeCroy_scope')        # /Acquisition/LeCroy_scope
    header_grp = scope_grp.create_group('Headers')                                 # not legacy

    ctl_grp    = f.create_group('/Control')                  # /Control
    pos_grp    = ctl_grp.create_group('Positions')           # /Control/Positions

    meta_grp   = f.create_group('/Meta')                     # /Meta                not legacy
    script_grp = meta_grp.create_group('Python')             # /Meta/Python
    scriptfiles_grp = script_grp.create_group('Files')       # /Meta/Python/Files

    # in the /Meta/Python/Files group:
    for src_file in src_files:
        create_sourcefile_dataset(scriptfiles_grp, src_file)                       # not legacy

    # I don't know how to get this information from the scope:
    scope_grp.create_dataset('LeCroy_scope_Setup_Arrray', data=numpy.array('Sorry, this is not included', dtype='S'))

    pos_ds = pos_grp.create_dataset('positions_setup_array', data=positions)
    pos_ds.attrs['xpos'] = xpos                                                     # not legacy
    pos_ds.attrs['ypos'] = ypos                                                     # not legacy

    # create the scope access object, and iterate over positions
    with LeCroy_Scope(ip_addresses['scope'], verbose=False) as scope:
        if not scope:
            print('Scope not found at '+ip_addresses['scope'])      # I think we have raised an exception if this is the case, so we never get here
            return

        scope_grp.attrs['ScopeType'] = scope.idn_string

        NPos = len(positions)
        NTimes = scope.max_samples()

        datasets = {}
        hdr_data = {}

        # create 4 default data sets, empty.  These will all be populated for compatibility with legacy format hdf5 files.

        datasets['C1'] = scope_grp.create_dataset('Channel1', shape=(NPos,NTimes), fletcher32=True, compression='gzip', compression_opts=9)
        datasets['C2'] = scope_grp.create_dataset('Channel2', shape=(NPos,NTimes), fletcher32=True, compression='gzip', compression_opts=9)
        datasets['C3'] = scope_grp.create_dataset('Channel3', shape=(NPos,NTimes), fletcher32=True, compression='gzip', compression_opts=9)
        datasets['C4'] = scope_grp.create_dataset('Channel4', shape=(NPos,NTimes), fletcher32=True, compression='gzip', compression_opts=9)

        # create other datasets, one for each displayed trace (but not C1-4, which we just did)
        # todo: should we maybe just ignore these?  or have a user option to include them?

        traces = scope.displayed_traces()
        for tr in traces:
            name = scope.expanded_name(tr)
            if tr not in ('C1','C2','C3','C4'):
                ds = scope_grp.create_dataset(name, (NPos,NTimes), chunks=(1,NTimes), fletcher32=True, compression='gzip', compression_opts=9)
                datasets[tr] = ds

        # For each trace we are storing, we will write one header per position (immediately after
       #    the data for that position has been acquired); these compress to an insignificant size
        # For whatever stupid reason we need to write the header as a binary blob using an "HDF5 opaque" type - here void type 'V346'  (otherwise I could not manage to avoid invisible string processing and interpretation)
        for tr in traces:
            name = scope.expanded_name(tr)
            hdr_data[tr] = header_grp.create_dataset(name, shape=(NPos,), dtype="V%i"%(WAVEDESC_SIZE), fletcher32=True, compression='gzip', compression_opts=9)  # V346 = void type, 346 bytes long

        # create "time" dataset
        time_ds = scope_grp.create_dataset('time', shape=(NTimes,), fletcher32=True, compression='gzip', compression_opts=9)

        # at this point all datasets should be created, so we can
        # switch to SWMR mode
        #?# f.swmr_mode = True    # SWMR MODE: DO NOT CREATE ANY MORE DATASETS AFTER THIS
        #?# check effects of flushing...see above

        try:  # try-catch for Ctrl-C keyboard interrupt

            ######### BEGIN MAIN ACQUISITION LOOP #########
            print('starting acquisition loop at', time.ctime())
            acquisition_loop_start_time = time.time()

            for pos in positions:
                # move to next position
                print('position index =', pos[0], '  x =', pos[1], '  y =', pos[2], end='')
                mc.move_to_position(pos[1], pos[2])

                if pos[0] > 1:
                    print ('   %6.2f'%((len(positions) - pos[0]) * (time.time()-acquisition_loop_start_time)/pos[0] / 3600))
                else:
                    print ('')

                print('------------------', scope.gaaak_count, '-------------------- ',pos[0],sep='')

#				scope.autoscale('C3')  # for now can only _increase_ the V/div

                # do averaging, and copy scope data for each trace on the screen to the output HDF5 file
                acquire_displayed_traces(scope, datasets, hdr_data, pos[0]-1)   # argh the pos[0] index is 1-based

                # at least get one time array recorded for swmr functions
                if pos[0] == 1:
                    time_ds[0:NTimes] = scope.time_array()[0:NTimes]
                    #time_ds.flush()

            ######### END MAIN ACQUISITION LOOP #########

        except KeyboardInterrupt:
            print('\n______Halted due to Ctrl-C______', '  at', time.ctime())

        # copy the array of time values, corresponding to the last acquired trace, to the times_dataset
        time_ds[0:NTimes] = scope.time_array()[0:NTimes]      # specify number of points, sometimes scope return extras
        if type(time_ds) == 'stupid':
            print(' this is only included to make the linter happy, otherwise it thinks time_ds is not used')

        # Set any unused datasets to 0 (e.g. any C1-4 that was not acquired); when compressed they require negligible space
        # Also add the text descriptions.    Do these together to be able to be able to make a note in the description
        for tr in traces:
            if datasets[tr].len() == 0:
                datasets[tr] = numpy.zeros(shape=(NPos,NTimes))
                datasets[tr].attrs['description'] = 'NOT RECORDED: ' + get_channel_description(tr)           # callback arg to the current function
                datasets[tr].attrs['recorded']    = False
            else:
                datasets[tr].attrs['description'] = get_channel_description(tr)                              # callback arg to the current function
                datasets[tr].attrs['recorded']    = True

    f.close()  # close the HDF5 file
    #done
