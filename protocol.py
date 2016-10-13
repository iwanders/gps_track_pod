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

import ctypes
import struct
from collections import namedtuple
import crcmod

PACKET_SIZE = 128

#############################################################################
# Mixins & structures
#############################################################################
# Convenience mixin to allow construction of struct from a byte like object.
class Readable:
    @classmethod
    def read(cls, byte_object):
        a = cls()
        ctypes.memmove(ctypes.addressof(a), bytes(byte_object),
                       min(len(byte_object), ctypes.sizeof(cls)))
        return a


# Mixin to allow conversion of a ctypes structure to and from a dictionary.
class Dictionary:
    # Implement the iterator method such that dict(...) results in the correct
    # dictionary.
    def __iter__(self):
        for k, t in self._fields_:
            if (issubclass(t, ctypes.Structure)):
                yield (k, dict(getattr(self, k)))
            else:
                yield (k, getattr(self, k))

    # Implement the reverse method, with some special handling for dict's and
    # lists.
    def from_dict(self, dict_object):
        for k, t in self._fields_:
            set_value = dict_object[k]
            if (isinstance(set_value, dict)):
                v = t()
                v.from_dict(set_value)
                setattr(self, k, v)
            elif (isinstance(set_value, list)):
                v = getattr(self, k)
                for j in range(0, len(set_value)):
                    v[j] = set_value[j]
                setattr(self, k, v)
            else:
                setattr(self, k, set_value)

    def __str__(self):
        return str(dict(self))


#############################################################################

crc_proto = crcmod.mkCrcFun(poly=0x11021, initCrc=0xFFFF, rev=False, xorOut=0)

# Structs for the various parts in the firmware. These correspond to
# the structures as defined in the header files.
class PacketHeader(ctypes.LittleEndianStructure, Dictionary):
    _pack_ = 1
    # https://github.com/openambitproject/openambit/blob/master/src/libambit/protocol.c#L41
    _fields_ = [("magic", ctypes.c_uint8),
                ("usb_length", ctypes.c_uint8),
                ("message_part", ctypes.c_uint8),
                ("message_length", ctypes.c_uint8),
                ("sequence", ctypes.c_uint16),
                ("header_checksum", ctypes.c_uint16)]

    def is_correct(self):
        header_bytes = bytes(self)[2:-2]
        calc_crc = crc_proto(header_bytes)
        return (calc_crc == self.header_checksum) and \
                (self.usb_length == self.message_length + 8) and \
                (self.magic == 0x3f)

    def is_first(self):
        return self.message_part == 0x5D # first part in sequence

    def get_part_counter(self):
        return self.sequence

    def __str__(self):
        is_ok = self.is_correct()
        if (is_ok):
            if (self.is_first()):
                return "start({: >1d}) len: {: >3d}".format(self.get_part_counter(), self.message_length)
            else:
                return "part({: >1d}) len: {: >3d}".format(self.get_part_counter(),  self.message_length)
        else:
            return "damaged header"




#############################################################################


# Class which represents all messages. That is; it holds all the structs.
class Fragment(ctypes.LittleEndianStructure, Readable):
    _pack_ = 1
    _fields_ = [("header", PacketHeader),
                ("payload", ctypes.c_uint8 * (PACKET_SIZE-ctypes.sizeof(PacketHeader)))]

    # Pretty print the message according to its type.
    def __str__(self):
        message_field = str(self.header)
        return "<Fragment {}: data({})>".format(message_field, len(self.data))

    # We have to treat the mixin slightly different here, since we there is
    # special handling for the message type and thus the body.
    def __iter__(self):
        for k, t in self._fields_:
            if (k == "payload"):
                message_field = "payload"
                body = [a for a in getattr(self, message_field)]
                yield (message_field, body)
            elif (issubclass(t, ctypes.Structure)):
                yield (k, dict(getattr(self, k)))
            else:
                yield (k, getattr(self, k))

    def from_dict(self, dict_object):
        # Walk through the dictionary, as we do not know which elements from
        # the struct we would need.
        for k, set_value in dict_object.items():
            if (isinstance(set_value, dict)):
                v = getattr(self, k)
                v.from_dict(set_value)
                setattr(self, k, v)
            elif (isinstance(set_value, list)):
                v = getattr(self, k)
                for j in range(0, len(set_value)):
                    v[j] = set_value[j]
                setattr(self, k, v)
            else:
                setattr(self, k, set_value)
    @property
    def data(self):
        data_len = self.header.message_length
        data = self.payload[0:data_len]
        crc_val, = struct.unpack("<H", bytes(self.payload[data_len:data_len+2]))
        crc_calcd = crc_proto(bytes(data), crc=self.header.header_checksum)
        if (crc_val == crc_calcd):
            return data
        else:
            return None

    @data.setter
    def data(self, value):
        print("setting: {}".format(value))

class FragmentFeed:
    def __init__(self):
        self.fragments = []

    def packet(self, fragment):
        if (fragment.header.is_first()):
            # this is the first fragment of a packet.
            if ((len(self.fragments) != 0)):
                # problem right there, we already have fragments.
                print("Detected new packet while old packet isn't finished.")
                self.fragments = []


            self.fragments.append(fragment)
        else:
            # this is not the first, so we append it, check sequence number, and if finished return.
            self.fragments.append(fragment)


        # we have the right number of fragments, create the packet data and return.
        if (len(self.fragments) == self.fragments[0].header.get_part_counter()):
            # packet is finished!
            packet_data = []
            for j in self.fragments:
                if (j.data):
                    packet_data += j.data
                else:
                    print("Checksum failed, discarding data")
                    self.fragments = []
                    return None
            self.fragments = []
            return packet_data

        if (len(self.fragments) >= 2):
            if (fragment.header.get_part_counter() + 1 != len(self.fragments)):
                print("Sequence number not matching")
                self.fragments = []
                return None
            



class Command(ctypes.LittleEndianStructure, Dictionary):
    _pack_ = 1
    _fields_ = [
        ("command", ctypes.c_uint16),
        ("direction", ctypes.c_uint16),
        ("format", ctypes.c_uint16),
        ("packet_sequence", ctypes.c_uint16),
        ("packet_length", ctypes.c_uint32)
    ]
    def __str__(self):
        return "cmd 0x{:0>4X}, fmt 0x{:0>2X}, seq 0x{:0>2X}, len {:0>2d}".format(self.command, self.format, self.packet_sequence, self.packet_length)

class Packet(ctypes.LittleEndianStructure, Readable):
    def __str__(self):
        return "<Packet cmd: {:4>0X}, seq: {:3>0d}, len: {:3>0d}, {}, {}>".format(self.command.command, self.command.packet_sequence, self.command.packet_length, self.packet_length, [hex(a) for a in self.payload])

def packet_factory(byte_object):
    packet_payload_length = len(byte_object)-ctypes.sizeof(Command)
    class Packet_(Packet):
        _pack_ = 1
        packet_length = packet_payload_length
        _fields_ = [("command", Command),
                    ("payload", ctypes.c_uint8 * packet_payload_length)]
    a = Packet_()
    ctypes.memmove(ctypes.addressof(a), bytes(byte_object),
                   min(len(byte_object), ctypes.sizeof(Packet_)))
    return a
    

