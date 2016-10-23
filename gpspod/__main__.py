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
    "logformat":Cmd(protocol.LogHeaderFormatRequest, "Request log format"),
}

for command in single_commands:
    spec = single_commands[command]
    sub_parser = subparsers.add_parser(command, help=spec.help)

dump_rom = subparsers.add_parser("dump", help="Make a dump of some memory")
dump_rom.add_argument('-upto', type=int, default=int(0x3c0000 / 0x0200),
                      help='number of blocks to retrieve')
dump_rom.add_argument('--file', type=str, default="/tmp/dump.bin",
                      help='file to write to')

# parse the arguments.
args = parser.parse_args()

communicator_class = RecordingCommunicator if args.record else Communicator

# no command
if (args.command is None):
    parser.print_help()
    parser.exit()
    sys.exit(1)

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