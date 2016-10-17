"""
    The data request command is utilized to retrieve the filesystem.

    In the filesystem data:
        0x9e1c0 Always indicates the start of the internal log of events.
        0xffc40 Always indicates the start of the first log.

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

    But we know for sure that the file starts at 0xba00 in the disk image.


"""