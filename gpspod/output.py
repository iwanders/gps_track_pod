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

from .pmem import PeriodicStructure, GpsUserData
import xml.etree.cElementTree as ET
from xml.dom import minidom
import datetime


def create_gpx_from_log(logentries, metadata):
    root = ET.Element("gpx")
    root.attrib["creator"] = "GPS Track Pod "\
                             "(via https://github.com/iwanders/gps_track_pod)"
    root.attrib["xmlns:xsi"] = "http://www.w3.org/2001/XMLSchema-instance"
    root.attrib["xsi:schemaLocation"] = "http://www.topografix.com/GPX/1/1 "\
        "http://www.topografix.com/GPX/1/1/gpx.xsd "\
        "http://www.cluetrust.com/XML/GPXDATA/1/0 "\
        "http://www.cluetrust.com/Schemas/gpxdata10.xsd "\
        "http://www.garmin.com/xmlschemas/TrackPointExtension/v1 "\
        "http://www.garmin.com/xmlschemas/TrackPointExtensionv1.xsd"
    root.attrib["xmlns:gpxdata"] = "http://www.cluetrust.com/XML/GPXDATA/1/0"
    root.attrib["xmlns:gpxtpx"] = \
        "http://www.garmin.com/xmlschemas/TrackPointExtension/v1"
    root.attrib["xmlns"] = "http://www.topografix.com/GPX/1/1"
    root.attrib["version"] = "1.1"

    trk = ET.SubElement(root, "trk")
    trkseg = ET.SubElement(trk, "trkseg")

    # first run a for loop to consolidate the data, we take the periodic as
    # dominant for the time, as it is more precise.
    entries = []
    current = {}
    for entry in logentries:
        # print(type(entry))
        if (isinstance(entry, PeriodicStructure)):
            current.update(dict(entry))
        if (isinstance(entry, GpsUserData)):
            current.update(dict(entry))
            entries.append(current)
            current = {}

    base_time = datetime.datetime(year=metadata.year,
                                  month=metadata.month,
                                  day=metadata.day,
                                  hour=metadata.hour,
                                  minute=metadata.minute,
                                  second=metadata.second)
    name_el = ET.SubElement(trk, "name")
    name_el.text = base_time.strftime("Track %Y-%m-%d %H:%M:%S")

    for seg in entries:
        # print(seg)
        if ("latitude" not in seg) or ("longitude" not in seg) or (
                                                            "time" not in seg):
            print("Skipping segment: {}".format(seg))
            continue

        trkpt = ET.SubElement(trkseg, "trkpt")
        trkpt.attrib["lat"] = "{:.7f}".format(seg["latitude"]["value"])
        trkpt.attrib["lon"] = "{:.7f}".format(seg["longitude"]["value"])

        relative_time = datetime.timedelta(seconds=seg["time"]["value"])
        sample_time = base_time + relative_time

        time_el = ET.SubElement(trkpt, "time")
        time_el.text = sample_time.isoformat() + "Z"

        if "gpsaltitude" in seg:
            elevation = ET.SubElement(trkpt, "ele")
            elevation.text = "{:d}".format(seg["gpsaltitude"])

        extensions = ET.SubElement(trkpt, "extensions")

        if "distance" in seg:
            distance = ET.SubElement(extensions, "gpxdata:distance")
            distance.text = "{:d}".format(seg["distance"]["value"])

        if ("speed" in seg) and (seg["speed"]["value"] is not None):
            speed = ET.SubElement(extensions, "gpxdata:speed")
            speed.text = "{:.3f}".format(seg["speed"]["value"])

        if "vertical_velocity" in seg:
            vertical_velocity = ET.SubElement(extensions,
                                              "gpxdata:verticalSpeed")
            vertical_velocity.text = "{:.3f}".format(
                seg["vertical_velocity"]["value"])

        if ("heartrate" in seg) and (seg["heartrate"]["value"] is not None):
            heartrate = ET.SubElement(extensions,
                                      "gpxdata:hr")
            heartrate.text = "{:d}".format(seg["heartrate"]["value"])

        if "EHPE" in seg:
            EHPE = ET.SubElement(extensions,
                                 "gpxdata:EHPE")
            EHPE.text = "{:d}".format(seg["EHPE"])

        if "EVPE" in seg:
            EVPE = ET.SubElement(extensions,
                                 "gpxdata:EVPE")
            EVPE.text = "{:d}".format(seg["EVPE"])

        if "gpsheading" in seg:
            gpsheading = ET.SubElement(extensions,
                                       "gpxdata:heading")
            gpsheading.text = "{:.3f}".format(seg["gpsheading"]["value"])

    xmlstr = ET.tostring(root, encoding='utf-8', method='xml')
    xmlstr_pretty = minidom.parseString(xmlstr).toprettyxml()

    return xmlstr_pretty
