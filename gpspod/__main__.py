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
from .interact import Communicator, RecordingCommunicator
import argparse
import time
import sys
import os


def get_communicator(args):
    if (args.recordfile is None):
        recordpath = time.strftime("%Y_%m_%d_%H_%M_%S.json.gz")
    else:
        recordpath = args.recordfile
    if (args.record):
        return RecordingCommunicator(recordpath)
    else:
        return Communicator()


def run_device_info(args):
    communicator = get_communicator(args)
    with communicator:
        request = protocol.DeviceInfoRequest()
        communicator.write_msg(request)


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
    up_to_block = max(min(int(0x3c0000 / 0x0200), int(args.upto)), 0)
    with communicator:
        p = protocol.DataRequest()
        f = open(args.file, "bw")
        sequence_number = 0
        error_count = 0
        i = 0
        while (i < up_to_block) and (error_count < 10):
            sys.stdout.write(
                "Retrieve: 0x{:0>8X}/0x{:0>8X}\r".format(
                        i*p.block_size, up_to_block*p.block_size))
            sys.stdout.flush()
            p.pos(i * p.block_size)
            communicator.write_msg(p)
            ret_packet = communicator.read_msg()
            if (type(ret_packet) == protocol.DataReply):
                i += 1
                f.write(ret_packet.content())
            else:
                error_count += 1
                print("Wrong packet response: {:s}".format(ret_packet))
                print("Will retry this block: {:>0X}"
                      ", current_error count: {}".format(i, error_count))
            time.sleep(0.01)
            sequence_number += 1

        f.close()

# argument parsing
parser = argparse.ArgumentParser(description="GPS Pod: Interact with ")
parser.add_argument('--verbose', '-v', help="Print all communication.",
                    action="store_true", default=False)
parser.add_argument('--record', help="Record usb packets to aid debugging and\
                    analysis.", default=True)
parser.add_argument('--recordfile', help="Default file to record to"
                    " (%%Y_%%m_%%d_%%H_%%M_%%S.json.gz)",
                    default=None)

subparsers = parser.add_subparsers(dest="command")


device_info = subparsers.add_parser("info", help="Print device info")
device_info.set_defaults(func=run_device_info)


"""
dump_rom = subparsers.add_parser("dump", help="Make a dump of some memory")
dump_rom.add_argument('-upto', type=int, default=int(0x3c0000 / 0x0200),
                      help='number of blocks to retrieve')
dump_rom.add_argument('--file', type=str, default="/tmp/dump.binfs",
                      help='file to write to')
"""


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
