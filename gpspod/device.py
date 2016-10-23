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


class GpsPod:
    def __init__(self, communicator):
        self.fs = bytearray(pmem.FILESYSTEM_SIZE)
        self.retrieved_fs = bytearray(pmem.FILESYSTEM_SIZE)
        self.com = communicator
        self.memfs = None
        self.data = None

    def transfer_block(self, block_index, retry_count=10):
        p = protocol.DataRequest()
        error_count = 0
        while (error_count < retry_count):
            try:
                p.pos(block_index * p.block_size)
                self.com.write_msg(p)
                ret_packet = self.com.read_msg()
                if (type(ret_packet) == protocol.DataReply):
                        pos = ret_packet.position()
                        length = ret_packet.length()
                        self.fs[pos:pos+length] = ret_packet.content()
                        ones = bytes([1 for i in range(length)])
                        self.retrieved_fs[pos:pos+length] = bytes(ones)
                        return True
                else:
                    error_count += 1
                    print("Will retry this block: {:>0X}"
                          ", current_error count: {}".format(i, error_count))
                time.sleep(0.01)
            except usb.core.USBError:
                pass
                time.sleep(0.01)
        return False

    def have_data(self, key):
        if (sum(self.retrieved_fs[key]) == (key.stop - key.start)):
            return True
        # otherwise, we have to get it.
        block_size = protocol.DataRequest.block_size
        block_start = int(key.start / block_size)
        block_end = int((key.stop + block_size) / block_size)

        for i in range(block_start, block_end):
            if (not self.transfer_block(i)):
                return False
        return True

    def __getitem__(self, key):
        if self.have_data(key):
            return self.fs[key]
        else:
            raise IndexError("Could not get data") # TODO: Use a proper error?

    def mount(self):
        self.memfs = pmem.MEMfs(self)
        self.data = pmem.BPMEMfile(self.memfs)

    def load_logs(self):
        self.data.tracks.load_block_header()
        self.data.tracks.load_logs()
        print(" ".join([str(l) for l in self.data.tracks.logs]))

        for track in self.data.tracks.logs:
            if not track.load_header():
                continue
            # track.load_entries()

        for track in self.data.tracks.logs:
            print("\n\nNew track {}".format(track.header_metadata))
