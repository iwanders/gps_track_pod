#!/usr/bin/env python3

import sys
from usb_pdml import USBPDML
from protocol import USBPacket, USBPacketFeed, Packet, load_packet

if __name__ == "__main__":
    conversation = USBPDML(sys.argv[1])
    conversation.parse_file()
    start_time = None
    index = 0
    incoming = USBPacketFeed()
    outgoing = USBPacketFeed()
    incoming_command_dirs = {}
    outgoing_command_dirs = {}
    for msg in conversation.interaction():
        index += 1
        customstring = ""
        if (start_time == None):
            start_time = msg["time"]
        #print(comm)
        t = msg["time"] - start_time
        print("{: >8.3f} {}".format(t, conversation.stringify_msg(msg)))
        
        if "data" in msg:
            usb_packet = USBPacket.read(bytes(msg["data"]))
            if msg["direction"] == ">":
                res = outgoing.packet(usb_packet)
                if (res):
                    packet = load_packet(res)
                    print(packet)
                    command_dir = (packet.command.command, packet.command.direction)
                    if (not command_dir in outgoing_command_dirs):
                        outgoing_command_dirs[command_dir] = 0
                    outgoing_command_dirs[command_dir] += 1

            if msg["direction"] == "<":
                res = incoming.packet(usb_packet)
                if (res):
                    packet = load_packet(res)
                    print(packet)
                    command_dir = (packet.command.command, packet.command.direction)
                    if (not command_dir in incoming_command_dirs):
                        incoming_command_dirs[command_dir] = 0
                    incoming_command_dirs[command_dir] += 1
            #print(usb_packet)
        print("#{:0>5d}".format(index))
        if (index > 80):
            break
    print("outgoing:")
    print("\n".join([str(a) for a in outgoing_command_dirs.items()]))
    print("Incoming")
    print("\n".join([str(a) for a in incoming_command_dirs.items()]))

