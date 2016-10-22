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
import usb
import usb.util
import sys
import time


class Communicator():
    def __init__(self):
        self.dev = None
        self.incoming = protocol.USBPacketFeed()
        self.sequence_number = 0

    def connect(self):
        # Bus 003 Device 008: ID 1493:0020 Suunto
        self.dev = usb.core.find(idVendor=0x1493, idProduct=0x0020)

        # was it found?
        if self.dev is None:
            raise ValueError('Device not found')

        # set the active configuration. With no arguments, the first
        # configuration will be the active one
        # dev.set_configuration()
        # get an endpoint instance
        for interface in self.dev.get_active_configuration():
            if self.dev.is_kernel_driver_active(interface.bInterfaceNumber):
                self.dev.detach_kernel_driver(interface.bInterfaceNumber)
                usb.util.claim_interface(self.dev, interface.bInterfaceNumber)

        # set the active configuration. With no arguments, the first
        # configuration will be the active one
        self.dev.set_configuration()
        res = True
        while(res):
            try:
                res = self.dev.read(0x82, 64)
            except usb.core.USBError:
                break

    def close(self):
        cfg = self.dev.get_active_configuration()
        intf = cfg[(0, 0)]
        usb.util.release_interface(self.dev, intf)

    def print_device(self):
        cfg = self.dev.get_active_configuration()
        intf = cfg[(0, 0)]
        print("print cfg")
        print(cfg)
        print("print intf")
        print(intf)

    def write_msg(self, msg):
        msg.command.packet_sequence = self.sequence_number
        self.sequence_number += 1
        packets = protocol.usbpacketizer(msg)
        for p in packets:
            write_res = self.dev.write(0x02, bytes(p))

    def read_msg(self, timeout=1000):
        start = time.time()
        while (start + timeout / 1000.0) > time.time():
            res = self.dev.read(0x82, 64)
            msg_res = self.incoming.packet(protocol.USBPacket.read(res))
            if msg_res:
                return protocol.load_msg(msg_res)
        return None


if __name__ == "__main__":
    req = protocol.DeviceInfoRequest()
    c = Communicator()
    c.connect()
    c.write_msg(req)
    print("{:s}".format(c.read_msg()))

