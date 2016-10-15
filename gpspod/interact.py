#!/usr/bin/env python3

from . import protocol
import usb
import usb.util
import sys
import time


class Communicator():
    def __init__(self):
        self.dev = None
        self.incoming = protocol.USBPacketFeed()

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
        packets = protocol.usbpacketizer(msg)
        for p in packets:
            write_res = self.dev.write(0x02, bytes(p), timeout=100)

    def read_msg(self, timeout=100):
        start = time.time()
        while (start + timeout / 1000.0) > time.time():
            res = self.dev.read(0x82, 64, timeout=100)
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

