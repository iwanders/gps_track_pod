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
import xml.etree.cElementTree as ET
from xml.dom import minidom
import datetime
from math import pi


class GPSWriter:
    def __init__(self, logentries, metadata, lap_splits_segment=True,
                 lap_adds_wpt=True, write_points=True):

        self.logentries = logentries
        self.metadata = metadata

        self.lap_splits_segment = lap_splits_segment
        self.lap_adds_wpt = lap_adds_wpt
        self.write_points = write_points

        self.process_data()

    def process_data(self):
        self.base_time = datetime.datetime(year=self.metadata.year,
                                           month=self.metadata.month,
                                           day=self.metadata.day,
                                           hour=self.metadata.hour,
                                           minute=self.metadata.minute,
                                           second=self.metadata.second)
        # first run a for loop to consolidate the data, we take the periodic as
        # dominant for the time, as it is more precise.
        self.entries = []
        current = {}
        self.time_reference = None
        self.distance_source = None  # Can this ever be other than the gps?
        self.lap_info = []
        finished_log = False
        for entry in self.logentries:
            # print(type(entry))
            if (isinstance(entry, pmem.PeriodicStructure)):
                current.update(dict(entry))
                continue
            if (isinstance(entry, pmem.GpsUserData)):
                current.update(dict(entry))
                self.entries.append(current)
                current = {}
                continue
            if (isinstance(entry, pmem.TimeReference)):
                self.time_reference = entry
                continue
            if (isinstance(entry, pmem.DistanceSourceField)):
                self.distance_source = entry
                continue
            if (isinstance(entry, pmem.LogPauseField)):
                # this is an empty message at the end.
                if (finished_log):
                    print("Found {} again! Should that ever happen?".format(
                          type(entry)))
                finished_log = True
                continue

            if (isinstance(entry, pmem.LapInfoField)):
                # Get current or most recent current with the gps position.
                if ("latitude" in current):
                    posinfo = current
                else:
                    posinfo = self.entries[-1]
                # event_type == 1 is manual (button is pressed)
                position_info = posinfo.copy()
                position_info.update(dict(entry))
                position_info["lap_indicator"] = True
                self.entries.append(position_info)
                self.lap_info.append(position_info)
                continue

            print("Unhandled type: {}".format(type(entry)))
            print("Unhandled data: {}".format(" ".join(["{:0>2X}".format(x)
                                              for x in bytes(entry)])))

    def create_xml(self):
        root = ET.Element("gpx")
        root.attrib["creator"] = "GPS Track Pod "\
            "(via https://github.com/iwanders/gps_track_pod)"
        root.attrib["xmlns:xsi"] = "http://www.w3.org/2001/XMLSchema-instance"
        root.attrib["xsi:schemaLocation"] = \
            "http://www.topografix.com/GPX/1/1 "\
            "http://www.topografix.com/GPX/1/1/gpx.xsd "\
            "http://www.cluetrust.com/XML/GPXDATA/1/0 "\
            "http://www.cluetrust.com/Schemas/gpxdata10.xsd "\
            "http://www.garmin.com/xmlschemas/TrackPointExtension/v1 "\
            "http://www.garmin.com/xmlschemas/TrackPointExtensionv1.xsd"
        root.attrib["xmlns:gpxdata"] = \
            "http://www.cluetrust.com/XML/GPXDATA/1/0"
        root.attrib["xmlns:gpxtpx"] = \
            "http://www.garmin.com/xmlschemas/TrackPointExtension/v1"
        root.attrib["xmlns"] = "http://www.topografix.com/GPX/1/1"
        root.attrib["version"] = "1.1"

        trk = ET.SubElement(root, "trk")

        if self.lap_adds_wpt:
            for i in range(0, len(self.lap_info)):
                lap = self.lap_info[i]
                # print(lap)
                wptel = ET.SubElement(root, "wpt")
                if lap["event_type"] == 1:
                    added_extensions = {"gpxdata:event": "lap_manual"}
                    name = "Manual waypoint {}".format(i+1)
                    timestamp = datetime.datetime(year=lap["year"],
                                                  month=lap["month"],
                                                  day=lap["day"],
                                                  hour=lap["hour"],
                                                  minute=lap["minute"],
                                                  second=lap["second"])
                    pretty_date = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    comment = "Button click at {}.".format(pretty_date)
                else:
                    # TODO
                    added_extensions = {"gpxdata:event": "unknown"}
                    name = "unknown waypoint."
                    comment = "Not known why there is a lap here..?"
                    print("Unkown lap event type: {}".format(
                          lap["event_type"]))
                self.populate_element(wptel, lap, name=name,
                                      added_extensions=added_extensions,
                                      comment=comment)

        name_el = ET.SubElement(trk, "name")
        name_el.text = self.base_time.strftime("Track %Y-%m-%d %H:%M:%S")

        if self.write_points:
            trkseg = ET.SubElement(trk, "trkseg")
            for seg in self.entries:
                if (self.lap_splits_segment and "lap_indicator" in seg):
                    trkseg = ET.SubElement(trk, "trkseg")
                    continue

                if ("latitude" not in seg) or ("longitude" not in seg) or (
                                                            "time" not in seg):
                    print("Skipping segment: {}".format(seg))
                    continue

                trkpt = ET.SubElement(trkseg, "trkpt")
                self.populate_element(trkpt, seg)

        xmlstr = ET.tostring(root, encoding='utf-8', method='xml')
        xmlstr_pretty = minidom.parseString(xmlstr).toprettyxml(
                            encoding='utf-8')

        return xmlstr_pretty

    def populate_element(self, el, seg, name=None, comment=None,
                         added_extensions={}):

        el.attrib["lat"] = "{:.7f}".format(seg["latitude"]["value"])
        el.attrib["lon"] = "{:.7f}".format(seg["longitude"]["value"])

        relative_time = datetime.timedelta(seconds=seg["time"]["value"])
        sample_time = self.base_time + relative_time

        time_el = ET.SubElement(el, "time")
        time_el.text = sample_time.isoformat() + "Z"

        if "gpsaltitude" in seg:
            elevation = ET.SubElement(el, "ele")
            elevation.text = "{:d}".format(seg["gpsaltitude"])

        if (comment is not None):
            commentel = ET.SubElement(el, "cmt")
            commentel.text = "{}".format(comment)

        if (name is not None):
            nameel = ET.SubElement(el, "name")
            nameel.text = "{}".format(name)

        extensions = ET.SubElement(el, "extensions")

        if "distance" in seg:
            distance = ET.SubElement(extensions, "gpxdata:distance")
            distance.text = "{:d}".format(seg["distance"]["value"])

        if ("speed" in seg) and (seg["speed"]["value"] is not None):
            speed = ET.SubElement(el, "speed")
            speed.text = "{:.3f}".format(seg["speed"]["value"])

        """ # always zero for my recordings.
        if "vertical_velocity" in seg:
            vertical_velocity = ET.SubElement(extensions,
                                              "gpxdata:verticalSpeed")
            vertical_velocity.text = "{:.3f}".format(
                seg["vertical_velocity"]["value"])
        """

        if ("heartrate" in seg) and (seg["heartrate"]["value"] is not None):
            heartrate = ET.SubElement(extensions,
                                      "gpxdata:hr")
            heartrate.text = "{:d}".format(seg["heartrate"]["value"])

        if "EHPE" in seg:
            hdop = ET.SubElement(el, "hdop")
            hdop.text = "{:d}".format(seg["EHPE"])

        if "EVPE" in seg:
            vdop = ET.SubElement(el, "vdop")
            vdop.text = "{:d}".format(seg["EVPE"])

        if "gpsheading" in seg:
            gpsheading = ET.SubElement(extensions,
                                       "gpxdata:heading")
            # Spec describes degreesType: "Used for bearing, heading, course."
            # But does not mention the tag names heading should have, is it
            # out of the extensions in GPX 1.1?
            # Either way, have to convert it.
            heading = (seg["gpsheading"]["value"] / (2*pi)) * 360.0
            gpsheading.text = "{:.3f}".format(heading)

        for k, v in added_extensions.items():
            _ = ET.SubElement(extensions, k)
            _.text = "{}".format(v)
