# This program corresponds to a probe moving in axial(cm) and theta(degree) direction.
# It calls Acquire_Scope_Data_2D.py to acquire data and save it in an HDF5 file.
# The GUI directly communicate with this program to
# 	1) Set up the positions array
# 	2) Set the Lecroy scope IP address and the IP addresses of the motors.
# 	3) Set the hdf5 filename (if not, a file dialog will pop up)
# 	4) Set descriptions of the channels being recorded


import math
import numpy
import tkinter

from tkinter import filedialog
from typing import Tuple, Union

from Acquire_Scope_Data_2D import Acquire_Scope_Data_2D
from LeCroy_Scope import EXPANDED_TRACE_NAMES

##########################################################################################

# user: set up simple positions array here (see function get_positions() below)
xmin = 0
xmax = 1
nx = 2

ymin = 0
ymax = 0
ny = 1

# vmin = -1.0
# vmax = 0.5
# nv =   31

# user: set known ip addresses:
#    scope  - see Utility | Remote menu item in scope to determine current IP address
#    x  - motion in/out. IP address set by dial on motor
#    y  - motion transverse. IP address set by dial on motor
#    z  - motion vertical. IP address set by Applied Motion program on PC
#    agilent - waveform generator IP address (actually Raspberry Pi that
#              is controlling the Agilent)
#    do NOT set agilent if not being used
#
ip_addrs = {"scope": "128.97.13.195", "x": "128.97.13.198", "y": "128.97.13.197"}


# user: set output file name, or None for prompt (see function get_hdf5_filename() below)
# e.g. "161014_I25_F35_P3e-4_Ar.hdf5"
hdf5_filename = None  # type: Union[None, str]

##########################################################################################
# user: set channel descriptions


def get_channel_description(tr) -> str:
    """
    callback function to return a string containing a description of
    the data in each recorded channel
    """

    # user: assign channel description text here to override the default:
    if tr == "C1":
        return (
            "(aliased) current from Pearson at .01V/A; note 50 ohms provided externally"
        )
    if tr == "C2":
        # return "Miana bx-dot (x10) with centering ring"
        # return "Iisat 1k 40V"
        return "I_isat 470 ohm, variable bias"
    if tr == "C3":
        # return "Miana by-dot (x10) with centering ring"
        # return "na"
        # return "VRF"
        # return "Miana by-dot (x10)"
        return "negative of Vbias"
    if tr == "C4":
        # return "Miana bz-dot (x10) with centering ring"
        # return "na"
        # return "Miana bz-dot (x10)"
        return "current envelope ~200A/V"

    # otherwise, program-generated default description strings follow
    if tr in EXPANDED_TRACE_NAMES.keys():
        return f"no entered description for {EXPANDED_TRACE_NAMES[tr]}"

    return (
        f"**** get_channel_description(): "
        f"unknown trace indicator '{tr}'. How did we get here?"
    )


def get_positions() -> Tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]:
    """
    callback function to return the positions array

    This function is baroque because we need to to match the legacy format.
    In particular, we assign the positions array as an array of tuples
    """
    # for simplicity, axial position is refered to "x" and
    # theta position is refered to "y"

    global xmin, xmax, nx
    global ymin, ymax, ny

    xpos = numpy.linspace(xmin, xmax, nx)
    ypos = numpy.linspace(ymin, ymax, ny)

    nx = len(xpos)
    ny = len(ypos)

    num_duplicate_shots = 1  # number of duplicate shots recorded at the ith location
    num_run_repeats = 1  # number of times to repeat sequentially over all locations

    # allocate the positions array, fill it with zeros
    positions = numpy.zeros(
        (nx * ny * num_duplicate_shots * num_run_repeats),
        dtype=[("Line_number", ">u4"), ("x", ">f4"), ("y", ">f4")],
    )

    # create rectangular shape position array with height z
    index = 0
    for repeat_cnt in range(num_run_repeats):
        for y in ypos:
            for x in xpos:
                for dup_cnt in range(num_duplicate_shots):
                    positions[index] = (index + 1, x, y)
                    index += 1

    return positions, xpos, ypos


def get_hdf5_filename() -> str:
    """actual callback function to return the output file name"""
    global hdf5_filename  # type: Union[None, str]

    # Setting avoid_overwrite to False will allow overwriting an existing
    # file without a prompt
    avoid_overwrite = True

    fn = hdf5_filename
    if fn is None or len(fn) == 0 or (avoid_overwrite and os.path.isfile(fn)):
        # if we are not allowing possible overwrites as default and the
        # file already exists, use file open dialog
        tk = tkinter.Tk()
        tk.withdraw()
        fn = filedialog.asksaveasfilename(title="Enter name of HDF5 file to write")
        if len(fn) == 0:
            # user pressed 'cancel'
            raise SystemExit(0)
        tk.destroy()

    hdf5_filename = fn
    return fn


if __name__ == "__main__":
    import os
    import time

    Acquire_Scope_Data_2D(
        get_hdf5_filename, get_positions, get_channel_description, ip_addrs
    )

    # when done, find size of hdf5 file
    if os.path.isfile(hdf5_filename):
        size = os.stat(hdf5_filename).st_size / (1024 * 1024)
        print(
            f"wrote file '{hdf5_filename}',  {time.ctime()}, {size:6.2f} MB",
        )
    else:
        print(
            f"*********** file '{hdf5_filename}' is not found - this seems bad",
        )

    print("\ndone")
