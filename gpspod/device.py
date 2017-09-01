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

    def recovered_track(self):
        self.data.tracks.load_block_header()
        self.data.tracks.load_logs()
        for track in self.data.tracks.logs:
            if track.load_header():
                self.tracks.append(track)

        # the relevant data is ALWAYS after the last existing track.
        # we use this last track, we assume the recovered one is made using the
        # same settings which is a valid assumption, since changing the config
        # requires a USB connection, which means the tracks should've been
        # retrieved.
        rtrack = self.tracks[-1]  # recover track
        print("Retrieving track prior to the recoverables.")
        print(rtrack.periodic_structure)
        print(dict(rtrack.header_metadata))
        start_time = time.time()
        track.load_entries()
        samples = track.get_entries()
        end_time = time.time()
        print("Track prior retrieved in {:.1f}s, with {} entries".format(
              end_time - start_time, len(samples)))
        empty_start = rtrack.pos  # recover from here.

        def is_parsed_sane(parsed):
            """
                This function can check if a parsed entry makes sense.
            """
            if (parsed == None):
                return True

            if (hasattr(parsed, "_fields_")):
                return bool(parsed._fields_)

            data = dict(parsed)
            if "gpsheading" in data:
                # heading < 2 * pi:
                return abs(data["gpsheading"]["value"]) < 7
            if "time" in data:
                return data["time"]["value"] >= 0.0
            if "local" in data:
                return data["local"]["month"] < 13
            if (isinstance(parsed, pmem.DistanceSourceField)):
                return True
            if (data == {}):
                return True
            return False

        def check_packet_tail(rtrack, offset, to_check):
            """
                This tries to read to_check entries from rtrack at offset.
                interprets the entries and determines if they are valid. It
                calls itself until to_check is equal to zero, at which point it
                returns True.
                Basically this checks if there are to_check valid entries after
                offset.
            """
            if (to_check == 0):
                return True
            len1, data1 = rtrack.peek_entry(offset)
            # only bother if the type is < 256
            if (0 <= len1 < 256):
                try:
                    entry1 = rtrack.process_entry(data1)
                except struct.error as e:
                    return False

                if not is_parsed_sane(entry1):
                    return False
                # All good, check if the remainder of packets to be checked is
                # good as well.
                return check_packet_tail(rtrack, offset + len1 + 2, to_check - 1)
            else:
                return False

        found_offset = False
        print("Attempting to align to recoverable data.")
        # At first, we have to align position to samples. We do this by peeking
        # at samples, checking if the values are sane, if they are not, we
        # advance the look position by one.
        # We look max 2**16 bytes ahead, this is the maximum length an entry
        # can be.
        for offset in range(0, 2**16):
            # search for 10 valid consecutive packets
            if (check_packet_tail(rtrack, empty_start + offset, 10)):
                found_offset = True
                break

        if (not found_offset):
            print("Failed to align with data, recovery failed :(")
            return None
        else:
            print("Successfully aligned with data, offset: 0x{:X}".format(
                  offset))

        # Now, it is time to start eating entries from the void.
        rtrack.entries = []
        rtrack.pos = empty_start + offset
        rtrack.header_metadata.samples = 0
        rtrack.retrieved_entry_count = 0
        prior_size = len(rtrack.entries)

        for i in range(0, 1000000):
            # peek into this entry
            peek_length, peek_data = rtrack.peek_entry(rtrack.pos)
            #print("0x{:0>8X} l1: {: >8d}, data1[0]: {} ".format(rtrack.pos,
            #      peek_length,
            #      " ".join(["{:0>2X}".format(x) for x in peek_data])))

            if (peek_length):
                parsed = rtrack.process_entry(peek_data)
            else:
                continue

            # determine if it is a valid gps entry.
            if (is_parsed_sane(parsed) and peek_length):
                # it is a valid entry, increase the number of samples that are
                # known to be in this block
                rtrack.header_metadata.samples += 1
                # load all the entries, this loads up till retrieved_entry_count
                # equals the header metadata samples. Basically in this case
                # it loads just one entry!
                rtrack.load_entries()
            else:
                print("This entry did not look sane, calling it a day!")
                break

        print("Retrieved {} entries.".format(rtrack.retrieved_entry_count))
        if (rtrack.retrieved_entry_count != 0):
            return rtrack
        else:
            return None

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
