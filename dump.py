#!/usr/bin/env python3

import sys
from usb_pdml import USBPDML
from protocol import Fragment, FragmentFeed, packet_factory

if __name__ == "__main__":
    conversation = USBPDML(sys.argv[1])
    conversation.parse_file()
    start_time = None
    index = 0
    incoming = FragmentFeed()
    outgoing = FragmentFeed()
    for msg in conversation.interaction():
        index += 1
        customstring = ""
        if (start_time == None):
            start_time = msg["time"]
        #print(comm)
        t = msg["time"] - start_time
        print("{: >8.3f} {}".format(t, conversation.stringify_msg(msg)))
        
        if "data" in msg:
            if msg["direction"] == "<":
                res = outgoing.packet(Fragment.read(bytes(msg["data"])))
                if (res):
                    print(packet_factory(res))

            if msg["direction"] == ">":
                res = incoming.packet(Fragment.read(bytes(msg["data"])))
                if (res):
                    print(packet_factory(res))
            print(Fragment.read(bytes(msg["data"])))
        if (index > 80):
            break
        print("")
