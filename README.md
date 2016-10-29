# GPS Track Pod
A pure Python client to interact with SUUNTO's [GPS Track Pod][suunto_pod].

Although the hardware created by SUUNTO is very nice, the software has significant limitations: It requires you to upload your tracks to the Movescount website before you can access them and internet connectivity is even required to change settings on the device. Combined with the fact that no linux version is provided I decided to write this command-line tool to interact with the device.

The efficient implementation in this client allows synchronizing tracks without copying all the data from the device. Moveslink spends about 6 minutes synchronizing all data, even if the only new track is just two minutes long. This client retrieves only the data necessary for that track (often taking less than 10 seconds). Other functionality, such as changing the settings is also provided.

## Usage
The client has been developed and tested on Ubuntu 14.04, to be able to access the device without requiring root access, place the [49-gpspod.rules][udevrules] in `/etc/udev/rules.d/`. The client requires Python 3 and has two dependencies [pyusb][pyusb] and [crcmod][crcmod], a [requirements.txt][requirements] file is available for easy installation.

To run the client one has to execute the module (so from a shell: `python3 -m gpspod`). I recommend making an alias for this, something like `alias gpspod='python3 -m gpspod`. Try `gpspod --help` for a list of available commands, they should be pretty self-explanatory.

I noticed that it takes considerable time for the device to become available for communication after it has been connected to an USB port. `gpspod device`  can be used to retrieve the version number of the device, after connecting to USB the first few commands may result in 'Resource Busy' or 'Permission Denied' errors, try a few more times and it should become available.

Typically, the following steps are used:
```
$gpspod device
Model: GpsPod, Serial: 8761994617001000, fw: 1.6.39.0 hw: 66.2.0.0 bsl: 1.4.3.0 
$gpspod status
Charge: 93%
$gpspod tracks
 0: 2016-10-25 10:35:42 distance:     0m, samples:     18, interval:  60s
 1: 2016-10-25 19:53:35 distance:   373m, samples:  81889, interval:  1s
 2: 2016-10-26 20:11:06 distance: 36073m, samples:   3427, interval:  1s
 3: 2016-10-27 06:11:14 distance: 36983m, samples:   3872, interval:  1s
$gpspod retrieve 2
Retrieving track  2, 3427 samples, writing to track_2016_10_26__20_11_06.gpx
Acquired the data in 3.57 seconds, writing gpx.
Lap adds waypoint: True, lap splits segments: True, all points: True.
Done creating gpx, wrote 489333 bytes to track_2016_10_26__20_11_06.gpx.
```

## Development & Architecture
For SUUNTO's watches, the [openambit][openambit] project provides an open-source alternative to Moveslink. However, this project does not support the GPS Pod. The [openambit][openambit] project provided me with a lot of information regarding the  communication protocol, hats off to them for their reverse-engineering work. There is a significant number of commands that is not shared with the ambit watches and the internal storage seems to be different as well.

To dissect the communication between the device and the official software, the USB packets were recorded using a virtual machine running Windows and a Linux host operating system to facilitate USB recording. The recorded communication was exported from Wireshark in PDML format. These recordings allowed development of the [protocol][protocolpy] code and provides insight into how we should interact with the device and allows disection of the messages. The processing of these logs is done by [debug][debugpy] and also offered by the debug command.

The filesystem, BPMEM.dat file, blocks and log entry parsing can be tested on an offline filesystem file (which can be created using the dump command). The parsing of this data is done with the code (mostly the structure & field definitions) from [pmem][pmempy]. Because all access operations to the 'filesystem' are done using standard Python indexing this allows using a backend that retrieves data on a need-to-know basis, which is provided in [device][devicepy].

The USB communication is contained to the [interact][interactpy] file. A special version of the communication class is available which records all communication and another one is available that facilitates replaying these recordings. Finally, the main entrypoint to the command-line tool is [\_\_main\_\_.py][mainpy]. Finally, the writer from [output][outputpy] is used to convert the data from the PMEM entries to a gpx file.


## Device
This internal storage is a (valid) FAT16 filesystem, with one file called BPMEM.dat on it. In this file (0x3c0000 bytes) I identified two separate blocks (`PMEMBlock`), these blocks contain (multiple) sub blocks that hold entries (`PMEMEntriesBlock`) these hold actual data samples. One block (`PMEMLogEntries`) contains an internal log detailing anything from USB connections to GPS status and battery voltages. The other block is (`PMEMTrackEntries`) holds the samples that contain the GPS position and velocity and the like, this block contains the tracks.

The `PMEMEntriesBlock`'s form a doubly linked list to each other, this means that after reading the start of the `PMEMBlock` we know where the first `PMEMEntriesBlock`, and after reading the start of that block we know where the next block of entries is located. This allows efficient retrieval of just the desired data.


## License
MIT License, see [LICENSE](LICENSE).

Copyright (c) 2016 Ivor Wanders

Ambit, Movescount, Moveslink and Suunto are registered trademarks of Suunto Oy, this project is in no way affiliated or endorsed by Suunto.

[suunto_pod]: http://www.suunto.com/en-GB/Products/PODs/Suunto-GPS-Track-POD/
[openambit]: https://github.com/openambitproject/openambit/
[udevrules]: blob/master/49-gpspod.rules
[pyusb]: https://walac.github.io/pyusb/
[crcmod]: https://pypi.python.org/pypi/crcmod
[requirements]: blob/master/requirements.txt
[protocolpy]: blob/master/gpspod/protocol.py
[pmempy]: blob/master/gpspod/pmem.py
[interactpy]: blob/master/gpspod/interact.py
[devicepy]: blob/master/gpspod/device.py
[debugpy]: blob/master/gpspod/debug.py
[mainpy]: blob/master/gpspod/__main__.py
[outputpy]: blob/master/gpspod/output.py
