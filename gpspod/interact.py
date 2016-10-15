#!/usr/bin/env python3

import protocol
import usb
import usb.util
import sys
import time


# import code
# code.interact(local=locals())

# Bus 003 Device 008: ID 1493:0020 Suunto
# find our device
dev = usb.core.find(idVendor=0x1493, idProduct=0x0020)

# was it found?
if dev is None:
    raise ValueError('Device not found')

# set the active configuration. With no arguments, the first
# configuration will be the active one
# dev.set_configuration()
# get an endpoint instance
for interface in dev.get_active_configuration():
    if dev.is_kernel_driver_active(interface.bInterfaceNumber):
        dev.detach_kernel_driver(interface.bInterfaceNumber)
        usb.util.claim_interface(dev, interface.bInterfaceNumber)

# set the active configuration. With no arguments, the first
# configuration will be the active one
dev.set_configuration()


cfg = dev.get_active_configuration()
intf = cfg[(0, 0)]
print("print cfg")
print(cfg)
print("print intf")
print(intf)

try:
    ret = dev.ctrl_transfer(bmRequestType=0x21,
                            bRequest=0x0a,
                            wIndex=1,
                            data_or_wLength=0)
    print(ret)
except:
    pass


# sys.exit(1)
feed = protocol.USBPacketFeed()
time.sleep(0.001)
# write_res = write(0x82, b"")
# write_res = dev.write(ep, b"", timeout=1000) #return bytes written
# print(write_res)

req = protocol.MsgDeviceInfoRequest()
packets = protocol.usbpacketizer(req)
print(packets)
for p in packets:
    write_res = dev.write(0x02, bytes(p), timeout=100)
    print(write_res)

read_res1 = dev.read(0x82, 64, timeout=100)
read_res2 = dev.read(0x82, 64, timeout=1000)
feed.packet(protocol.USBPacket.read(read_res1))
response = feed.packet(protocol.USBPacket.read(read_res2))
print(response)
msg = protocol.load_packet(response)
print(msg)


usb.util.release_interface(dev, intf)
