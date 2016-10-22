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


"""
    The data request command is utilized to retrieve the filesystem.

    In the filesystem data:
        0x9e1c0 Always indicates the start of the internal log of events.
        0xffc40 Always indicates the start of the first log.

    In the file data:
        0x927c0 Always indicates the start of the internal log of events.
        0xf4240 Always indicates the start of the first log.
        0x186a0 Indicates some ASCII header of dates?
        0x2008 - 0x4800 Unknown data, but contains b'GPS POD'
        0x29810 Unknown
        0x30d40 Localization data? .text?
        0x61a80 Dense binary combined with string... perhaps firmware?
            Contains parse / formats for strings at 0x62ed8, 0x65cc8

            
    In the filesystem image the b'2I.L' marker is on 0xBE1C, in the file itself
    this marker is at 0x41C -> Filesystem header is 47616 long?

    In the fat table we find the following entry for the file:
        E5 42 50 4D 45 4D 20 20 44 41 54 20 00 AD 6E 90 76 3F 76 3F 00 00  ...
        file + extension                |                                | ...

        00 60 21 00 02 00 70 38 39 00
          |     |2 clu|filesize 3750000 bytes

    If we mount the filesystem, such that we can look at the file itself and
    the internal offsets in the file, instead of the filesystem offsets.
    This makes everything a lot clearer:

    We find on offset 0xf4240 (the position of the first GPS track):
    52 42 0F 00 52 42 0F 00 01 00 00 00 FD 45 0F 00 00 A7 50 4D 45 4D 52 42 0F 00 52 42 0F 00 1B 00 00 04 00 19 00 00 00 02 00 03 00 02 0
                                                          ^ this position is 0x0F4252! :D -> Start of log
                                        ^ At this offset, the log ends 0x0F45FD



    For the gps log we find at position 0xf4240 the following header:
    52 42 0F 00 52 42 0F 00 01 00 00 00 FD 45 0F 00 00 A7 50 4D 45 4D 52 42 0F 00 52 42 0F 00 1B 00 00 04 00 19 00 00 00 02 00 03 00 02 00 04 00 04 00 06 00 02 00 06 00 08 00 04 00 69 00 01 E0 07 0A 
    ^0x0F4252------offset pointing to ->  ----------------^
                                        0x0F45FD -> End of this log.



    On 0x927c0 We find the internal log, with the following header:
    45 32 09 00 D2 27 09 00 02 00 00 00 7B 36 09 00 01 D4 50 4D 45 4D 45 32 09 00 D2 27 09 00 0C 00 02 00 00 00 00 DC 07
                                                          ^ 0x927d2 -> begin log
    ^0x093245 points to the continuation? Or the prior?

    At 0x93245 We find another part of the internal log?
    50 4D 45 4D 45 32 09 00 D2 27 09 00 0C 00 02 00 00 00 00 DC 07 01 02 00 00 00 20 00 05 15 00 00 00 50 00 1D 03 00 56 65 72 73 69 6F 6E 3A 31 2E 36 2E 33 39
                ^ here is 0x93245, what the position of the 50 4D 45 is...
                            ^ 0x927d2 which is the start of the first log header...

    50 4D 45 4D = b'PMEM' -> The identifier of the logs.


    Ascii header at 0x186a0: day.month.year h:minutes uint32(0x00002976)

    But we know for sure that the file starts at 0xba00 in the disk image.
"""

from protocol import Readable, Dictionary
import ctypes
from collections import namedtuple
import struct
import math

"""
    So, we have a filesystem, with one file, which has an offset from the filesystem.

    Then, we can discern (at least) two PMEM blocks, one contains internal logs, the other the track logs.

    Each PMEM block has a PMEMBlockHeader, which points to a PMEMSubBlockHeader, these PMEMSubBlockHeader create a doubly
    linked list. These Logheaders contain entries, which should be parsed differently for the two PMEM Blocks.

    PMEM entries are of varying length, with one byte denoting the length of the next sample.
"""
"""
class Sample:
    # this is for simple entries...
    def __init__(self, data, id, name, itype, unit=None, scale=1, limits=None, ignore=None):
        self.data = data
        self.name = name
        self.id = id
        self.type = itype
        self.unit = unit
        self.scale = scale
        self.limits = limits
        self.ignore = ignore
        self.return_value = None
        self.raw_value = None

        if (self.type):
            self.raw_value = struct.unpack(self.type, self.data[0:struct.calcsize(self.type)])
            if ((len(self.raw_value) == 1) and (type(self.raw_value[0]) == int)):
                self.raw_value = self.raw_value[0]
                self.return_value = self.scale * self.raw_value
                if (self.limits):
                    self.return_value = max(min(self.return_value,self.limits[1]),self.limits[0])
            else:
                self.return_value = self.raw_value

    @classmethod
    def partial(cls, *partial, **kw_partial):
        return lambda d: cls(d, *partial, **kw_partial) 

    @property
    def value(self):
        return self.return_value

    def __str__(self):
        r = "<"
        r += self.name
        r += " {} ".format(self.return_value)
        if (self.unit):
            r += " [{}] ".format(self.unit)
        if (self.raw_value == self.ignore):
            r += " (ignore) "
        r += ">"
        # r += " " + " ".join(["{:>02X}".format(b) for b in self.data])
        return r

class EpisodicSamples:
    def __init__(self, *samples):
        self.samples = samples

    def __str__(self):
        return " ".join([str(s) for s in self.samples])

"""

# this is for creating more convoluted data types =)
class FieldEntry(ctypes.LittleEndianStructure, Readable, Dictionary):
    _fields_ = []
    scale = 1
    ignore = None
    unit = None
    limits = None

    @property
    def value(self):
        # works on self.field_

        # check if we ignore it.
        if (self.field_ == self.ignore):
            return None

        # next we convert the value.
        v = self.scale * self.field_
        if (self.limits):
            v = max(min(v,self.limits[1]),self.limits[0])
        return v

    def __iter__(self):
        yield ("value", self.value)
        yield ("unit", self.unit)


    """
    def __str__(self):
        r = "<"
        r += self.__class__.__name__
        v = self.value
        r += " {} ".format(v)
        if (self.unit):
            r += " [{}] ".format(self.unit)
        if (self.field_ == self.ignore):
            r += " (ignore) "
        r += ">"
        return r
    """

class Uint8ByteIgnored255Field(FieldEntry):
    _fields_ = [("field_", ctypes.c_uint8),]
    scale = 1
    ignore = 255
    

class Coordinate(FieldEntry):
    _fields_ = [("field_", ctypes.c_int32),]
    scale = 1e-7
    unit = "degrees"

class LatitudeField(Coordinate):
    limits = (-90, 90)
    key = "latitude"

class LongitudeField(Coordinate):
    limits = (-180, 180)
    key = "longitude"

class DistanceField(FieldEntry):
    _fields_ = [("field_", ctypes.c_uint32),]
    scale = 1
    unit = "m"
    key = "distance"

class HeartRateField(Uint8ByteIgnored255Field):
    unit = "bpm"
    key = "heartrate"

class TimeField(FieldEntry):
    _fields_ = [("field_", ctypes.c_int32),]
    scale = 1e-3
    unit = "s"
    key = "time"

class DurationField(FieldEntry):
    _fields_ = [("field_", ctypes.c_int32),]
    scale = 0.1
    unit = "s"
    key = "duration"

class VerticalVelocityField(FieldEntry):
    _fields_ = [("field_", ctypes.c_int16),]
    scale = 0.01
    unit = "m/s"
    key = "vertical_velocity"

class VelocityField(FieldEntry):
    _fields_ = [("field_", ctypes.c_uint16),]
    scale = 0.01
    ignore=65535
    unit = "m/s"
    key = "speed"

class GPSSpeedField(VelocityField):
    key = "gps_speed"

class WristAccSpeed(VelocityField):
    key = "wristaccessory_speed"

class BikePodSpeedField(VelocityField):
    key = "bikepod_speed"


class GPSHeadingField(FieldEntry):
    key = "gps_heading"
    _fields_ = [("field_", ctypes.c_uint16),]
    scale = 0.01 / 360.0 * 2 * math.pi
    unit = "radians"

class UnsignedMeterField(FieldEntry):
    _fields_ = [("field_", ctypes.c_uint32),]
    scale = 0.01
    unit = "m"

class EHPEField(UnsignedMeterField):
    key = "EHPE"

class EVPEField(UnsignedMeterField):
    key = "EVPE"

class AltitudeField(FieldEntry):
    _fields_ = [("field_", ctypes.c_int16),]
    scale = 0.01
    unit = "m"
    key = "altitude"
    limits = (-1000, 15000)

class PressureField(FieldEntry):
    scale = 0.1
    unit = "hpa"

class AbsPressureField(PressureField):
    _fields_ = [("field_", ctypes.c_uint16),]
    key = "absolute_pressure"

class TemperatureField(FieldEntry):
    _fields_ = [("field_", ctypes.c_int16),]
    key = "temperature"
    scale = 0.1
    unit = "celsius"
    limits = (-100, 100)

class BatteryChargeField(FieldEntry):
    _fields_ = [("field_", ctypes.c_uint8),]
    key = "batterycharge"
    unit = "%"

class GPSAltitudeField(UnsignedMeterField):
    key = "gps_altitude"
    limits = (-1000, 15000)
    

class GPSHDOPField(Uint8ByteIgnored255Field):
    key = "gps_hdop"

class GPSVDOPField(Uint8ByteIgnored255Field):
    key = "gps_vhdop"

class WristCadenceField(FieldEntry):
    _fields_ = [("field_", ctypes.c_uint16),]
    ignore=65535
    unit = "rpm"
    key = "wrist_cadence"

class GPSSNRField(FieldEntry):
    _fields_ = [("field_", ctypes.c_uint8*16),]
    unit = ""
    key = "snr"
    
class NumberOfSatellitesField(Uint8ByteIgnored255Field):
    key = "gps_satellites"

class SeaLevelPressureField(PressureField):
    _fields_ = [("field_", ctypes.c_int16),]
    key = "sealevel_pressure"

class CadenceField(Uint8ByteIgnored255Field):
    key = "cadence"


sample_types = {
    1:LatitudeField,
    2:LongitudeField,
    3:DistanceField,
    4:VelocityField,
    5:HeartRateField,
    6:TimeField,
    7:GPSSpeedField,
    8:VelocityField,
    9:BikePodSpeedField,
    10:EHPEField,
    11:EVPEField,
    12:AltitudeField,
    13:AltitudeField,
    14:AbsPressureField,
    15:TemperatureField,
    16:BatteryChargeField,
    17:GPSAltitudeField,
    18:GPSHeadingField,
    19:GPSHDOPField,
    20:GPSVDOPField,
    21:WristCadenceField,
    22:GPSSNRField,
    23:SeaLevelPressureField,
    24:NumberOfSatellitesField,
    25:VerticalVelocityField,    
    26:CadenceField,    
}

"""
sample_lookup = { # the one-off samples?
    1:Sample.partial(1, "Latitude", "i", "degrees", 0.0000001, (-90,90)),
    2:Sample.partial(2, "Longitude", "i", "degrees", 0.0000001, (-180,180)),
    3:Sample.partial(3, "Distance", "I", "meters"), #<
    4:Sample.partial(4, "Speed", "H", "m/s", scale=0.01, ignore=65535), #<
    5:Sample.partial(5, "HR", "B", "bpm", ignore=255),
    6:Sample.partial(6, "Time", "I", "ms"),
    7:Sample.partial(7, "GPSSpeed", "H", "m/s", scale=0.01),
    8:Sample.partial(8, "WristAccSpeed", "H", "m/s", scale=0.01),
    9:Sample.partial(9, "BikePodSpeed", "H", "m/s", scale=0.01),
    10:Sample.partial(10, "EHPE", "I", "meters", scale=0.01),
    11:Sample.partial(11, "EVPE", "I", "meters", scale=0.01),
    12:Sample.partial(12, "Altitude", "h", "meters", limits=(-1000,15000)),
    13:Sample.partial(13, "AbsPressure", "H", "hpa", scale=0.1),
    14:Sample.partial(14, "EnergyConsumption", "H", "hcal/min"),
    15:Sample.partial(15, "Temperature", "h", "celsius", 0.1, (-100,100)),
    16:Sample.partial(16, "BatteryCharge", "B", "%"),
    17:Sample.partial(17, "GPSAltitude", "i", "meters", 0.01, (-1000,15000)),
    18:Sample.partial(18, "GPSHeading", "H", "degrees", 0.01, (0,360), ignore=65535),
    19:Sample.partial(19, "GpsHDOP", "B", ignore=255),
    20:Sample.partial(20, "GpsVDOP", "B", ignore=255),
    21:Sample.partial(21, "WristCadence", "H", "rpm", ignore=65535),
    22:Sample.partial(22, "SNR", "16c"),
    23:Sample.partial(23, "NumberOfSatellites", "B", ignore=255),
    24:Sample.partial(24, "SeaLevelPressure", "h", "hpa", 0.1),
    25:Sample.partial(25, "VerticalSpeed", "h", "m/s", 0.01), #<
    26:Sample.partial(26, "Cadence", "B", "rpm", ignore=255),
}
"""

class DataStructure(ctypes.LittleEndianStructure, Readable, Dictionary):
    _pack_ = 1
    pass

class GpsUserData(DataStructure):
    _fields_ = [
                ("Time", TimeField),
                ("latitude", LatitudeField),
                ("longitude", LongitudeField),
                ("gpsaltitude", ctypes.c_int16),
                ("gpsheading", GPSHeadingField),
                ("EHPE", ctypes.c_uint8),
                ]

class TimeBlock(DataStructure):
    _fields_ = [
                ("year", ctypes.c_uint16),
                ("month",  ctypes.c_uint8),
                ("day", ctypes.c_uint8),
                ("hour", ctypes.c_uint8),
                ("minutes", ctypes.c_uint8),
                ("seconds", ctypes.c_uint8),
                ]
class TimeReference(DataStructure):
    _fields_ = [
                ("local", TimeBlock), # order might be swapped
                ("UTC",  TimeBlock)
                ]


class VelocityFieldKmH(FieldEntry):
    _fields_ = [("field_", ctypes.c_uint16),]
    scale = 0.01 / 3.6
    unit = "m/s"


class TrackHeader(DataStructure):
    _fields_ = [("time", TimeBlock), # sure
                ("interval_SPECULATED", ctypes.c_uint16),
                ("duration", DurationField), # sure
                ("_", ctypes.c_uint8*14), # ??
                ("velocity_avg", VelocityFieldKmH), # sure
                ("velocity_max", VelocityFieldKmH), # sure
                ("altitude_min", ctypes.c_int16),
                ("altitude_max", ctypes.c_int16),
                ("heartrate_avg", ctypes.c_uint8),
                ("heartrate_max", ctypes.c_uint8),
                ("_", ctypes.c_uint8),
                ("activity_type", ctypes.c_uint8), # sure
                ("activity_name", ctypes.c_char*16), # sure
                ("heartrate_min", ctypes.c_uint8),
                ("_", ctypes.c_uint8),
                ("_", ctypes.c_uint8),
                ("distance", DistanceField), # sure
                ("samples", ctypes.c_uint32), # sure
]
    _anonymous_ = ["time"]

class VariableLengthField():
    def __init__(self, blob):
        # self.data = ctypes.c_uint8 * int(len(blob))
        self.data = ctypes.create_string_buffer(len(blob))

    @classmethod
    def read(cls, byte_object):
        a = cls(byte_object)
        ctypes.memmove(ctypes.addressof(a.data), bytes(byte_object),
                       min(len(byte_object), ctypes.sizeof(a.data)))
        return a

    def __iter__(self):
        yield ("raw", self.data.value)
        yield ("key", self.key)

class FallbackField(VariableLengthField):
    key = "unknown_field"

class GPSTestField(FieldEntry):
    _fields_ = [("field_", ctypes.c_uint8*16),]
    key = "gps_test"

class GPSDataField(VariableLengthField):
    key = "gpsdata"

class GPSAccuracyField(VariableLengthField):
    key = "accdata"


class LogPauseField(FieldEntry):
    key = "logpause"

class LogRestartField(FieldEntry):
    key = "logrestart"

class IBIDataField(FieldEntry):
    _fields_ = [("field_", ctypes.c_uint8*64),]
    key = "ibidata"

class TTFFField(FieldEntry):
    _fields_ = [("field_", ctypes.c_uint16),]
    scale = 0.1
    unit = "s"
    key = "ttff"

class DistanceSourceField(Uint8ByteIgnored255Field):
    key = "distancesource"

class LapInfoField(FieldEntry):
    _fields_ = [("field_", ctypes.c_uint16 * 23),]
    key = "lapinfo"

class GPSTestData(FieldEntry):
    _fields_ = [("field_", ctypes.c_uint8*61),]
    key = "gpstestdata"



episodic_types = {
    1:GPSTestField,
    2:GPSDataField,
    3:GPSAccuracyField,
    4:LogPauseField,
    5:LogRestartField,
    6:IBIDataField,
    7:TTFFField,
    8:DistanceSourceField,
    9:LapInfoField,
    10:GpsUserData,
    11:GPSTestData,
    12:TimeReference,
}
"""
episodic_lookup = {
    1:Sample.partial(1, "GPS test", "16c"),
    2:Sample.partial(2, "gpsdata", "x"), # length:?
    3:Sample.partial(3, "accdata", "x"), # length:?
    4:Sample.partial(4, "logpause", ""),
    5:Sample.partial(5, "logrestart", ""),
    6:Sample.partial(6, "ibidata", "64c"),
    7:Sample.partial(7, "ttff", "H", "seconds", 0.1),
    8:Sample.partial(8, "distancesource", "B", ignore=255),
    9:Sample.partial(9, "lapinfo", "23c"),
    # 10:Sample.partial(10, "gpsuserdata", "17c"),
    10:lambda x: GpsUserData.read(x),
    11:Sample.partial(11, "gpstestdata", "61c"),
    # 12:Sample.partial(12, "timeref", "14c"),
    12:lambda x: TimeReference.read(x),
}
SampleFallback = Sample.partial(0, "Unknown", "")
"""

class MEMfs():
    # contains the entire filesystem.
    def __init__(self, obj):
        self.backend = obj

    def __getitem__(self, key):
        return self.backend[key]



class BPMEMfile():
    # contains the BPMEM.DAT file, that is; the thing that has the correct offsets.
    offset = 0xba00
    def __init__(self, fs):
        self.tracks = PMEMTrack(self, offset=0xf4240)
        self.log = PMEMInternalLog(self, offset=0x927c0)
        self.fs = fs

    def __getitem__(self, key):
        # print("File: 0x{:0>6X} : 0x{:0>6X}".format(key.start, key.stop))
        return self.fs[slice(key.start + self.offset, key.stop + self.offset, key.step)]

"""
    Every PMEMBlock contains several SubBlocks, these SubBlocks contain the
    entries to the log.
"""
class PMEMBlockHeader(ctypes.LittleEndianStructure, Dictionary, Readable):
    _pack_ = 1
    _fields_ = [
        ("last", ctypes.c_uint32),
        ("first", ctypes.c_uint32),
        ("entries", ctypes.c_uint32),
        ("free", ctypes.c_uint32),
        ("pad", ctypes.c_uint16),
    ]
    def __str__(self):
        return "first: 0x{:0>6X}, last 0x{:0>6X}, entries: {:0>4d}, free:  0x{:0>6X}, ({:0>4X})".format(self.first, self.last, self.entries, self.free, self.pad)



class PMEMSubBlockHeader(ctypes.LittleEndianStructure, Dictionary, Readable):
    _pack_ = 1
    _fields_ = [
        ("magic", ctypes.c_char*4),
        ("next", ctypes.c_uint32),
        ("prev", ctypes.c_uint32)
    ]
    def __str__(self):
        return "magic: {}, prev 0x{:0>6X} next 0x{:0>6X}".format(str(self.magic), self.prev, self.next)


class PMEMBlock():
    def __init__(self, file, offset):
        self.file = file
        self.offset = offset
        self.logs = []

    def load_block_header(self):
        tmp = self.file[self.offset:(self.offset+ctypes.sizeof(PMEMBlockHeader))]
        self.header = PMEMBlockHeader.read(tmp)

    def load_logs(self):
        current_position = self.header.first
        
        for i in range(0, self.header.entries):
            print("Reading at: 0x{:0>6X}".format(current_position))
            log_header = PMEMSubBlockHeader.read(self.file[current_position:current_position+ctypes.sizeof(PMEMSubBlockHeader)])

            if (log_header.next == current_position):
                print("Done")
            print(log_header)
            self.logs.append(self.pmem_type(self, current_position+ctypes.sizeof(PMEMSubBlockHeader), log_header))
            # self.logs.append({"entry":this_entry, "pos":current_position, "header_pos":current_position+ctypes.sizeof(PMEMSubBlockHeader)})
            current_position = log_header.next


class PMEMEntry(ctypes.LittleEndianStructure, Dictionary, Readable):
    _pack_ = 1
    _fields_ = [
        ("type", ctypes.c_uint8),
        ("next", ctypes.c_uint32),
        ("prev", ctypes.c_uint32)
    ]


class PMEMEntries():
    def __init__(self, block, pos, log_header):
        self.block = block
        self.start_pos = pos
        self.pos = pos
        self.log_header = log_header
        self.entries = []
        self.retrieved_entry_count = 0

    def get_entry(self):
        self.retrieved_entry_count += 1
        # everything is an entry: headers are too!
        length, = struct.unpack("<H", self.block.file[self.pos:self.pos+2])
        self.pos += 2

        # TODO: Manage log wrap... how does this manifest itself?!
        data = self.block.file[self.pos:self.pos+length]
        self.pos += length
        return data

    def parse(self, format, buffer, offset=0):
        res = list(struct.unpack_from(">"+format, buffer, offset))
        # print(res)
        res.append(offset + struct.calcsize(format))
        # print(res)
        return res

    def get_entries(self):
        return self.entries


class PMEMTrackEntries(PMEMEntries):
    header_metadata = None
    periodic_entries = []

    def load_header(self):
        # should contain the periodic specification
        self.header_samples = self.get_entry()
        self.process_entry(self.header_samples)

        # should contain all the metadata
        self.header_metadata_bytes = self.get_entry()
        self.process_entry(self.header_metadata_bytes)
        if (self.header_metadata is None):
            return False

        # No clue... \x03\x82\x00\x00\x00\x04
        self.header_unknown1 =  self.get_entry()
        self.process_entry(self.header_unknown1)

        # No clue... \x03\x83\x00\x00\x00\x05
        self.header_unknown2 =  self.get_entry()
        self.process_entry(self.header_unknown2)

        return True


    def process_entry(self, entry_bytes):
        pos = 0
        entry_type, pos = self.parse("B", entry_bytes, pos)

        # Defines the entries of the periodic type.
        if (entry_type == 0):
            pos = 0
            periodic_count, pos = self.parse("H", entry_bytes, pos)
            # This probably CAN be a variable length array, it consists of:
            #: \x04\x00 # count
            #  |type   |offset |length  of type 2 samples.
            #: \x19\x00\x00\x00\x02\x00
            #: \x03\x00\x02\x00\x04\x00
            #: \x04\x00\x06\x00\x02\x00
            #: \x06\x00\x08\x00\x04\x00
            self.periodic_entries = []
            field_list = []
            anonymous_fields = []
            for p in range(periodic_count):
                type, offset, length, pos = self.parse("HHH", entry_bytes, pos)
                self.periodic_entries.append((type, offset, length))
                field_list.append((sample_types[type].key, sample_types[type]))
                anonymous_fields.append(sample_types[type].key)

            print(field_list)
            # next, we craft our periodicStructure:
            class periodicStructure(DataStructure):
                _fields_ = field_list
                # _anonymous_ = anonymous_fields

            self.periodic_structure = periodicStructure
                
            return None

        if (entry_type == 1):
            # print("Bytes: {}".format(" ".join(["{:0>2X}".format(a) for a in entry_bytes[pos:]])))
            self.header_metadata = TrackHeader.read(entry_bytes[pos:])
            # print("Found header: {}".format(self.header_metadata))
            
        # is periodic sample.
        if (entry_type == 2):
            samples = []
            # parse it according to the periodic entries.
            # for sample_type, offset, length in self.periodic_entries:
                # sample = sample_lookup.get(sample_type, SampleFallback)
                # samples.append(sample(entry_bytes[pos+offset:pos+offset+length]))
            # print(" ".join([str(a) for a in samples]))
            # print(self.periodic_structure.read(entry_bytes[pos:]))
            # return EpisodicSamples(*samples)
            return self.periodic_structure.read(entry_bytes[pos:])

        # Episodic type
        if (entry_type == 3):
            timestamp, pos = self.parse("I", entry_bytes, pos)
            episode_type, pos = self.parse("B", entry_bytes, pos)
            sample = episodic_types.get(episode_type, FallbackField)
            processed = sample.read(entry_bytes[pos:])
            return processed


    def load_entries(self):
        if (self.header_metadata is not None):
            for i in range(self.header_metadata.samples-self.retrieved_entry_count):
                processed = self.process_entry(self.get_entry())
                # print(processed)
                self.entries.append(processed)


class InternalLogEntry:
    def __init__(self, mtype, header, time, identifier, text):
        self.header = header
        self.type = mtype
        self.time = time
        self.identifier = identifier
        self.text = text

    def __str__(self):
        return "t: {: >10d}, (0x{:0>8X}), {}".format(self.time, self.identifier, self.text)
        

class PMEMLogEntries(PMEMEntries):

    def load_header(self):
        self.header_bytes = self.get_entry()
        self.header = TimeBlock.read(self.header_bytes[5:])
        return True

    def process_entry(self, entry_bytes):
        pos = 0

        entry_type, pos = self.parse("B", entry_bytes, pos)

        # print("\033[1;90m{0}\033[00m".format(" ".join(["{:0>2X}".format(b) for b in entry_bytes])))
        # print("{}".format(" ".join(["{:0>2X}".format(b) for b in entry_bytes])))
        # print(str(entry_bytes))

        if (entry_type == 5):
            # Seriously, what's up with the change in endianness for timestamp?
            timestamp, = struct.unpack("<I", entry_bytes[pos:pos+4])
            identifier, pos = self.parse("Ix", entry_bytes, pos+4)
            try:
                text = entry_bytes[pos:].decode('ascii')
            except UnicodeDecodeError:
                text = str(entry_bytes[pos:])
            # print("entry_type: {} : t: {: >10d}, (0x{:0>8X}), {}".format(entry_type, timestamp, identifier, text))
            entry = InternalLogEntry(entry_type, self.header, timestamp, identifier, text)
            return entry

        if (entry_type == 3):
            # print("entry_type: {} : No clue {}".format(entry_type, " ".join(["{:0>2X}".format(b) for b in entry_bytes])))
            text = " ".join(["{:0>2X}".format(b) for b in entry_bytes[1:]])
            entry = InternalLogEntry(entry_type, self.header, 0, 0, text)
            return entry
            
            
        # return True

    def load_entries(self, max=1000000):
        # probably for the best to take some limit on this...
        for i in range(max):
            data = self.get_entry()
            if (not data):
                break
            processed = self.process_entry(data)
            # print(processed)
            self.entries.append(processed)


class PMEMTrack(PMEMBlock):
    pmem_type = PMEMTrackEntries

class PMEMInternalLog(PMEMBlock):
    pmem_type = PMEMLogEntries


if __name__ == "__main__":
    import sys
    with open(sys.argv[1], 'rb') as f:
        fs_data = f.read()

    m = MEMfs(fs_data)
    data = BPMEMfile(m)
    print("Tracks:")
    data.tracks.load_block_header()
    data.tracks.load_logs()
    print(data.tracks.logs)
    for track in data.tracks.logs:
        if not track.load_header():
            continue
        track.load_entries()

    for track in data.tracks.logs:
        print("\n\nNew track {}".format(track.header_metadata))
        samples = track.get_entries()
        for sample in samples[:15]:
            print(sample)

    sys.exit()
    data.log.load_block_header()
    data.log.load_logs()
    for log in data.log.logs:
        if not log.load_header():
            continue
        log.load_entries()
        samples = log.get_entries()
        for sample in samples[:15]:
            print(sample)
        
    # for j in range(10):
        # entry = data.tracks.logs[0].get_entry()
        # a = Sample.read(entry)
        # print(" ".join(["{:0>2X}".format(a) for a in entry]) +  "  " + str(entry))

    # print(data.tracks.header)
    # print(data.log.header)