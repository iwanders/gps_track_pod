#!/usr/bin/env python3

import sys
from usb_pdml import USBPDML
from messages import Msg

if __name__ == "__main__":
    conversation = USBPDML(sys.argv[1])
    conversation.parse_file()
    start_time = None
    index = 0
    for msg in conversation.interaction():
        index += 1
        customstring = ""
        if (start_time == None):
            start_time = msg["time"]
        #print(comm)
        t = msg["time"] - start_time
        print("{: >8.3f} {}".format(t, conversation.stringify_msg(msg)))
        # if msg["direction"] == "out":
        if "data" in msg:
            print(Msg.read(bytes(msg["data"])))
        if (index > 80):
            break
