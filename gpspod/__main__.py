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

from collections import namedtuple
Cmd = namedtuple("Cmd", ["request", "help"])


parser = argparse.ArgumentParser(description="GPS Pod: Interact with ")
parser.add_argument('--verbose', '-v', help="Print all communication.",
                    action="store_true", default=False)

parser.add_argument('--record', help="Record usb packets to aid debugging and\
                    analysis.", default=True)

subparsers = parser.add_subparsers(dest="command")


single_commands = {
    "device":Cmd(protocol.DeviceInfoRequest, "Request device info"),
    "reset":Cmd(protocol.SendResetRequest, "Reset"),
    "settings":Cmd(protocol.ReadSettingsRequest, "Request settings"),
    "status":Cmd(protocol.DeviceStatusRequest, "Request device status"),
    "logcount":Cmd(protocol.LogCountRequest, "Request log count"),
    "logrewind":Cmd(protocol.LogHeaderRewindRequest, "Request header unwind"),
    "logpeek":Cmd(protocol.LogHeaderPeekRequest, "Request header peek"),
    "logstep":Cmd(protocol.LogHeaderStepRequest, "Request header step"),

    # logformat actually only retrieves an entry.... it is not special.
    "logentry":Cmd(protocol.LogHeaderEntryRequest, "Request a log entry"),
}

for command in single_commands:
    spec = single_commands[command]
    sub_parser = subparsers.add_parser(command, help=spec.help)

dump_rom = subparsers.add_parser("dump", help="Make a dump of some memory")
dump_rom.add_argument('-upto', type=int, default=int(0x3c0000 / 0x0200),
                      help='number of blocks to retrieve')
dump_rom.add_argument('--file', type=str, default="/tmp/dump.bin",
                      help='file to write to')


debug_interaction = subparsers.add_parser("debug_interaction",
                                 help="Print interaction from file")
debug_interaction.add_argument('file', type=str,
                                help='The file with transactions.')

debug_reconstruct_fs = subparsers.add_parser("debug_reconstruct_fs",
                                 help="Print interaction from file")
debug_reconstruct_fs.add_argument('file', type=str,
                                help='The file with transactions.')
debug_reconstruct_fs.add_argument('outfile', type=str, default=None, nargs="?",
                                help='The file with transactions.')

# parse the arguments.
args = parser.parse_args()

communicator_class = RecordingCommunicator if args.record else Communicator

# no command
if (args.command is None):
    parser.print_help()
    parser.exit()
    sys.exit(1)

if (args.command == "debug_interaction"):
    from .debug import print_interaction
    print_interaction(args.file)

if (args.command == "debug_reconstruct_fs"):
    from .debug import reconstruct_filesystem
    if (args.outfile is None):
        # print(args.file.find("."))
        # print(args.file)
        path = os.path.dirname(args.file)
        file_name = os.path.basename(args.file)
        file_name = file_name[0:file_name.find(".")] + ".binfs"
        output_file = os.path.join(path, file_name)
    else:
        output_file = args.outfile
    # print(output_file)
    reconstruct_filesystem(args.file, output_file)
    

if (args.command == "logentry"):
    spec = single_commands[args.command]
    c = communicator_class()
    c.connect()
    req = spec.request()
    c.write_msg(req)
    res = c.read_msg()
    from . import pmem
    processor = pmem.PMEMTrackEntries(None, None, None)
    print("{:s}".format(res))
    print("{:s}".format(repr(res)))
    print("{:s}".format(repr(bytes(res))))
    v = processor.process_entry(res.log_header_entry.data)
    print(v)
    sys.exit()
    
    

# single command.
if (args.command in single_commands):
    spec = single_commands[args.command]
    c = communicator_class()
    c.connect()
    req = spec.request()
    c.write_msg(req)
    print("{:s}".format(c.read_msg()))

if (args.command == "dump"):
    up_to_block = max(min(int(0x3c0000 / 0x0200), int(args.upto)), 0)
    print("Up to {:>04X} (decimal: {:>04d}).".format(up_to_block, up_to_block))
    c = communicator_class()
    c.connect()
    p = protocol.DataRequest()
    f = open(args.file, "bw")
    sequence_number = 0
    error_count = 0
    # for i in range(up_to_block):
    i = 0
    while (i < up_to_block) and (error_count < 10):
        p.pos(i * p.block_size)
        c.write_msg(p)
        ret_packet = c.read_msg()
        if (type(ret_packet) == protocol.DataReply):
            # print("Successfully retrieved {:s}".format(ret_packet))
            i += 1
            f.write(ret_packet.content())
        else:
            error_count += 1
            print("Wrong packet response: {:s}".format(ret_packet))
            print("Will retry this block: {:>0X}, current_error count: {}".format(i, error_count))
        time.sleep(0.01)
        sequence_number += 1
        
    f.close()

    c.write_json("/tmp/risntreist.json")
    c.write_json("/tmp/risntreist.json.gz")