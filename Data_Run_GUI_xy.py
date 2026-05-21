# This graphic user interface allows user to
# (1) set up data point positions, channel description and start data acquisition
#     (by calling Data_Run_2D.py or Data_Run_3D.py)
# (2) control the motor (by calling Motor_Control_2D.py or Motor_Control_3D.py)
# (3) view graphic display of the current probe position and data point
#     positions in the chamber
#
# Author: Yuchen Qian
# Oct 2017
#

import datetime
import h5py
import math
import numpy
import os
import os.path
import sys
import time
import tkinter
import tkinter.messagebox

from PyQt5.QtCore import pyqtSignal, QObject, QRunnable, QThreadPool, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QWidget,
)
from scipy.linalg import norm
from tkinter import filedialog
from typing import Any, Dict, Tuple, Union

from lab_scopes.lecroy import EXPANDED_TRACE_NAMES, WAVEDESC_SIZE, LeCroyScope
from Motor_Control_2D_xy import Motor_Control_2D

# noqa
# the matplotlib backend imports must happen after import matplotlib and
# PySide6 (or any Qt bindings)
import matplotlib as mpl  # noqa
import matplotlib.collections  # noqa
import matplotlib.figure  # noqa
import matplotlib.patches  # noqa

mpl.use("qtagg")  # matplotlib's backend for Qt bindings
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas  # noqa
from mpl_toolkits.mplot3d import axes3d  # noqa

dir_path = os.path.dirname(os.path.realpath(__file__))
version_number = "03/01/2018 12:37pm"  # update this when a change has been made
data_running = False


class MyMplCanvas(FigureCanvas):
    """
    Ultimately, this is a QWidget (as well as a FigureCanvasAgg, etc.).
    """

    def __init__(self, parent=None, width=6, height=3, dpi=100):
        fig = mpl.figure.Figure(figsize=(width, height), dpi=dpi)
        self.ax = fig.add_subplot(111)
        self.ax.set_xlim(-25, 25)
        self.ax.set_ylim(-25, 25)

        FigureCanvas.__init__(self, fig)
        self.setParent(parent)

        # initialize some attributes
        self._parameters = None

        FigureCanvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

        self.ax.grid(which="both")
        self.ax.add_patch(
            mpl.patches.Rectangle((-38, -50), 76, 100, fill=False, edgecolor="red")
        )

        self.matrix = self.ax.scatter(0, 0, 0, color="blue", marker="o")
        self.point = self.ax.scatter(0, 0, 0, color="red", marker="*")

        # initialized content around visited_points
        self._visited_points = None
        self.finished_x = None
        self.finished_y = None
        self.initialize_visited_points()

    @property
    def parameters(self) -> Dict[str, Any]:
        if self._parameters is None:
            self._parameters = {}

        return self._parameters

    @property
    def visited_points(self) -> mpl.collections.PathCollection:
        return self._visited_points

    def update_figure(self, param):

        self._parameters = param

        xmax = self.parameters["xmax"]
        xmin = self.parameters["xmin"]
        ymax = self.parameters["ymax"]
        ymin = self.parameters["ymin"]
        nx = self.parameters["nx"]
        ny = self.parameters["ny"]

        xpos = numpy.linspace(xmin, xmax, nx)
        ypos = numpy.linspace(ymin, ymax, ny)

        X = numpy.zeros(nx * ny)
        Y = numpy.zeros(nx * ny)

        index = 0
        for xx in xpos:
            for yy in ypos:
                X[index] = xx
                Y[index] = yy
                index += 1
        self.matrix = self.ax.scatter(self.X, self.Y, color="blue", marker="o")
        self.draw()
        print(self.parameters)

    def update_probe(self, xnow, ynow):
        self.point = self.ax.scatter(xnow, ynow, color="red", marker="*")
        self.draw()

    def update_axis(self, x1, y1, x2, y2):
        self.ax.set_xlim(x2, x1)
        self.ax.set_ylim(y2, y1)

    def finished_positions(self, x, y):
        self.finished_x.append(x)
        self.finished_y.append(y)
        self._visited_points = self.ax.scatter(
            self.finished_x, self.finished_y, color="green", marker="o"
        )
        self.draw()

    def initialize_visited_points(self):
        self.finished_x = []
        self.finished_y = []
        self._visited_points = self.ax.scatter(
            self.finished_x, self.finished_y, color="green", marker="o"
        )


class AxisControls(QGroupBox):
    def __init__(self):
        super().__init__()
        self.xupInput = QSpinBox()
        self.yupInput = QSpinBox()
        self.xlowInput = QSpinBox()
        self.ylowInput = QSpinBox()

        self.xupInput.setRange(-60, 60)
        self.yupInput.setRange(-60, 60)
        self.xlowInput.setRange(-60, 60)
        self.ylowInput.setRange(-60, 60)

        self.xupInput.setValue(25)
        self.yupInput.setValue(25)
        self.xlowInput.setValue(-25)
        self.ylowInput.setValue(-25)

        self.xaxisLabel = QLabel("x axis range:")
        self.yaxisLabel = QLabel("y axis range:")
        self.toLabel = QLabel("to")
        self.toLabel2 = QLabel("to")
        self.blankLabel = QLabel("  ")

        axisLayout = QGridLayout()
        axisLayout.addWidget(self.xaxisLabel, 0, 0)
        axisLayout.addWidget(self.xlowInput, 0, 1)
        axisLayout.addWidget(self.toLabel, 0, 2)
        axisLayout.addWidget(self.xupInput, 0, 3)
        axisLayout.addWidget(self.blankLabel, 0, 4)
        axisLayout.addWidget(self.yaxisLabel, 0, 5)
        axisLayout.addWidget(self.ylowInput, 0, 6)
        axisLayout.addWidget(self.toLabel2, 0, 7)
        axisLayout.addWidget(self.yupInput, 0, 8)
        self.setLayout(axisLayout)


class PositionControls(QGroupBox):
    def __init__(self):
        super().__init__()
        self.setTitle("Set up DAQ position")

        self.xMaxLabel = QLabel("Max x:")
        self.xMinLabel = QLabel("Min x:")
        self.yMaxLabel = QLabel("Max y:")
        self.yMinLabel = QLabel("Min y:")
        self.nxLabel = QLabel("nx:")
        self.nyLabel = QLabel("ny:")

        self.xMaxInput = QLineEdit()
        self.xMinInput = QLineEdit()
        self.yMaxInput = QLineEdit()
        self.yMinInput = QLineEdit()
        self.nxInput = QLineEdit()
        self.nyInput = QLineEdit()

        self.xMaxInput.setText("0")
        self.xMinInput.setText("0")
        self.yMaxInput.setText("0")
        self.yMinInput.setText("0")
        self.nxInput.setText("1")
        self.nyInput.setText("1")

        self.ConfirmButton = QPushButton("Confirm Input", self)

        controlsLayout = QGridLayout()
        controlsLayout.addWidget(self.xMaxLabel, 0, 0)
        controlsLayout.addWidget(self.xMinLabel, 1, 0)
        controlsLayout.addWidget(self.yMaxLabel, 2, 0)
        controlsLayout.addWidget(self.yMinLabel, 3, 0)
        controlsLayout.addWidget(self.nxLabel, 4, 0)
        controlsLayout.addWidget(self.nyLabel, 5, 0)

        controlsLayout.addWidget(self.xMaxInput, 0, 1)
        controlsLayout.addWidget(self.xMinInput, 1, 1)
        controlsLayout.addWidget(self.yMaxInput, 2, 1)
        controlsLayout.addWidget(self.yMinInput, 3, 1)
        controlsLayout.addWidget(self.nxInput, 4, 1)
        controlsLayout.addWidget(self.nyInput, 5, 1)

        controlsLayout.addWidget(self.ConfirmButton, 6, 1)

        self.setLayout(controlsLayout)


class AcquisitionControls(QGroupBox):

    def __init__(self):
        super().__init__()
        self.DataRun = QPushButton("Start Data Acquisition", self)
        self.TestShot = QPushButton("Take Single Test Shot", self)
        self.num_run = QSpinBox()
        self.num_shots = QSpinBox()
        self.num_run_label = QLabel("Number of total runs:")
        self.num_shots_label = QLabel("Shots per position:")

        self.num_run.setRange(1, 100)
        self.num_shots.setRange(1, 200)
        self.num_run.setValue(1)
        self.num_shots.setValue(1)

        ACLayout = QGridLayout()
        ACLayout.addWidget(self.DataRun, 0, 0)
        ACLayout.addWidget(self.TestShot, 0, 1)
        ACLayout.addWidget(self.num_run_label, 1, 0)
        ACLayout.addWidget(self.num_shots_label, 2, 0)
        ACLayout.addWidget(self.num_run, 1, 1)
        ACLayout.addWidget(self.num_shots, 2, 1)

        self.setLayout(ACLayout)


class MotorMovement(QGroupBox):

    def __init__(self, x_ip_addr=None, y_ip_addr=None, MOTOR_PORT=None):
        super().__init__()
        self.setTitle("Motor Movement Control")

        # Initialize some attributes
        self.x_ip_addr = x_ip_addr
        self.y_ip_addr = y_ip_addr
        self.MOTOR_PORT = MOTOR_PORT
        self.speedx = None  # type: Union[None, float]
        self.speedy = None  # type: Union[None, float]

        # (cm) Move probe to absolute position along the shaft counted by motor encoder
        self.xMoveLabel = QLabel("Move x motor to:")
        self.yMoveLabel = QLabel("Move y motor to:")
        self.xMoveInput = QLineEdit()
        self.yMoveInput = QLineEdit()

        # For 3D acquisition, need another feature to move the probe to
        # absolute position.  This should be done by calling
        # "move_to_position" function in Motor_Control_3D, with corresponding
        # geometry calculation

        # Set velocity.
        self.xvLabel = QLabel("Set x velocity:")
        self.yvLabel = QLabel("Set y velocity:")
        self.xvInput = QLineEdit()
        self.yvInput = QLineEdit()

        self.MoveButton = QPushButton("Move Motor", self)
        self.StopNowButton = QPushButton("BUG (Don't click)", self)
        self.SetZero = QPushButton("Set Zero (Don't click or get an F)", self)
        self.SetVelocity = QPushButton("Set Velocity", self)
        self.MoveButton.clicked.connect(self.move_to_position)
        self.StopNowButton.clicked.connect(self.stop_now)
        self.SetZero.clicked.connect(self.zero)
        self.SetVelocity.clicked.connect(self.set_velocity)

        self.CurposLabel = QLabel("Current probe position (cm, cm):")
        self.CurposInput = QLineEdit(readOnly=True)
        self.velocityButton = QPushButton("Get motor speed (rpm):")
        self.velocityInput = QLineEdit(readOnly=True)
        self.velocityButton.clicked.connect(self.update_current_speed)

        MMLayout = QGridLayout()
        MMLayout.addWidget(self.xMoveLabel, 0, 0)
        MMLayout.addWidget(self.yMoveLabel, 0, 1)
        MMLayout.addWidget(self.xMoveInput, 1, 0)
        MMLayout.addWidget(self.yMoveInput, 1, 1)
        MMLayout.addWidget(self.MoveButton, 1, 2)
        MMLayout.addWidget(self.xvLabel, 2, 0)
        MMLayout.addWidget(self.yvLabel, 2, 1)
        MMLayout.addWidget(self.xvInput, 3, 0)
        MMLayout.addWidget(self.yvInput, 3, 1)
        MMLayout.addWidget(self.SetVelocity, 3, 2)
        MMLayout.addWidget(self.SetZero, 4, 0)
        MMLayout.addWidget(self.StopNowButton, 4, 1)
        MMLayout.addWidget(self.CurposLabel, 5, 0)
        MMLayout.addWidget(self.CurposInput, 5, 1, 1, 2)
        MMLayout.addWidget(self.velocityButton, 6, 0)
        MMLayout.addWidget(self.velocityInput, 6, 1, 1, 2)

        self.setLayout(MMLayout)

        self.mc = Motor_Control_2D(x_ip_addr=self.x_ip_addr, y_ip_addr=self.y_ip_addr)
        self.mc.sdsdsdsds()

    def move_to_position(self):
        # Directly move the motor to their absolute position
        try:
            x_pos = float(self.xMoveInput.text())
            y_pos = float(self.yMoveInput.text())
            self.mc.enable()
            self.mc.move_to_position(x_pos, y_pos)
            self.mc.disable()
        except ValueError:
            QMessageBox.about(self, "Error", "Position should be valid numbers.")

    def disable(self):
        self.mc.disable()

    def stop_now(self):
        # Stop motor movement now
        self.mc.stop_now()

    def zero(self):
        zeroreply = QMessageBox.question(
            self,
            "Set Zero",
            "You are about to set the current probe position to (0,0). Are you sure?",
            QMessageBox.Yes,
            QMessageBox.No,
        )
        if zeroreply == QMessageBox.Yes:
            QMessageBox.about(self, "Set Zero", "Probe position is now (0,0).")
            self.mc.set_zero()

    def ask_velocity(self):
        return self.mc.ask_velocity()

    def set_velocity(self):
        xv = self.xvInput.text()
        yv = self.yvInput.text()
        self.mc.set_velocity(xv, yv)

    def current_probe_position(self):
        return self.mc.current_probe_position()

    def update_current_speed(self):
        self.speedx, self.speedy = self.ask_velocity()
        self.velocityInput.setText(f"({self.speedx} , {self.speedy})")

    def set_input_usage(self, usage):
        self.mc.set_input_usage(usage)

    def set_steps_per_rev(self, stepsx, stepsy):
        self.mc.set_steps_per_rev(stepsx, stepsy)


class ScopeChannel(QGroupBox):
    def __init__(self):
        super().__init__()

        self.titleLabel = QLabel("Enter channel descriptions")
        self.c1Label = QLabel("Channel 1:")
        self.c2Label = QLabel("Channel 2:")
        self.c3Label = QLabel("Channel 3:")
        self.c4Label = QLabel("Channel 4:")
        self.c1Input = QLineEdit()
        self.c2Input = QLineEdit()
        self.c3Input = QLineEdit()
        self.c4Input = QLineEdit()

        SCLayout = QGridLayout()
        SCLayout.addWidget(self.titleLabel, 0, 0, 1, 2)
        SCLayout.addWidget(self.c1Label, 1, 0)
        SCLayout.addWidget(self.c2Label, 2, 0)
        SCLayout.addWidget(self.c3Label, 3, 0)
        SCLayout.addWidget(self.c4Label, 4, 0)
        SCLayout.addWidget(self.c1Input, 1, 1)
        SCLayout.addWidget(self.c2Input, 2, 1)
        SCLayout.addWidget(self.c3Input, 3, 1)
        SCLayout.addWidget(self.c4Input, 4, 1)
        self.setLayout(SCLayout)


class SoftwareVersion(QGroupBox):
    def __init__(self):
        super().__init__()
        self.mod_timestr = os.path.getmtime(dir_path)
        self.mod_datetime = datetime.datetime.fromtimestamp(self.mod_timestr).strftime(
            "%Y-%b-%d %H:%M:%S %p"
        )
        self.vLabel = QLabel("Last Modified: ")
        self.lastmodified = QLabel(self.mod_datetime)
        self.version = QLabel("Version: " + version_number)

        SVLayout = QGridLayout()
        SVLayout.addWidget(self.vLabel, 0, 0)
        SVLayout.addWidget(self.lastmodified, 1, 0)
        SVLayout.addWidget(self.version, 2, 0)
        self.setLayout(SVLayout)


class Signals(QObject):
    finished = pyqtSignal()
    updated_position = pyqtSignal(float, float)
    new_screen_dump = pyqtSignal()
    finished_position = pyqtSignal(float, float)
    cancel = pyqtSignal()


class DataRunThread(QRunnable):

    def __init__(self, hdf5_filename, pos_param, channel_description, ip_addrs):
        super(DataRunThread, self).__init__()

        self.hdf5_filename = hdf5_filename
        self.pos_param = pos_param
        self.channel = channel_description
        self.ip_addrs = ip_addrs
        self.signals = Signals()

    def get_channel_description(self, tr) -> str:
        """
        Return a string containing a description of the data in each
        recorded channel.
        """

        # user: assign channel description text here to override the default:
        if tr in ("C1", "C2", "C3", "C4"):
            desc = self.channel.get(tr, None)

            if desc is not None:
                return desc

        # otherwise, program-generated default description strings follow
        if tr in EXPANDED_TRACE_NAMES.keys():
            return f"no entered description for {EXPANDED_TRACE_NAMES[tr]}"

        return (
            f"**** get_channel_description(): unknown trace indicator '{tr}'."
            f" How did we get here?"
        )

    def get_positions(self) -> Tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray, int]:
        """
        Return the positions array.

        This function is baroque because we need to to match the legacy
        format.  In particular, we assign the positions array as an
        array of tuples.
        """

        xmax = self.pos_param["xmax"]
        xmin = self.pos_param["xmin"]
        ymax = self.pos_param["ymax"]
        ymin = self.pos_param["ymin"]
        nx = self.pos_param["nx"]
        ny = self.pos_param["ny"]

        xpos = numpy.linspace(xmin, xmax, nx)
        ypos = numpy.linspace(ymin, ymax, ny)

        num_duplicate_shots = self.pos_param[
            "num_shots"
        ]  # number of duplicate shots recorded at the ith location
        num_run_repeats = self.pos_param[
            "num_run"
        ]  # number of times to repeat sequentially over all locations

        # allocate the positions array, fill it with zeros
        positions = numpy.zeros(
            (nx * ny * num_duplicate_shots * num_run_repeats),
            dtype=[("Line_number", ">u4"), ("x", ">f4"), ("y", ">f4")],
        )

        # create rectangular shape position array
        index = 0
        for repeat_cnt in range(num_run_repeats):
            for y in ypos:
                for x in xpos:
                    for dup_cnt in range(num_duplicate_shots):
                        positions[index] = (index + 1, x, y)
                        index += 1

        return positions, xpos, ypos, num_duplicate_shots

    def get_hdf5_filename(self) -> str:

        # Setting avoid_overwrite to False will allow overwriting an
        # existing file without a prompt
        avoid_overwrite = True

        fn = self.hdf5_filename
        if fn is None or len(fn) == 0 or (avoid_overwrite and os.path.isfile(fn)):
            # if we are not allowing possible overwrites as default and the file
            # already exists, use file open dialog
            tk = tkinter.Tk()
            tk.withdraw()  # prevent tk GUI from popping up
            fnoptions = {
                "title": "Save file as ...",
                "defaultextension": ".hdf5",
                "filetypes": [
                    ("Hierarchical Data Format", "*.hdf5"),
                    ("All files", "*.*"),
                ],
            }

            fn = filedialog.asksaveasfilename(**fnoptions)
            if not fn:
                # if user pressed 'cancel', fn = None
                print("\nUser cancelled save file input.")

            tk.destroy()

        self.hdf5_filename = fn
        return fn

    def acquire_displayed_traces(self, scope: LeCroyScope, datasets, hdr_data, pos_ndx):
        """
        Acquire enough sweeps for the averaging, then read displayed
        scope trace data into HDF5 datasets.
        """
        timeout = 2000  # seconds
        timed_out, N = scope.wait_for_max_sweeps(
            f"{pos_ndx}: ", timeout
        )  # leaves scope not triggering

        if timed_out:
            print(f"**** averaging timed out: got {N} at {timeout:.6g} s")

        traces = scope.displayed_traces()

        for tr in traces:
            NPos, NTimes = datasets[tr].shape
            signal = scope.acquire(tr)  # type: numpy.ndarray
            try:
                datasets[tr][pos_ndx, ...] = signal[...]
            except KeyError as err:
                print(
                    f"{tr} is displayed on the scope but not recorded.  "
                    "To record this channel, please display the trace "
                    f"before starting the data run.  {err}"
                )
            except TypeError as err:
                # the returned signal does not always have exactly NTimes
                # samples.  It's is off by a few data points.
                signal_NTimes = signal.size
                if not numpy.isclose(signal_NTimes, NTimes, rtol=0.005, atol=0):
                    # the difference in the number of time samples is greater
                    # than 0.5%
                    raise err

                if NTimes > signal_NTimes:
                    datasets[tr][pos_ndx, 0:signal_NTimes] = signal[...]
                else:
                    datasets[tr][pos_ndx, ...] = signal[0:NTimes]

        for tr in traces:
            try:
                hdr_data[tr][pos_ndx] = numpy.void(
                    scope.header_bytes()
                )

                # Are there consequences in timing or compression size if
                # we do the flush()s recommend for the SWMR function?
                #
                # hdr_data[tr].flush()
            except KeyError:
                pass

        scope.set_trigger_mode("NORM")

    def create_sourcefile_dataset(self, grp, fn):
        """
        Create an HDF5 dataset containing the contents of the specified
        file add attributes file name and modified time.
        """
        fds_name = os.path.basename(fn)
        fds = grp.create_dataset(fds_name, data=open(fn, "r").read())
        fds.attrs["filename"] = fn
        fds.attrs["modified"] = time.ctime(os.path.getmtime(fn))

    def run(self):
        # The main data acquisition routine
        #
        # Arguments are user-provided callback functions that return the following:
        #   get_hdf5_filename()         the output HDF5 filename,
        #   get_positions()             the positions array,
        #   get_channel_description(c)  the individual channel descriptions
        #                                (c = 'C1', 'C2', 'C3', 'C4'),
        #   get_ip_addresses()          a dict of the form
        #                                {
        #                                   'scope': '10.0.1.122',
        #                                   'x': '10.0.0.123',
        #                                   'y': '10.0.0.124',
        #                                   'z': '',
        #                                }
        # 		                        if a key is not specified, no motion will
        # 		                         be attempted on that axis
        #
        # Creates the HDF5 file, creates the various groups and datasets, adds metadata (see "HDF5 OUTPUT FILE SETUP")
        #
        # Iterates through the positions array (see "MAIN ACQUISITION LOOP"):
        #   - calls motor_control.set_position(pos)
        #   - Waits for the scope to average the data, as per scope settings
        #   - Writes the acquired scope data to the HDF5 output file
        #
        # Closes the HDF5 file when done
        #
        # list of files to include in the HDF5 data file
        thispath = os.path.realpath(__file__)
        src_files = [
            thispath,  # ASSUME this file is in the same directory as the next two:
            f"{os.path.dirname(thispath)}{os.sep}LeCroy_Scope.py",
            f"{os.path.dirname(thispath)}{os.sep}Motor_Control_2D_xy.py",
        ]

        # for testing, list these:s
        print("Files to record in the hdf5 archive:")
        print(f"    invoking file (this file) = {src_files[0]}")
        print(f"    LeCroy_Scope file         = {src_files[1]}")
        print(f"    motor control file        = {src_files[2]}")

        # position array given by Data_Run_GUI_xy.py:
        positions, xpos, ypos, num_duplicate_shots = self.get_positions()

        # Create empty position arrays
        if xpos is None:
            xpos = numpy.array([])
        if ypos is None:
            ypos = numpy.array([])

        mc = Motor_Control_2D(x_ip_addr=self.ip_addrs["x"], y_ip_addr=self.ip_addrs["y"])

        ######### HDF5 OUTPUT FILE SETUP #########

        # Open hdf5 file for writing (user callback for filename):

        ofn = self.get_hdf5_filename()  # callback arg to the current function
        if not ofn:  # if user pressed cancel during input file name
            self.signals.cancel.emit()
            pass
        else:
            f = h5py.File(ofn, "w")

            # create HDF5 groups similar to those in the legacy format:
            acq_grp = f.create_group("/Acquisition")
            acq_grp.attrs["run_time"] = time.ctime()
            scope_grp = acq_grp.create_group("LeCroy_scope")
            header_grp = scope_grp.create_group("Headers")

            ctl_grp = f.create_group("/Control")
            pos_grp = ctl_grp.create_group("Positions")

            meta_grp = f.create_group("/Meta")
            script_grp = meta_grp.create_group("Python")
            scriptfiles_grp = script_grp.create_group("Files")

            # in the /Meta/Python/Files group:
            for src_file in src_files:
                self.create_sourcefile_dataset(scriptfiles_grp, src_file)

            # I don't know how to get this information from the scope:
            scope_grp.create_dataset(
                "LeCroy_scope_Setup_Arrray",
                data=numpy.array("Sorry, this is not included", dtype="S"),
            )

            pos_ds = pos_grp.create_dataset("positions_setup_array", data=positions)
            pos_ds.attrs["xpos"] = xpos
            pos_ds.attrs["ypos"] = ypos
            pos_ds.attrs["shotperpos"] = num_duplicate_shots

            # create the scope access object, and iterate over positions
            with LeCroyScope(
                self.ip_addrs["scope"], verbose=False
            ) as scope:  # type: LeCroyScope
                if not scope:
                    # I think we have raised an exception if this is the
                    # case, so we never get here
                    print(f"Scope not found at {self.ip_addrs["scope"]}")
                    return

                scope_grp.attrs["ScopeType"] = scope.idn_string

                NPos = len(positions)
                NTimes = (
                    scope.max_samples()
                )  # Scope somtimes return less sample than this

                datasets = {}
                hdr_data = {}

                # create other datasets, one for each displayed trace
                # (but not C1-4, which we just did)
                # TODO: should we maybe just ignore these?
                #       or have a user option to include them?
                #
                traces = scope.displayed_traces()
                for tr in traces:
                    name = scope.expanded_name(tr)
                    ds = scope_grp.create_dataset(
                        name,
                        shape=(NPos, NTimes),
                        fletcher32=True,
                        compression="gzip",
                        compression_opts=9,
                    )
                    datasets[tr] = ds

                # For each trace we are storing, we will write one header
                # per position (immediately after the data for that position
                # has been acquired).  These compress to an insignificant size.
                #
                # For whatever stupid reason we need to write the header as a
                # binary blob using an "HDF5 opaque" type - here void type 'V346'
                # (otherwise I could not manage to avoid invisible string
                # processing and interpretation)
                #
                for tr in traces:
                    name = scope.expanded_name(tr)
                    hdr_data[tr] = header_grp.create_dataset(
                        name,
                        shape=(NPos,),
                        dtype="V%i" % WAVEDESC_SIZE,
                        fletcher32=True,
                        compression="gzip",
                        compression_opts=9,
                    )  # V346 = void type, 346 bytes long

                # create "time" dataset
                time_ds = scope_grp.create_dataset(
                    "time",
                    shape=(NTimes,),
                    fletcher32=True,
                    compression="gzip",
                    compression_opts=9,
                )

                # At this point all datasets should be created, so we can
                # switch to SWMR mode
                # f.swmr_mode = True    # SWMR MODE: DO NOT CREATE ANY MORE DATASETS AFTER THIS
                # check effects of flushing...see above

                try:
                    # try-catch for Ctrl-C keyboard interrupt

                    print(f"starting acquisition loop at {time.ctime()}")
                    acquisition_loop_start_time = time.time()

                    nowx, nowy = (-999, -999)
                    for pos in positions:
                        # prevent motor from enabling/disabling when taking data
                        # at the same position this stops the motor noise from being
                        # picked up by the data in between shots
                        if nowx != pos[1] or nowy != pos[2]:
                            mc.enable()

                            # move to next position
                            print(
                                f"position index = {pos[0]}  x = {pos[1]}  y = {pos[2]}",
                                end="\n",
                            )
                            mc.move_to_position(pos[1], pos[2])
                            self.signals.updated_position.emit(pos[1], pos[2])
                            nowx, nowy = (pos[1], pos[2])
                            x_encoder, y_encoder = mc.current_probe_position()
                            self.signals.updated_position.emit(x_encoder, y_encoder)

                            mc.disable()

                        if pos[0] > 1:
                            time_delta = (
                                    (len(positions) - pos[0])
                                    * (time.time() - acquisition_loop_start_time)
                                    / (pos[0] * 3600)
                                )
                            print(f"Estimated remaining time:{time_delta:6.2f}")
                        else:
                            print("")

                        print(
                            f"------------------ {scope.gaaak_count}"
                            f"--------------------  {pos[0]}",
                        )

                        # Do averaging and copy scope data for each trace on
                        # the screen to the output HDF5 file
                        #
                        self.acquire_displayed_traces(
                            scope, datasets, hdr_data, pos[0] - 1
                        )  # argh the pos[0] index is 1-based

                        # Show plot traces on GUI
                        try:
                            scope.screen_dump()
                            self.signals.new_screen_dump.emit()
                        except:
                            print("Unable to grab screen due to unknown Error")
                            continue

                        self.signals.finished_position.emit(x_encoder, y_encoder)

                        # at least get one time array recorded for swmr functions
                        if pos[0] == 1:
                            time_array = scope.time_array()
                            try:
                                time_ds[...] = scope.time_array()[...]
                            except TypeError as err:
                                # the returned signal does not always have exactly NTimes
                                # samples.  It's is off by a few data points.
                                time_size = time_array.size
                                if not numpy.isclose(
                                    time_size, NTimes, rtol=0.005, atol=0
                                ):
                                    # the difference in the number of time
                                    # samples is greater than 0.5%
                                    raise err

                                if NTimes > time_size:
                                    time_ds[0:time_size] = time_array[...]
                                else:
                                    time_ds[...] = time_array[0:NTimes]

                except KeyboardInterrupt:
                    print(f"\n______Halted due to Ctrl-C______  at {time.ctime()}")

                # copy the array of time values, corresponding to the last acquired
                # trace, to the times_dataset
                time_array = scope.time_array()
                try:
                    time_ds[...] = scope.time_array()[...]
                except TypeError as err:
                    # the returned signal does not always have exactly NTimes
                    # samples.  It's is off by a few data points.
                    time_size = time_array.size
                    if not numpy.isclose(time_size, NTimes, rtol=0.005, atol=0):
                        # the difference in the number of time samples is greater
                        # than 0.5%
                        raise err

                    if NTimes > time_size:
                        time_ds[0:time_size] = time_array[...]
                    else:
                        time_ds[...] = time_array[0:NTimes]

                # Set any unused datasets to 0 (e.g. any C1-4 that was not acquired).
                # When compressed they require negligible space.
                # Also add the text descriptions.
                # Do these together to be able to be able to make a note in
                # the description.
                #
                for tr in traces:
                    if datasets[tr].len() == 0:
                        datasets[tr] = numpy.zeros(shape=(NPos, NTimes))
                        datasets[tr].attrs["description"] = (
                            f"NOT RECORDED: {self.get_channel_description(tr)}"
                        )
                        datasets[tr].attrs["recorded"] = False
                    else:
                        datasets[tr].attrs["description"] = (
                            self.get_channel_description(tr)
                        )
                        datasets[tr].attrs["recorded"] = True
                        datasets[tr].attrs["shots per position"] = (
                            self.pos_param["num_shots"]
                        )

            f.close()

            self.signals.finished.emit()


class TestShotThread(QRunnable):

    def __init__(self, ip_addrs):
        super(TestShotThread, self).__init__()
        self.signals = Signals()
        self.ip_addrs = ip_addrs

    def acquire_displayed_traces(self, scope):
        """
        Acquire enough sweeps for the averaging, then read displayed
        scope trace data into HDF5 datasets.
        """
        timeout = 2000  # seconds
        timed_out, N = scope.wait_for_max_sweeps(
            "Test shot: ", timeout
        )  # leaves scope not triggering

        if timed_out:
            print(f"**** averaging timed out: got {N} at {timeout:.6g} s")

        scope.screen_dump()
        self.signals.new_screen_dump.emit()
        scope.set_trigger_mode("NORM")  # resume triggering

    def run(self):
        with LeCroyScope(self.ip_addrs["scope"], verbose=False) as scope:
            if not scope:
                # I think we have raised an exception if this is the
                # case, so we never get here
                print(f"Scope not found at {self.ip_addrs['scope']}")
                return

            self.acquire_displayed_traces(scope)  # argh the pos[0] index is 1-based
        self.signals.finished.emit()


class Window(QWidget):

    def __init__(self):
        super(Window, self).__init__()

        # Initialize some attributes
        self.canvas = MyMplCanvas()
        self.sv = SoftwareVersion()
        self.sc = ScopeChannel()
        self.x_ip = "192.168.0.70"
        self.y_ip = "192.168.0.80"
        self.scope_ip = "192.168.0.60"
        self.port_ip = int(7776)
        self.threadpool = QThreadPool()
        self.xnow = None  # type: Union[None, float]
        self.ynow = None  # type: Union[None, float]
        self._parameters = None  # type: dict
        self.update = True

        # initialize motor movement controls
        self.mm = MotorMovement(
            x_ip_addr=self.x_ip, y_ip_addr=self.y_ip, MOTOR_PORT=self.port_ip
        )
        self.mm.set_input_usage(3)
        self.mm.set_steps_per_rev(20000, 20000)

        # initialize axis controls
        self.axc = AxisControls()
        self.axc.xupInput.valueChanged.connect(self.axis_change)
        self.axc.yupInput.valueChanged.connect(self.axis_change)
        self.axc.xlowInput.valueChanged.connect(self.axis_change)
        self.axc.ylowInput.valueChanged.connect(self.axis_change)

        # initialize position controls
        self.pc = PositionControls()
        self.pc.ConfirmButton.clicked.connect(self.update_geometry)

        # initialize acquisition controls
        self.ac = AcquisitionControls()
        self.ac.DataRun.clicked.connect(self.start_data_run)
        self.ac.TestShot.clicked.connect(self.start_test_shot)

        self.ScopeScreen = QLabel(self)
        self.update_screen_dump()

        layout = QGridLayout()
        layout.addWidget(self.canvas, 0, 0, 1, 2)
        layout.addWidget(self.axc, 1, 0, 1, 2)  # axes control
        layout.addWidget(self.mm, 2, 0, 2, 1)  # motor movement
        layout.addWidget(self.pc, 2, 1, 2, 1)  # position control
        layout.addWidget(self.ac, 2, 2)  # acquisition control
        layout.addWidget(self.sc, 2, 3, 2, 1)  # scope channel comments
        layout.addWidget(self.sv, 3, 2)
        layout.addWidget(self.ScopeScreen, 0, 2, 2, 2)
        self.setLayout(layout)

        self.setWindowTitle("180E Data Acquisition System for XY Probe Drives")
        self.resize(1600, 700)

        # Set timer to update current probe position and instant motor velocity
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_current_position)
        self.timer.start(500)

    @property
    def parameters(self) -> dict:
        if self._parameters is None:
            self._parameters = {}

        return self._parameters

    def axis_change(self):
        xup = self.axc.xupInput.value()
        yup = self.axc.yupInput.value()
        xlow = self.axc.xlowInput.value()
        ylow = self.axc.ylowInput.value()
        self.canvas.update_axis(xup, yup, xlow, ylow)

    def update_current_position(self):
        if not data_running:
            self.xnow, self.ynow = self.mm.current_probe_position()
            self.canvas.point.remove()
            self.canvas.update_probe(self.xnow, self.ynow)
            self.mm.CurposInput.setText(
                f"({round(self.xnow, 2)} , {round(self.ynow, 2)})"
            )

    def update_current_position_during_data_run(self, xnow, ynow):
        if not data_running:
            print("Why is this called when data_running == False ?")
            return

        self.xnow = xnow
        self.ynow = ynow
        self.canvas.point.remove()
        self.canvas.update_probe(self.xnow, self.ynow)
        self.mm.CurposInput.setText(
            "(" + str(round(self.xnow, 2)) + " ," + str(round(self.ynow, 2)) + ")"
        )

    def update_screen_dump(self):
        pixmap = QPixmap("scope_screen_dump.png")
        self.ScopeScreen.setPixmap(pixmap)

    def mark_finished_positions(self, x, y):
        if not data_running:
            print("Why is this called when data_running == False ?")
            return

        self.canvas.visited_points.remove()
        self.canvas.finished_positions(x, y)

    def update_current_speed(self):
        speedx, speedy = self.mm.ask_velocity()
        self.velocityInput.setText(f"({speedx} , {speedy})")

    def update_parameters(self):
        self.update = True
        try:
            self.parameters["xmax"] = float(self.pc.xMaxInput.text())
            self.parameters["xmin"] = float(self.pc.xMinInput.text())
            self.parameters["ymax"] = float(self.pc.yMaxInput.text())
            self.parameters["ymin"] = float(self.pc.yMinInput.text())
            self.parameters["nx"] = int(self.pc.nxInput.text())
            self.parameters["ny"] = int(self.pc.nyInput.text())
            return self.parameters
        except ValueError:
            QMessageBox.about(self, "Error", "Position should be valid numbers.")
            self.update = False

    def update_geometry(self):
        if not self.update:
            return
        params = self.update_parameters()
        self.canvas.matrix.remove()
        self.canvas.update_figure(params)

    def update_channel_information(self):
        return {
            "C1": self.sc.c1Input.text(),
            "C2": self.sc.c2Input.text(),
            "C3": self.sc.c3Input.text(),
            "C4": self.sc.c4Input.text(),
        }

    def start_data_run(self):
        # start data_run threading
        self.hdf5_filename = None

        self.pos_param = self.update_parameters()
        self.pos_param["num_shots"] = self.ac.num_shots.value()
        self.pos_param["num_run"] = self.ac.num_run.value()

        self.channel_description = self.update_channel_information()

        self.ip_addrs = {}
        self.ip_addrs["x"] = self.x_ip
        self.ip_addrs["y"] = self.y_ip
        self.ip_addrs["scope"] = self.scope_ip

        self.data_run = DataRunThread(
            self.hdf5_filename, self.pos_param, self.channel_description, self.ip_addrs
        )
        self.freeze_all_controls()
        self.data_run.signals.finished.connect(self.data_run_finished)
        self.data_run.signals.cancel.connect(self.acquisition_canceled)
        self.data_run.signals.updated_position.connect(
            self.update_current_position_during_data_run
        )
        self.data_run.signals.finished_position.connect(self.mark_finished_positions)
        self.data_run.signals.new_screen_dump.connect(self.update_screen_dump)
        self.threadpool.start(self.data_run)

    def acquisition_canceled(self):
        QMessageBox.about(self, "Acquisition Status", "Data acquisition cancelled.")
        self.enable_all_controls()

    def data_run_finished(self):
        QMessageBox.about(self, "Acquisition Status", "Data acquisition complete.")
        self.enable_all_controls()
        self.canvas.visited_points.remove()
        self.canvas.initialize_visited_points()
        # self.canvas.finished_x = []
        # self.canvas.finished_y = []

    def test_shot_finished(self):
        QMessageBox.about(self, "Take Test Shot", "Test shot is finished.")
        self.enable_all_controls()
        # global data_running
        # data_running = False
        # self.pc.setEnabled(True)
        # self.ac.setEnabled(True)
        # self.sc.setEnabled(True)
        # self.mm.setEnabled(True)

    def freeze_all_controls(self):
        global data_running
        data_running = True
        self.pc.setEnabled(False)
        self.ac.setEnabled(False)
        self.sc.setEnabled(False)
        self.mm.MoveButton.setEnabled(False)
        self.mm.SetZero.setEnabled(False)
        self.mm.SetVelocity.setEnabled(False)
        self.mm.velocityButton.setEnabled(False)

    def enable_all_controls(self):
        global data_running
        data_running = False
        self.pc.setEnabled(True)
        self.ac.setEnabled(True)
        self.sc.setEnabled(True)
        self.mm.MoveButton.setEnabled(True)
        self.mm.SetZero.setEnabled(True)
        self.mm.SetVelocity.setEnabled(True)
        self.mm.velocityButton.setEnabled(True)

    def start_test_shot(self):
        self.ip_addrs = {}
        self.ip_addrs["scope"] = self.scope_ip
        self.test_shot = TestShotThread(self.ip_addrs)
        self.test_shot.signals.finished.connect(self.test_shot_finished)
        self.test_shot.signals.new_screen_dump.connect(self.update_screen_dump)
        self.threadpool.start(self.test_shot)

    def fileQuit(self):
        self.close()

    def closeEvent(self, ce):
        self.fileQuit()


if __name__ == "__main__":

    app = QApplication(sys.argv)
    window = Window()
    window.show()

    sys.exit(app.exec_())
