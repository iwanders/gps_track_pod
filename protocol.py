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
# Protocol specific parameters.
#############################################################################

crc_proto = crcmod.mkCrcFun(poly=0x11021, initCrc=0xFFFF, rev=False, xorOut=0)
USB_PACKET_SIZE = 128
MAX_PACKET_SIZE = 540 # maximum protocol packet size. (Split over USBPackets)


#############################################################################
# USB Packet handling.
#############################################################################
class USBPacketHeader(ctypes.LittleEndianStructure, Dictionary):
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






# Class which represents all messages. That is; it holds all the structs.
class USBPacket(ctypes.LittleEndianStructure, Readable):
    _pack_ = 1
    _fields_ = [("header", USBPacketHeader),
                ("payload", ctypes.c_uint8 * (USB_PACKET_SIZE-ctypes.sizeof(USBPacketHeader)))]

    # Pretty print the message according to its type.
    def __str__(self):
        message_field = str(self.header)
        return "<USBPacket {}: data({})>".format(message_field, len(self.data))

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

class USBPacketFeed:
    def __init__(self):
        self.packets = []

    def packet(self, packet):
        if (packet.header.is_first()):
            # this is the first fragment of a packet.
            if ((len(self.packets) != 0)):
                # problem right there, we already have fragments.
                print("Detected new packet while old packet isn't finished.")
                self.packets = []


            self.packets.append(packet)
        else:
            # this is not the first, so we append it, check sequence number, and if finished return.
            self.packets.append(packet)


        # we have the right number of fragments, create the packet data and return.
        if (len(self.packets) == self.packets[0].header.get_part_counter()):
            # packet is finished!
            packet_data = []
            for j in self.packets:
                if (j.data):
                    packet_data += j.data
                else:
                    print("Checksum failed, discarding data")
                    self.packets = []
                    return None
            self.packets = []
            return packet_data

        if (len(self.packets) >= 2):
            if (packet.header.get_part_counter() + 1 != len(self.packets)):
                print("Sequence number not matching")
                self.packets = []
                return None
            

#############################################################################
# Higher level protocol messages. Often composed of several USBPackets
#############################################################################

class Command(ctypes.LittleEndianStructure, Dictionary, Readable):
    _pack_ = 1
    _fields_ = [
        ("command", ctypes.c_uint16),
        ("direction", ctypes.c_uint16),
        ("format", ctypes.c_uint16),
        ("packet_sequence", ctypes.c_uint16),
        ("packet_length", ctypes.c_uint32)
    ]
    def __str__(self):
        return "cmd 0x{:0>4X}, dir:0x{:0>4X} fmt 0x{:0>2X}, packseq 0x{:0>2X}, len {:0>2d}".format(self.command, self.direction, self.format, self.packet_sequence, self.packet_length)

class BodyDeviceInfo(ctypes.LittleEndianStructure, Dictionary):
    _pack_ = 1
    _fields_ = [
        ("model", ctypes.c_char * 16),
        ("serial", ctypes.c_char * 16),
        ("fw_version", ctypes.c_uint8 * 4),
        ("hw_version", ctypes.c_uint8 * 4),
        ("bsl_version", ctypes.c_uint8 * 4)
    ]
    def __str__(self):
        version_string = ""
        for k,t in self._fields_:
            if (k.endswith("_version")):
                v = getattr(self, k)
                version_string += "{}: {}.{}.{}.{} ".format(k.replace("_version", ""), *v)
        return "Model: {}, Serial: {}, {}".format(self.model, self.serial, version_string)

class BodyDeviceInfoRequest(ctypes.LittleEndianStructure, Dictionary):
    _pack_ = 1
    _fields_ = [
        ("version", ctypes.c_uint8 * 4)
    ]
    def __str__(self):
        return "version " + ".".join(["{:>02d}".format(a) for a in self.version])
    

class BodyDateTime(ctypes.LittleEndianStructure, Dictionary):
    _pack_ = 1
    _fields_ = [
        ("year", ctypes.c_uint16),
        ("month", ctypes.c_uint8),
        ("day", ctypes.c_uint8),
        ("hour", ctypes.c_uint8),
        ("minute", ctypes.c_uint8),
        ("ms", ctypes.c_uint16)
    ]

class BodyDeviceStatus(ctypes.LittleEndianStructure, Dictionary):
    _pack_ = 1
    _fields_ = [
        ("pad0", ctypes.c_uint8),
        ("charge", ctypes.c_uint8),
        ("pad1", ctypes.c_uint8),
        ("pad2", ctypes.c_uint8)
    ]

class BodyPersonalSettings(ctypes.LittleEndianStructure, Dictionary):
    _pack_ = 1
    _fields_ = [
        ("data", ctypes.c_uint8*70)
    ]
    def __str__(self):
        return "".join([" {:>02X}".format(a) for a in self.data])

class BodyEmpty(ctypes.LittleEndianStructure, Dictionary):
    _pack_ = 1
    _fields_ = []

class PacketBody_(ctypes.Union):
    _fields_ = [("raw", ctypes.c_uint8 * (MAX_PACKET_SIZE - ctypes.sizeof(Command))),
                ("device_info", BodyDeviceInfo),
                ("device_info_request", BodyDeviceInfoRequest),
                ("device_status", BodyDeviceStatus),
                ("date_time", BodyDateTime),
                ("empty", BodyEmpty),
                ("personal_settings", BodyPersonalSettings),
                ]

class Packet(ctypes.LittleEndianStructure, Readable):
    _pack_ = 1
    _fields_ = [("command", Command),
                ("_body", PacketBody_)]
    _anonymous_ = ["_body",]

    command_id = None
    direction_id = None
    body_field = "raw"
 
    def __init__(self):
        message_body = getattr(self, self.body_field)
        self.command.format = 0x09
        self.command.command = self.command_id
        self.command.direction = self.direction_id
        self.body_length = ctypes.sizeof(message_body)
        self.command.packet_length = self.body_length

    @classmethod
    def read(cls, byte_object):
        a = cls()
        a.body_length = len(byte_object) - ctypes.sizeof(Command)
        ctypes.memmove(ctypes.addressof(a), bytes(byte_object),
                       min(len(byte_object), ctypes.sizeof(cls)))
        return a

    def __str__(self):
        if (self.body_field == "print"):
            return "<{} {}, {}>".format(self.__class__.__name__, self.command, "".join([" {:>02X}".format(a) for a in self.raw[0:self.body_length]]))
        else:
            message_body = str(getattr(self, self.body_field))
            return "<{} {}, {}>".format(self.__class__.__name__, self.command, message_body)

    def __bytes__(self):
        goal_length = self.body_length + ctypes.sizeof(Command)
        a = ctypes.create_string_buffer(goal_length)
        ctypes.memmove(ctypes.addressof(a), ctypes.addressof(self), goal_length)
        return bytes(a)


known_messages = []
def register_msg(a):
    known_messages.append(a)
    return a

@register_msg
class MsgDeviceInfoReply(Packet):
    command_id = 0x0200
    direction_id = 0x0002
    body_field = "device_info"

@register_msg
class MsgDeviceInfoRequest(Packet):
    command_id = 0x0000
    direction_id = 0x0001
    body_field = "device_info_request"

    def __init__(self):
        super().__init__()
        self.device_info_request.version[0] = 2
        self.device_info_request.version[1] = 4
        self.device_info_request.version[2] = 89

@register_msg
class MsgSetDateRequest(Packet):
    command_id = 0x0203
    direction_id = 0x0005
    body_field = "date_time"

@register_msg
class MsgSetDateReply(Packet):
    command_id = 0x0203
    direction_id = 0x000a
    body_field = "empty"

@register_msg
class MsgSetTimeRequest(Packet):
    command_id = 0x0003
    direction_id = 0x0005
    body_field = "date_time"

@register_msg
class MsgSetTimeReply(Packet):
    command_id = 0x000a
    body_field = "empty"

@register_msg
class MsgDeviceStatusRequest(Packet):
    command_id = 0x0603
    direction_id = 0x0005
    body_field = "empty"

@register_msg
class MsgDeviceStatusReply(Packet):
    command_id = 0x0603
    direction_id = 0x000a
    body_field = "device_status"


@register_msg
class MsgLockStatusRequest(Packet):
    command_id = 0x190B
    direction_id = 0x0005
    body_field = "empty"

@register_msg
class MsgLockStatusReply(Packet):
    command_id = 0x190B
    direction_id = 0x0202
    body_field = "empty"

@register_msg
class MsgReadSettingsRequest(Packet):
    command_id = 0x000B
    direction_id = 0x0005
    body_field = "empty"

@register_msg
class MsgReadSettingsReply(Packet):
    command_id = 0x000B
    direction_id = 0x000A
    body_field = "personal_settings"


@register_msg
class MsgWriteSettingsRequest(Packet):
    command_id = 0x010B
    direction_id = 0x0005
    body_field = "personal_settings"

@register_msg
class MsgWriteSettingsReply(Packet):
    command_id = 0x010B
    direction_id = 0x000a
    body_field = "empty"

@register_msg
class MsgSettingsUnknownRequest(Packet):
    command_id = 0x0F0B
    # direction_id = 0x0005
    body_field = "print"


@register_msg
class MsgSettingsUnknownRequest(Packet):
    command_id = 0x100B
    # direction_id = 0x0005
    body_field = "print"




message_lookup = {}

for a in known_messages:
    if ((a.command_id is not None) and (a.direction_id is not None)):
        message_lookup[(a.command_id, a.direction_id)] = a
    if ((a.command_id is not None) and (a.direction_id is None)):
        message_lookup[a.command_id] = a

def load_packet(byte_object):
    cmd = Command.read(byte_object)
    # print(cmd)
    # print(message_lookup)
    if ((cmd.command, cmd.direction) in message_lookup):
        return message_lookup[(cmd.command, cmd.direction)].read(byte_object)
    if (cmd.command in message_lookup):
        return message_lookup[cmd.command].read(byte_object)
    else:
        return Packet.read(byte_object)
    