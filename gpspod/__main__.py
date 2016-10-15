
from . import protocol
from .interact import Communicator
import argparse
import time

from collections import namedtuple
Cmd = namedtuple("Cmd", ["request", "help"])


parser = argparse.ArgumentParser(description="GPS Pod: Interact with ")
parser.add_argument('--verbose', '-v', help="Print all communication.",
                    action="store_true", default=False)

subparsers = parser.add_subparsers(dest="command")


single_commands = {
    "device":Cmd(protocol.DeviceInfoRequest, "Request device info"),
    "status":Cmd(protocol.DeviceStatusRequest, "Request device status"),
    "logcount":Cmd(protocol.LogCountRequest, "Request log count"),
    "logunwind":Cmd(protocol.LogHeaderUnwindRequest, "Request header unwind"),
    "logpeek":Cmd(protocol.LogHeaderPeekRequest, "Request header peek"),
    "logstep":Cmd(protocol.LogHeaderStepRequest, "Request header step"),
    "logformat":Cmd(protocol.LogHeaderFormatRequest, "Request log format"),
}

for command in single_commands:
    spec = single_commands[command]
    sub_parser = subparsers.add_parser(command, help=spec.help)

dump_rom = subparsers.add_parser("dump", help="Make a dump of some memory")
dump_rom.add_argument('upto', type=int, help='number of blocks to retrieve')
dump_rom.add_argument('--file', type=str, help='file to write to', default="/tmp/dump.bin")

# parse the arguments.
args = parser.parse_args()

# no command
if (args.command is None):
    parser.print_help()
    parser.exit()
    sys.exit(1)

# single command.
if (args.command in single_commands):
    spec = single_commands[args.command]
    c = Communicator()
    c.connect()
    req = spec.request()
    c.write_msg(req)
    print("{:s}".format(c.read_msg()))

if (args.command == "dump"):
    c = Communicator()
    c.connect()
    p = protocol.DataRequest()
    f = open(args.file, "bw")
    for i in range(args.upto):
        p.pos(i * p.block_size)
        c.write_msg(p)
        ret_packet = c.read_msg()
        print("{:s}".format(ret_packet))
        f.write(ret_packet.content())
        time.sleep(0.05)
        
    f.close()