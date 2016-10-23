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


import sys
from .usb_pdml import USBPDML
from .protocol import USBPacket, USBPacketFeed, load_msg
from . import protocol
from . import pmem
import pickle
import json
import gzip
import base64


def load_pdml_usb(path):
    # check if we have a cached version available
    if (path.endswith(".pickle3")):
        with open(path, "rb") as f:
            interactions = pickle.load(f)
    else:
        conversation = USBPDML(path)
        conversation.parse_file()
        interactions = conversation.interaction()
        # write the cached version
        with open(path + ".pickle3", "wb") as f:
            pickle.dump(interactions, f)

    entries = {"incoming": [], "outgoing": []}
    start_time = None
    index = 0

    for msg in interactions:
        index += 1
        if (start_time is None):
            start_time = msg["time"]
        t = msg["time"] - start_time

        if "data" in msg:
            data = bytes(msg["data"])
            direction = msg["direction"]
            if direction == "<":
                entries["incoming"].append((t, data))
            else:
                entries["outgoing"].append((t, data))

    return entries


def load_json_usb(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt") as f:
        rawentries = json.load(f)

    entries = {"incoming": [], "outgoing": []}
    for d in entries.keys():
        for t, v in rawentries[d]:
            entries[d].append((t, base64.b64decode(v)))

    return entries


def order_entries_and_combine(entries):
    one_list = []
    for d in entries.keys():
        for z in entries[d]:
            one_list.append((z[0], d, z[1]))
    return sorted(one_list, key=lambda d: d[0])


def load_usb_transactions(path):
    if (path.count(".xml") != 0):
        data = load_pdml_usb(path)
        return data

    if (path.count(".json")):
        data = load_json_usb(path)
        return data


def reconstruct_filesystem(path, output_file):
    data = load_usb_transactions(path)
    fs_bytes = bytearray(pmem.FILESYSTEM_SIZE)
    touched_fs = bytearray(pmem.FILESYSTEM_SIZE)
    feed = USBPacketFeed()
    for t, v in data["incoming"]:
        usb_packet = USBPacket.read(v)
        res = feed.packet(usb_packet)
        if (res):
            msg = load_msg(res)
            if (type(msg) == protocol.DataReply):
                pos = msg.position()
                length = msg.length()
                fs_bytes[pos:pos+length] = bytes(msg.content())
                touched_fs[pos:pos+length] = bytearray(
                                                [1 for i in range(length)])

    missing = False
    for i in range(len(touched_fs)):
        v = touched_fs[i]
        if (v == 0):
            if (missing is False):
                print("Missing from 0x{:0>4X}".format(i), end="")
            missing = True
        else:
            if (missing is True):
                print(" up to 0x{:0>4X}".format(i))
            missing = False
    if (missing is True):
        print(" up to 0x{:0>4X}".format(i))

    with open(output_file, "wb") as f:
        f.write(fs_bytes)


def print_interaction(path):
    dir_specific = {
        "incoming": {
            "feed": USBPacketFeed(),
            "color": "\033[1;32m{0}\033[00m",
        },
        "outgoing": {
            "feed": USBPacketFeed(),
            "color": "\033[1;34m{0}\033[00m",
        }
    }

    data = load_usb_transactions(path)
    # lets just start with outgoing always.
    combined_entries = order_entries_and_combine(data)
    start_time = combined_entries[0][0]
    for time, direction, data in combined_entries:
        reltime = time - start_time
        usb_packet = USBPacket.read(data)
        res = dir_specific[direction]["feed"].packet(usb_packet)
        if (res):
            message = load_msg(res)
            print(dir_specific[direction]["color"].format(
                  "#{:0>6.3f} {:r}".format(reltime, message)))
