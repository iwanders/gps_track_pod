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

# to export the communication
import json
import gzip
import base64


class Communicator():
    write_endpoint = 0x02
    read_endpoint = 0x82
    usb_packetlength = 64

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

        # clean up any packets left in the delivery queue...
        res = True
        while(res):
            try:
                res = self.dev.read(self.read_endpoint, self.usb_packetlength)
            except usb.core.USBError:
                break

    def close(self):
        cfg = self.dev.get_active_configuration()
        intf = cfg[(0, 0)]
        usb.util.release_interface(self.dev, intf)

    def print_device(self):
        cfg = self.dev.get_active_configuration()
        intf = cfg[(0, 0)]

    def write_msg(self, msg):
        msg.command.packet_sequence = self.sequence_number
        self.sequence_number += 1
        # create the necessary USB packets and write these to the device.
        packets = protocol.usbpacketizer(msg)
        for p in packets:
            self.write_packet(p)

    def read_msg(self, timeout=1000):
        start = time.time()
        while (start + timeout / 1000.0) > time.time():
            res = self.read_packet()
            msg_res = self.incoming.packet(protocol.USBPacket.read(res))
            if msg_res:
                return protocol.load_msg(msg_res)
        return None

    def write_packet(self, packet):
        write_res = self.dev.write(self.write_endpoint, bytes(packet))
        return write_res

    def read_packet(self):
        res = self.dev.read(self.read_endpoint, self.usb_packetlength)
        return res

    def __enter__(self):
        self.connect()
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class RecordingCommunicator(Communicator):
    def __init__(self, path=None):
        self.save_path = path
        self.incoming_packets = []
        self.outgoing_packets = []
        super().__init__()

    def write_packet(self, packet):
        self.outgoing_packets.append((time.time(), bytes(packet)))
        return super().write_packet(packet)

    def read_packet(self):
        read_res = super().read_packet()
        if (read_res):
            self.incoming_packets.append((time.time(), bytes(read_res)))
        return read_res

    def transactions(self):
        incoming_processed = []
        outgoing_processed = []
        for t, v in self.incoming_packets:
            incoming_processed.append((t, base64.b64encode(v).decode('ascii')))
        for t, v in self.outgoing_packets:
            outgoing_processed.append((t, base64.b64encode(v).decode('ascii')))
        return {"incoming": incoming_processed, "outgoing": outgoing_processed}

    def write_json(self, path=None):
        if (path is None):
            path = self.save_path
        if (path is not None):
            opener = gzip.open if path.endswith(".gz") else open
            with opener(path, "wt") as f:
                json.dump(self.transactions(), f)

    def __exit__(self, *args, **kwargs):
        self.write_json()
        return super().__exit__(*args, **kwargs)

# this one should be able to use a transaction log...
class OfflineCommunicator(Communicator):
    def write_packet(self, packet):
        return True

    def read_packet(self):
        return b''

    def connect(self):
        pass

    def close(self):
        pass




if __name__ == "__main__":
    req = protocol.DeviceInfoRequest()
    c = Communicator()
    c.connect()
    c.write_msg(req)
    print("{:s}".format(c.read_msg()))
