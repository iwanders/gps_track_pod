#!/usr/bin/env python3

import xml.etree.ElementTree as ET
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
        "caplen": lambda x: int(x, 16),
        "usb.transfer_type": lambda x: int(x,16),
        "usb.urb_id": lambda x: int(x,16),
        "usb.urb_type": lambda x: int(x,16),
        "usb.urb_status": lambda x: int(x,16),
        "usb.endpoint_number": lambda x: int(x,16),
        "usb.endpoint_number.direction": lambda x: int(x),
        "usb.endpoint_number.endpoint": lambda x: int(x),
        "usb.capdata": lambda x: [int(c,16) for c in [x[i:i + 2] for i in range(0, len(x), 2)]],
        
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
                self.d[name] = self.data_conversion[name](fieldvalue) if name in self.data_conversion else fieldvalue
                break
        if ("showname" in element.attrib):
            self.s[element.attrib["name"]] = element.attrib["showname"]


    def parse(self, element):
        for el in element:
            self.assign(el.attrib["name"], el)
            self.parse(el)

    def __getitem__(self, name):
        return self.d[name]

    def __str__(self):
        return "<{} - {} {}>".format("INTERRUPT" if self["usb.transfer_type"] == USB_TRANSFER_INTERRUPT else "CONTROL",
                                        self["usb.endpoint_number"],
                                        "IN" if self["usb.endpoint_number.direction"] == USB_ENDPOINT_DIRECTION_IN else "OUT")

class USBPDML():
    def __init__(self, path):
        self.path = path

    def parse_file(self):
        tree = ET.parse(self.path)
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

    def usb_transaction(self, submit, completed):
        if (completed["usb.urb_status"] != URB_STATUS_SUCCESS):
            print("Failure in USB transmission!")
        if (completed["usb.endpoint_number.direction"] == USB_ENDPOINT_DIRECTION_IN):
            # the completed one is the relevant data.
            print("Incoming: {}".format(completed))
            if (completed["usb.transfer_type"] == USB_TRANSFER_CONTROL):
                print(completed.d)
        else:
            # the submit one has the relevant data.
            print("Outgoing: {}".format(submit))
        # print(submit)
        # print(completed)
        print("\n"*4)

if __name__ == "__main__":
    conversation = USBPDML(sys.argv[1])
    conversation.parse_file()
