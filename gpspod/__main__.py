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
        recordpath = time.strftime("%Y_%m_%d_%H_%M_%S.json.gz")
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


def run_debug_dev_func(args):
    communicator = get_communicator(args)
    gps = get_device(args, communicator)
    with communicator:
        print(gps[0:100])
        gps.load_logs()


def run_show_tracks(args):
    communicator = get_communicator(args)
    gps = get_device(args, communicator)
    with communicator:
        gps.load_tracks()
        tracklist = gps.get_tracks()
        for i in range(len(tracklist)):
            print("{: >2d}: {}".format(i, tracklist[i].get_header()))


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
        text = output.create_gpx_from_log(samples, metadata=metadata)
        print("Done creating gpx, writing")

        with open(output_path, "wt") as f:
            f.write(text)


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


def run_debug_retrieve_fs(args):
    communicator = get_communicator(args)
    gps = get_device(args, communicator)
    with communicator:
        data = gps[0:pmem.FILESYSTEM_SIZE]

    with open(args.file, "bw") as f:
        f.write(data)

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
parser = argparse.ArgumentParser(description="GPS Pod: Interact with ")
parser.add_argument('--verbose', '-v', help="Print all communication.",
                    action="store_true", default=False)
parser.add_argument('--record', help="Record usb packets to aid debugging and\
                    analysis.", default=True)
parser.add_argument('--recordfile', help="Default file to record to"
                    " (%%Y_%%m_%%d_%%H_%%M_%%S.json.gz)",
                    default=None)
parser.add_argument('--playbackfile', help="Play transactions from this file",
                    default=None)

parser.add_argument('--fs', help="Specify a filesystem file to use.",
                    default=None)

subparsers = parser.add_subparsers(dest="command")


device_info = subparsers.add_parser("info", help="Print device info")
device_info.set_defaults(func=run_device_info)
device_status = subparsers.add_parser("status", help="Print device status")
device_status.set_defaults(func=run_device_status)

show_tracks = subparsers.add_parser("tracks", help="Show available tracks")
show_tracks.set_defaults(func=run_show_tracks)

retrieve_tracks = subparsers.add_parser("retrieve", help="Retrieve a track")
retrieve_tracks.add_argument('index', type=int,
                             help='The index of the track to download')
retrieve_tracks.add_argument('outfile', type=str, default=None, nargs="?",
                             help='The output file for FS, defaults to: '
                             'track_%%Y_%%m_%%d__%%H_%%M_%%S.gpx')
retrieve_tracks.set_defaults(func=run_retrieve_tracks)


# create subparser for debug
debug_command = subparsers.add_parser("debug", help="Various debug tools.")

debug_subcommand = debug_command.add_subparsers(dest="subcommand")

debug_view_messages = debug_subcommand.add_parser(
                        "view", help="Show messages in file")
debug_view_messages.add_argument('file', type=str,
                                 help='The file with usb interaction.')
debug_view_messages.set_defaults(func=run_debug_view_messages)


debug_reconstruct_fs = debug_subcommand.add_parser(
                        "reconstruct",
                        help="Reconstruct filesystem from interaction")
debug_reconstruct_fs.add_argument('file',
                                  type=str,
                                  help='The file with transactions.')
debug_reconstruct_fs.add_argument(
                    'outfile', type=str, default=None, nargs="?",
                    help='The output file for FS, defaults to: '
                    'INPUTFILE.binfs')
debug_reconstruct_fs.set_defaults(func=run_debug_reconstruct_fs)

debug_retrieve_fs = debug_subcommand.add_parser(
                        "retrieve",
                        help="Pull all bytes from the filesystem")
debug_retrieve_fs.add_argument('file',
                               type=str,
                               help='The file to write to.')
debug_retrieve_fs.add_argument('--upto', type=int, default=0x3c0000,
                               help="Retrieve up to this address (0x3c0000)")
debug_retrieve_fs.set_defaults(func=run_debug_retrieve_fs)

debug_internallog = debug_subcommand.add_parser(
                        "internallog",
                        help="print the internal log")
debug_internallog.set_defaults(func=run_debug_internallog)

debug_dev_func = debug_subcommand.add_parser("test")
debug_dev_func.set_defaults(func=run_debug_dev_func)

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
