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


import xml.etree.ElementTree as ET
import gzip
import sys

URB_TYPE_SUBMIT = 83
URB_TYPE_COMPLETED = 67

URB_STATUS_SUCCESS = 0
URB_STATUS_ESHUTDOWN = 2499805183
URB_STATUS_EINPROGRESS = 2382364671
URB_STATUS_EPIPE = 3774873599
URB_STATUS_ENOENT = 4278190079

USB_TRANSFER_INTERRUPT = 1
USB_TRANSFER_CONTROL = 2

USB_ENDPOINT_DIRECTION_IN = 1
USB_ENDPOINT_DIRECTION_OUT = 0


class USBPacket():
    data_conversion = {
        "usb.endpoint_number": lambda x: int(x, 16),
        "num": lambda x: int(x, 16),
        "len": lambda x: int(x, 16),
        "frame.time_epoch": lambda x: float(x),
        "caplen": lambda x: int(x, 16),
        "usb.transfer_type": lambda x: int(x, 16),
        "usb.urb_id": lambda x: int(x, 16),
        "usb.urb_type": lambda x: int(x, 16),
        "usb.urb_status": lambda x: int(x, 16),
        "usb.endpoint_number": lambda x: int(x, 16),
        "usb.endpoint_number.direction": lambda x: int(x),
        "usb.endpoint_number.endpoint": lambda x: int(x),
        "usb.capdata": lambda x: [
                int(c, 16) for c in [x[i:i + 2] for i in range(0, len(x), 2)]],
        "usb.bString": lambda z: "".join(
            [chr(int(c[2:4] + c[0:2], 16)) for c in
                [z[i:i+4]for i in range(0, len(z), 4)]])
    }

    def __init__(self, packet):
        self.packet = packet
        self.d = {}
        self.s = {}
        self.parse(packet)

    def assign(self, name, element):
        for f in ["value", "show"]:
            if (f in element.attrib):
                fieldname = element.attrib["name"]
                fieldvalue = element.attrib.get(f, None)
                self.d[name] = self.data_conversion[name](fieldvalue) if name\
                    in self.data_conversion else fieldvalue
                break
        if ("showname" in element.attrib):
            self.s[element.attrib["name"]] = element.attrib["showname"]

    def parse(self, element):
        for el in element:
            self.assign(el.attrib["name"], el)
            self.parse(el)

    def __getitem__(self, name):
        return self.d[name]

    def __contains__(self, item):
        return item in self.d

    def pp(self):
        k = self.d.keys()
        ks = sorted(k)
        representation = ""
        for k in ks:
            representation += " "*k.count(".") + "{}: {} ({})\n".format(
                    k, self.d[k], self.s[k] if k in self.s else "")
        return representation


class USBPDML():
    def __init__(self, path):
        self.path = path
        self.interactions = []
        self.interactions_full = {}

    def parse_file(self):
        if self.path.endswith("gz"):
            f = gzip.GzipFile(self.path)
        else:
            f = open(self.path)
        tree = ET.parse(f)
        f.close()
        root = tree.getroot()
        current_urbs = {}
        for child in root:
            p = USBPacket(child)
            urb_id = p["usb.urb_id"]
            urb_status = p["usb.urb_status"]
            urb_type = p["usb.urb_type"]
            if (urb_type == URB_TYPE_SUBMIT):
                current_urbs[urb_id] = p
            if (urb_type == URB_TYPE_COMPLETED):
                if (urb_id not in current_urbs):
                    print("Urb id not present: {:x}".format(urb_id))
                else:
                    submit = current_urbs[urb_id]
                    completed = p
                    self.usb_transaction(submit, completed)
                    del current_urbs[urb_id]

    def add_comm(self, packet):
        summary = {}
        self.interactions_full[packet["num"]] = packet
        summary["type"] = "interrupt" if packet["usb.transfer_type"]\
            == USB_TRANSFER_INTERRUPT else "control"
        summary["direction"] = "<" if packet["usb.endpoint_number.direction"]\
            == USB_ENDPOINT_DIRECTION_IN else ">"
        summary["endpoint"] = packet["usb.endpoint_number.endpoint"]
        summary["num"] = packet["num"]
        summary["time"] = packet["frame.time_epoch"]
        if "usb.capdata" in packet:
            summary["data"] = packet["usb.capdata"]
        if "usb.bString" in packet:
            summary["usb.bString"] = packet["usb.bString"]
        self.interactions.append(summary)

    def usb_transaction(self, submit, completed):
        if (completed["usb.urb_status"] != URB_STATUS_SUCCESS):
            print("Failure in USB transmission!")
        if (completed["usb.endpoint_number.direction"] ==
                USB_ENDPOINT_DIRECTION_IN):
            # the completed one is the relevant data.
            self.add_comm(completed)
        else:
            # the submit one has the relevant data.
            self.add_comm(submit)

    def interaction(self):
        return self.interactions

    def get_full(self, num):
        if (type(num) == int):
            return self.interactions_full[num]
        if (type(num) == dict):
            return self.interactions_full[num["num"]]

    def stringify_msg(self, msg):
        customstring = ""
        if ("usb.bString" in msg):
            customstring = msg["usb.bString"]
        if ("data" in msg):
            customstring = " ".join(["{:0>2X}".format(d) for d in msg["data"]])
        return "{endpoint: >2d} {direction: >1s}"\
               " {stype} {addition}".format(
                        stype=msg["type"][0:3], addition=customstring, **msg)

if __name__ == "__main__":
    conversation = USBPDML(sys.argv[1])
    conversation.parse_file()
    start_time = None
    for msg in conversation.interaction():
        customstring = ""
        if (start_time is None):
            start_time = msg["time"]
        # print(comm)
        t = msg["time"] - start_time
        print("{: >8.3f} {}".format(t, conversation.stringify_msg(msg)))
