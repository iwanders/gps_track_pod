
from . import protocol
from .interact import Communicator
import argparse


parser = argparse.ArgumentParser(description="GPS Pod: Interact with ")
parser.add_argument('--verbose', '-v', help="Print all communication.",
                    action="store_true", default=False)

subparsers = parser.add_subparsers(dest="command")


command_parser = subparsers.add_parser("device", help = "Request device info")

# parse the arguments.
args = parser.parse_args()

# no command
if (args.command is None):
    parser.print_help()
    parser.exit()
    sys.exit(1)


if (args.command == "device"):
    req = protocol.DeviceInfoRequest()
    c = Communicator()
    c.connect()
    c.write_msg(req)
    print("{:s}".format(c.read_msg()))
