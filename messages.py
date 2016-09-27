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
from collections import namedtuple

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
# Structs for the various parts in the firmware. These correspond to
# the structures as defined in the header files.
class MsgHeader(ctypes.LittleEndianStructure, Dictionary):
    _pack_ = 1
    # https://github.com/openambitproject/openambit/blob/master/src/libambit/protocol.c#L41
    _fields_ = [("magic", ctypes.c_uint8),
                ("usb_length", ctypes.c_uint8),
                ("message_part", ctypes.c_uint8),
                ("message_length", ctypes.c_uint8),
                ("sequence", ctypes.c_uint16),
                ("header_checksum", ctypes.c_uint16)]

    #def __str__(self):
       #return "cmd: {:0>4X}, len: {:0>4d}, seq: {:0>4d} {}".format(self.command, self.len, self.sequence, (" {:0>2X}"*len(bytes(self))).format(*bytes(self)))

class MsgBodyCommand(ctypes.LittleEndianStructure, Dictionary):
    _pack_ = 1
    _fields_ = [
        ("command", ctypes.c_uint32),
        ("format", ctypes.c_uint16),
        ("packet_sequence", ctypes.c_uint16),
        ("packet_length", ctypes.c_uint32)
    ]

# create the composite message.
class _MsgBody(ctypes.Union):
    # checksum is at the end of the body length, not at the end of packet!
    _fields_ = [("raw", ctypes.c_byte * (PACKET_SIZE-ctypes.sizeof(MsgHeader))),
                ("command", MsgBodyCommand)]

#############################################################################


# Class which represents all messages. That is; it holds all the structs.
class Msg(ctypes.LittleEndianStructure, Readable):
    _pack_ = 1
    _fields_ = [("header", MsgHeader),
                ("_body", _MsgBody)]
    _anonymous_ = ["_body"]

    # Pretty print the message according to its type.
    def __str__(self):
        # if (self.msg_type in msg_type_field):
           # payload_text = str(getattr(self, msg_type_field[self.msg_type]))
           # message_field = msg_type_name[self.msg_type]
        #else:
        message_field = str(self.header)
        # payload_text = "-"
        return "<Msg {}: {}>".format(message_field, self.command)

    # We have to treat the mixin slightly different here, since we there is
    # special handling for the message type and thus the body.
    def __iter__(self):
        for k, t in self._fields_:
            if (k == "_body"):
                if (self.msg_type in msg_type_field):
                    message_field = msg_type_field[self.msg_type]
                    body = dict(getattr(self, msg_type_field[self.msg_type]))
                else:
                    message_field = "raw"
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