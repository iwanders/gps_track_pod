#!/usr/bin/env python3

# The MIT License (MIT)
#
# Copyright (c) 2016 Ivor Wanders
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from . import protocol
from . import output
from . import pmem
from . import interact
from . import device
from . import debug
import argparse
import time
import datetime
import sys
import os


def get_communicator(args):
    if (args.recordfile is None):
        recordpath = time.strftime("%Y_%m_%d__%H_%M_%S.json.gz")
    else:
        recordpath = args.recordfile

    if (args.playbackfile is not None):
        entries = debug.load_json_usb(args.playbackfile)
        return interact.OfflineCommunicator(entries)

    if (args.fs is not None):
        return interact.OfflineCommunicator()

    if (args.record):
        return interact.RecordingCommunicator(recordpath)
    else:
        return interact.Communicator()


def get_device(args, communicator):
    if (args.fs is not None):
        # load it
        with open(args.fs, "rb") as f:
            fs = f.read()
    else:
        fs = None
    gps = device.GpsPod(communicator)
    gps.mount(fs)
    return gps


def run_device_info(args):
    communicator = get_communicator(args)
    with communicator:
        request = protocol.DeviceInfoRequest()
        communicator.write_msg(request)
        print(communicator.read_msg().body)


def run_device_status(args):
    communicator = get_communicator(args)
    with communicator:
        request = protocol.DeviceStatusRequest()
        communicator.write_msg(request)
        print(communicator.read_msg().body)


def run_show_tracks(args):
    communicator = get_communicator(args)
    gps = get_device(args, communicator)
    with communicator:
        gps.load_tracks()
        tracklist = gps.get_tracks()
        for i in range(len(tracklist)):
            print("{: >2d}: {}".format(i, tracklist[i].get_header()))


def run_set_sounds(args):
    request = protocol.SetSettingsRequest()
    if (args.state != ""):
        if (args.state in ["1", "true", "on"]):
            request.sounds = True
        elif (args.state in ["0", "false", "off"]):
            request.sounds = False
        else:
            print("State should be 0/1, true/false, on/off")
            sys.exit(1)
    communicator = get_communicator(args)
    with communicator:
        if (args.state != ""):
            communicator.write_msg(request)
            if (type(communicator.read_msg()) == protocol.SetSettingsReply):
                print("Sound state should be: {}".format(args.state))
            else:
                print("Wrong response recevied, probably an USB error?")
        else:
            request = protocol.ReadSettingsRequest()
            communicator.write_msg(request)
            msg = communicator.read_msg()
            res = msg.body
            print(res)


def run_settings(args):
    if (args.write):
        # alpha
        # setlogparam
        # bravo
        request = protocol.SetLogSettingsRequest()
        if (args.autostart in ["1", "true", "on"]):
            request.autostart = True
        elif (args.autostart in ["0", "false", "off"]):
            request.autostart = False
        else:
            print("Autostart should be 0/1, true/false, on/off, exiting.")
            sys.exit(1)

        if (args.autosleep not in [0, 10, 30, 60]):
            print("Autosleep should be 0, 10, 30 or 60, exiting.")
            sys.exit(1)

        if (args.interval not in [1, 60]):
            print("Interval should be 1 or 60, exiting.")
            sys.exit(1)
        if ((args.autolap < 0) or (args.autolap > 2**16)):
            print("Autolap should be in 0-65536 (perhaps 2**32? needs test.).")
            sys.exit(1)

        request.autolap = args.autolap
        request.autosleep = args.autosleep
        request.interval = args.interval

    comm = get_communicator(args)
    gps = get_device(args, comm)
    if (args.write):
        with comm:
            comm.write_msg(protocol.SetUnknownRequestAlpha())
            if (type(comm.read_msg()) != protocol.SetUnknownReplyAlpha):
                print("Wrong response in preparing to send the settings.")
                raise BaseError("Quitting, but with grace so the log is"
                                "stored.")
            comm.write_msg(request)
            if (type(comm.read_msg()) != protocol.SetLogSettingsReply):
                print("Wrong response to write settings...")
                raise BaseError("Quitting, but with grace so the log is"
                                "stored.")
            comm.write_msg(protocol.SetUnknownRequestBravo())
            if (type(comm.read_msg()) != protocol.SetUnknownReplyBravo):
                print("Wrong response in finishing settings procedure.")
                raise BaseError("Quitting, but with grace so the log is"
                                "stored.")
            print("Settings should be {}".format(request.set_settings_request))
    else:
        with comm:
            print(gps.get_settings())


def run_retrieve_tracks(args):
    communicator = get_communicator(args)
    gps = get_device(args, communicator)
    with communicator:
        gps.load_tracks()
        tracklist = gps.get_tracks()
        for i in range(len(tracklist)):
            print("{: >2d}: {}".format(i, tracklist[i].get_header()))
        if (abs(args.index >= len(tracklist))):
            print("The track index is out of range.")
            print("Valid track range is: 0-{}".format(len(tracklist)-1))
            sys.exit(1)
        track = tracklist[args.index]

        metadata = track.get_header()

        base_time = datetime.datetime(year=metadata.year,
                                      month=metadata.month,
                                      day=metadata.day,
                                      hour=metadata.hour,
                                      minute=metadata.minute,
                                      second=metadata.second)
        if (args.outfile is None):
            output_path = base_time.strftime("track_%Y_%m_%d__%H_%M_%S.gpx")
        else:
            output_path = args.outfile

        print("Retrieving track {: >2d}, of {: >4d} samples and"
              " writing to {}".format(args.index,
                                      metadata.samples,
                                      output_path))

        track.load_entries()
        samples = track.get_entries()
        # for s in samples:
        #    print(s)

        print("Acquired the data, writing gpx.".format(len(samples)))
        lap_split = not args.no_lap_splits_segment
        add_wpt = not args.no_lap_adds_wpt
        all_points = not args.no_write_points
        print("Lap adds waypoint: {}, lap splits segments: {}, all points:"\
              " {}.".format(add_wpt, lap_split, all_points))

        logwriter = output.GPSWriter(samples, metadata=metadata,
                                     lap_splits_segment=lap_split,
                                     lap_adds_wpt=add_wpt,
                                     write_points=all_points)
        text = logwriter.create_xml()

        with open(output_path, "wb") as f:
            f.write(text)

        print("Done creating gpx, wrote {} bytes to {}.".format(len(text),
              output_path))


def run_dump_fs(args):
    communicator = get_communicator(args)
    gps = get_device(args, communicator)
    with communicator:
        data = gps[0:pmem.FILESYSTEM_SIZE]

    with open(args.file, "bw") as f:
        f.write(data)


def run_debug_reconstruct_fs(args):
    from .debug import reconstruct_filesystem
    if (args.outfile is None):
        path = os.path.dirname(args.file)
        file_name = os.path.basename(args.file)
        file_name = file_name[0:file_name.find(".")] + ".binfs"
        output_file = os.path.join(path, file_name)
    else:
        output_file = args.outfile
    # print(output_file)
    reconstruct_filesystem(args.file, output_file)


def run_debug_view_messages(args):
    from .debug import print_interaction
    print_interaction(args.file)


def run_debug_internallog(args):
    communicator = get_communicator(args)
    gps = get_device(args, communicator)
    with communicator:
        gps.load_debug_logs()
        logs = gps.get_debug_logs()
        for log in logs:
            log.load_entries()
            for m in log.get_entries():
                print(m)

# argument parsing
parser = argparse.ArgumentParser(
            description="GPS Pod: Interact with SUUNTO's GPS Track Pod."
                                )

parser.add_argument('--record', help="Record usb packets to aid debugging and\
                    analysis.", default=False)

parser.add_argument('--recordfile', help="Default file to record to"
                    " (%%Y_%%m_%%d__%%H_%%M_%%S.json.gz).",
                    default=None)

parser.add_argument('--playbackfile', help="Play transactions from this file.",
                    default=None)

parser.add_argument('--fs', help="Specify a filesystem file to use.",
                    default=None)

subparsers = parser.add_subparsers(dest="command")


device_info = subparsers.add_parser("info", help="Print device info.")
device_info.set_defaults(func=run_device_info)
device_status = subparsers.add_parser("status", help="Print device status.")
device_status.set_defaults(func=run_device_status)

show_tracks = subparsers.add_parser("tracks", help="Show available tracks.")
show_tracks.set_defaults(func=run_show_tracks)

retrieve_tracks = subparsers.add_parser("retrieve", help="Retrieve a track.",
                    epilog="A lap event is either caused by the autolap value"\
                           " or by the user pressing the button once.")
retrieve_tracks.add_argument('index', type=int,
                             help='The index of the track to download.')
retrieve_tracks.add_argument('outfile', type=str, default=None, nargs="?",
                             help='The output file for FS, defaults to: '
                             'track_%%Y_%%m_%%d__%%H_%%M_%%S.gpx.')
retrieve_tracks.add_argument('--no-lap-splits-segment', default=False,
                             action="store_true",
                             help='Do not split the segments on a lap event.')
retrieve_tracks.add_argument('--no-lap-adds-wpt', default=False,
                             action="store_true",
                             help='Do not add a wpt entry for a lap event.')
retrieve_tracks.add_argument('--no-write-points', default=False,
                             action="store_true",
                             help='Do not write all points, only lap events.')

retrieve_tracks.set_defaults(func=run_retrieve_tracks)

set_sounds = subparsers.add_parser("sounds", help="Enable or disable sounds. "
                                   "Call without arguments to show the current"
                                   " sound state.")
set_sounds.add_argument('state', type=str, default="", nargs="?",
                        help='0/1, true/false, on/off...')
set_sounds.set_defaults(func=run_set_sounds)


settings = subparsers.add_parser("settings",
                                 help="Sets the logging parameters. "
                                 "Call without arguments to show the current"
                                 " logging parameters.")
settings.add_argument('--write', default=False, action="store_true",
                      help="Write settings instead of showing them.")
settings.add_argument('--autolap', type=int, default=0,
                      help='Autolap distance in meters. (default: 0)')
settings.add_argument('--autostart', type=str, default="on",
                      help='Autostart logging after fix if (default: on)')
settings.add_argument('--autosleep', type=int, default=0,
                      help='Sleep after 10/30/60 minute idle (default: 0)')
settings.add_argument('--interval', type=int, default=1,
                      help='Set the logging interval 1s/60s (default: 1)')
settings.set_defaults(func=run_settings)

retrieve_fs = subparsers.add_parser(
                        "dump",
                        help="Dump all bytes from the filesystem to a file.")
retrieve_fs.add_argument('file',
                         type=str,
                         help='The file to write to.')
retrieve_fs.set_defaults(func=run_dump_fs)


# create subparser for debug
debug_command = subparsers.add_parser("debug", help="Various debug tools.")

debug_subcommand = debug_command.add_subparsers(dest="subcommand")

debug_view_messages = debug_subcommand.add_parser(
                        "view", help="Show messages stored in an file that "
                        "contains USB messages, either an PDML from wireshark "
                        "or a recording from this tool with --record.")
debug_view_messages.add_argument('file', type=str,
                                 help='The file with USB interaction.')
debug_view_messages.set_defaults(func=run_debug_view_messages)


debug_reconstruct_fs = debug_subcommand.add_parser(
                        "reconstruct",
                        help="Reconstruct filesystem from interaction.")
debug_reconstruct_fs.add_argument('file',
                                  type=str,
                                  help='The file with transactions.')
debug_reconstruct_fs.add_argument(
                    'outfile', type=str, default=None, nargs="?",
                    help='The output file for FS, defaults to: '
                    'INPUTFILE.binfs')
debug_reconstruct_fs.set_defaults(func=run_debug_reconstruct_fs)

debug_internallog = debug_subcommand.add_parser(
                        "internallog",
                        help="Print the internal diagnostics log kept on the "
                        "GPS, info such as time to fix, battery voltage, etc.")
debug_internallog.set_defaults(func=run_debug_internallog)

# debug_dev_func = debug_subcommand.add_parser("test")
# debug_dev_func.set_defaults(func=run_debug_dev_func)

args = parser.parse_args()

# parse the arguments.


# no command
if (args.command is None):
    parser.print_help()
    parser.exit()
    sys.exit(1)

# debug and no command.
if (args.command == "debug"):
    if (args.subcommand is None):
        debug_command.print_help()
        debug_command.exit()
        sys.exit(1)


args.func(args)
sys.exit()
