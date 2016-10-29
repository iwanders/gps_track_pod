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

from . import pmem
from . import protocol
import usb
import time
import struct


class GpsPod:
    def __init__(self, communicator, inter_packet_delay=0.01):
        self.fs = bytearray(pmem.FILESYSTEM_SIZE)
        self.retrieved_fs = bytearray(pmem.FILESYSTEM_SIZE)
        self.com = communicator
        self.memfs = None
        self.data = None
        self.inter_packet_delay = inter_packet_delay

        self.tracks = []
        self.debug_logs = []

    def communicate(self, msg, expected_reply, retry_count=10):
        error_count = 0
        while (error_count < retry_count):
            try:
                self.com.write_msg(msg)
                ret_packet = self.com.read_msg()
                if (type(ret_packet) == expected_reply):
                    return ret_packet
                else:
                    error_count += 1
                time.sleep(self.inter_packet_delay)
            except usb.core.USBError:
                time.sleep(self.inter_packet_delay)
        return False

    def transfer_block(self, block_index):
        p = protocol.DataRequest()
        p.pos(block_index * p.block_size)
        ret_packet = self.communicate(p, protocol.DataReply)
        if (ret_packet):
            # load the data
            pos = ret_packet.position()
            length = ret_packet.length()
            self.fs[pos:pos+length] = ret_packet.content()
            ones = bytes([1 for i in range(length)])
            self.retrieved_fs[pos:pos+length] = bytes(ones)
            return True
        else:
            print("Failed retrieving block: {:>0X}".format(block_index))
            return False

    def have_data(self, key):
        if (sum(self.retrieved_fs[key]) == (key.stop - key.start)):
            return True
        # otherwise, we have to get it.
        block_size = protocol.DataRequest.block_size
        block_start = int(key.start / block_size)
        block_end = min(int((key.stop + block_size) / block_size),
                        int(pmem.FILESYSTEM_SIZE/block_size))

        for i in range(block_start, block_end):
            if (not self.transfer_block(i)):
                return False
        return True

    def __getitem__(self, key):
        if self.have_data(key):
            return self.fs[key]
        else:
            # TODO: Use a proper error?
            raise IndexError("Could not get data")

    def mount(self, fs=None):
        if (fs is None):
            self.memfs = pmem.MEMfs(self)
            self.data = pmem.BPMEMfile(self.memfs)
        else:
            # assume it is a complete filesystem.
            self.retrieved_fs = bytes([1 for i in range(pmem.FILESYSTEM_SIZE)])
            self.memfs = pmem.MEMfs(fs)
            self.data = pmem.BPMEMfile(self.memfs)

    def load_tracks(self):
        self.data.tracks.load_block_header()
        self.data.tracks.load_logs()
        # print(" ".join([str(l) for l in self.data.tracks.logs]))

        for track in self.data.tracks.logs:
            if track.load_header():
                self.tracks.append(track)

    def get_tracks(self):
        return self.tracks

    def load_debug_logs(self):
        self.data.logs.load_block_header()
        self.data.logs.load_logs()
        for log in self.data.logs.logs:
            if log.load_header():
                self.debug_logs.append(log)

    def get_debug_logs(self):
        return self.debug_logs

    def get_settings(self):
        # We know that the settings data is at 0x2000 in the file...
        # Use that to return a message of the correct size.
        settings_type = protocol.BodySetLogSettingsRequest
        setting = self.data[0x2000:0x2000 + settings_type.settings_true_size]
        return settings_type.load_settings(setting)

    def get_sgee_timestamp(self):
        request = protocol.ReadSGEEDateRequest()
        res = self.communicate(request, protocol.ReadSGEEDateReply)
        return res

    def write_sgee(self, data):
        # EE data in pmem starts at 0x704e0, but we do not really need that
        # information. Just good to know.

        current_timestamp = self.get_sgee_timestamp().body
        # The endianness is different in the data, so we reorder the bytes.
        # Also add a 0x01 byte at begin to match with the returned message.
        databytes = bytes([1]) + data[7:5:-1] + bytes([data[8]]) + \
            bytes([data[9]]) + data[13:9:-1]
        sgeedate = protocol.BodySGEEDate.read(databytes)

        if (databytes == bytes(current_timestamp)):
            print("SGEE timestamp in device is already at {}.".format(
                  sgeedate))
            return True

        print("Old SGEE timestamp was {}.".format(current_timestamp))
        print("Writing SGEE data with timestamp {}.".format(sgeedate))

        # At begin is length as uint32_t, NOT including the length field.
        d = struct.pack("<I", len(data)) + data
        chunk_size = 512  # maximum bytes per transaction.
        chunked = [d[i:i + chunk_size] for i in range(0, len(d), chunk_size)]
        index = 0
        for block in chunked:
            msg = protocol.WriteSGEEDataRequest()
            msg.data_reply.position = chunk_size * index
            msg.data_reply.length = len(block)
            msg.load_payload(block)
            ret_packet = self.communicate(msg, protocol.WriteSGEEDataReply)
            if (not ret_packet):
                return False
            index += 1
        # send unknown request delta.
        msg = protocol.SetUnknownRequestDelta()
        ret_packet = self.communicate(msg, protocol.SetUnknownReplyDelta)
        if (not ret_packet):
            return False
        return True
