#!/usr/bin/env python2
# -*- coding: utf-8 -*-


# Copyright 2010, 2011 Michael Ossmann
# Copyright 2015 Travis Goodspeed
#
# This file was forked from Project Ubertooth as a DFU client for the
# TYT MD1702, an amateur radio for the DMR protocol on the UHF bands.
# This script implements a lot of poorly understood extensions unique
# to the MD1702.


from __future__ import print_function

import sys
import time

import usb.core

from DM1702_DFU import DM1702_DFU, Versions

# The tricky thing is that *TWO* different applications all show up
# as this same VID/PID pair.
#
# 1. The run-time DFU interface.
# 2. The bootloader at 0x08000000
md1702_vendor = 0x0483
md1702_product = 0x5780


# flash_config = 0x08004000
# application = 0x08008000

# bootloader= 0x08000000
# ram_offset = 0x20000000
# bootloader_size   = 0x00004000

def hexdump(string):
    """God awful hex dump function for testing taken from md380tools."""
    buf = ""
    i = 0
    for c in string:
        buf += "%02x" % c
        i += 1
        if i & 3 == 0:
            buf += " "
        if i & 0xf == 0:
            buf += "   "
        if i & 0x1f == 0:
            buf += "\n"

    print(buf)

def download_codeplug(dfu, data):
    return

def hexdump(string):
    """God awful hex dump function for testing."""
    buf = ""
    i = 0
    for c in string:
        buf += "%02x" % c
        i += 1
        if i & 3 == 0:
            buf += " "
        if i & 0xf == 0:
            buf += "   "
        if i & 0x1f == 0:
            buf += "\n"

    print(buf)


def upload_config(dfu, filename):
    """Dumps the config block at 0x8004000."""
    block_size = 0x4000

    f = None
    if filename is not None:
        f = open(filename, 'wb')

    print("Dumping config.")
    try:
        data = dfu.upload(0, block_size)
        if f is not None:
            f.write(data)
        else:
            hexdump(data)

    finally:
        print("Done.")

def display_versions(dfu):
    """Dumps the version information from radio."""
    for i in [ 'FWVersion', 'RefDate', 'DataFormat', 'GPSFormat', 'CPSFormat' ] :
        print("%s= %s"  % (i + (' ' * (12-len(i))), dfu.to_str(dfu.verify(Versions[i]))))

    for i in [ 'Voices', 'HZKFont', 'Recordings', 'Settings', 'Logo', 'Unknown1' ]:
        start, end = dfu.verify_addrs(Versions[i])
        print("%s= 0x%06x - 0x%06x "  % (i+ (' ' * (12-len(i))), start, end ))
    dfu.enter_spi_usb_mode()
    print('DeviceID    = 0x%s' % dfu.hd(dfu.verify(Versions['DeviceID'])))

def upload_firmware(dfu, filename):
    """Dumps the firmware at 0x8008000."""
    fw_addr = 0x4000 #Block after config
    fw_size = 0xF8000

    f = None
    if filename is not None:
        f = open(filename, 'wb')

    print("Dumping firmware.")
    try:
        data = dfu.upload(fw_addr, fw_size)
        if f is not None:
            f.write(data)
        else:
            hexdump(data)

    finally:
        f.close()

def upload(dfu, filename, start=0, end=0xFFFFFF, crop=True):
    """Dumps the SPI flash data for given range."""
    f = open(filename, 'wb')
    try:
        data = dfu.upload_spi(start, end-start+1, crop=crop)
        if f is not None:
            f.write(data)
        else:
            hexdump(data)

    finally:
        f.close()

def download(dfu, data, start, end):
    """Writes the SPI flash data for given range."""
    if (end-start+1 < len(data)):
        raise RuntimeError('Uploaded data size %i is larger than maximum allowed size %i' % (len(data), end-start+1))
    dfu.download_spi(start, data, end-start+1)

def init_dfu(alt=0, dfu_mode=True):
    """Initializes the DFU switching to USB program mode."""
    dev = usb.core.find(idVendor=md1702_vendor, idProduct=md1702_product)

    if dev is None:
        raise RuntimeError('Device not found')

    dfu = DM1702_DFU(dev, alt)
    if dfu_mode:
        dev.default_timeout = 3000
        try:
            dfu.enter_dfu_mode()
        except usb.core.USBError as e:
            if len(e.args) > 0 and e.args[0] == 'Pipe error':
                raise RuntimeError('Failed to enter DFU mode. Is the device running in normal mode?')
            else:
                raise e
    else:
        dev.default_timeout = 15000
    return dfu


def usage():
    print("""
Usage: md1702-dfu <command> <arguments>

Write a codeplug to the radio. Supported file types: RAW (NOT compatible with official CPS editor!)
    md1702-dfu writecp <codeplug.raw>

Read a firmware and write it to a file.
    md1702-dfu readfw <firmware.bin>

Read a RAW codeplug and write it to a file.
    md1702-dfu readcp <codeplug.raw>

Display device version information
    md1702-dfu versions

Read a voice data/HZK font/Boot image and write it to a file.
    md1702-dfu readvoice <voice.bin>
    md1702-dfu readfont <font.hzk>
    md1702-dfu readlogo <bootlogo.bin>

Write voice data/HZK font/Boot image and from a file (no checking of correct file type is done!).
    md1702-dfu writevoice <voice.bin>
    md1702-dfu writefont <font.hzk>
    md1702-dfu writelogo <bootlogo.bin>

Read a full SPI flash dump including a codeplug and write it to a file (very slow, ~1h)
    md1702-dfu readspi <spiflash.bin>

Dump the config block from Flash memory.
    md1702-dfu readcfg <cfg_filename.bin>

Set time and date on MD1702 to system time or specified time.
    md1702-dfu settime
    md1702-dfu settime "mm/dd/yyyy HH:MM:SS" (with quotes)

Close the bootloader session.
    md1702-dfu reboot

Upgrade to new firmware (not implemented):
    md1702-dfu upgrade foo.bin
""")


def main():
    try:
        if len(sys.argv) == 3:
            if sys.argv[1] == 'readcp':
                import usb.core
                dfu = init_dfu()
                dfu.enter_spi_usb_mode()
                print("Dumping RAW codeplug.")
                upload(dfu, sys.argv[2], dfu.cps_start, dfu.cps_end)

            if sys.argv[1] == 'readlogo':
                import usb.core
                dfu = init_dfu()
                print("Dumping Boot logo raw image.")
                start, end = dfu.verify_addrs(Versions['Logo']) #logo offsets are not available in SPI_USB mode
                dfu.enter_spi_usb_mode()
                upload(dfu, sys.argv[2], start, end, crop=False)

            if sys.argv[1] == 'readfont':
                import usb.core
                dfu = init_dfu()
                dfu.enter_spi_usb_mode()
                print("Dumping HZK font data.")
                start, end = dfu.verify_addrs(Versions['HZKFont'])
                upload(dfu, sys.argv[2], start, end)

            if sys.argv[1] == 'readvoice':
                import usb.core
                dfu = init_dfu()
                dfu.enter_spi_usb_mode()
                print("Dumping Voice data.")
                start, end = dfu.verify_addrs(Versions['Voices'])
                upload(dfu, sys.argv[2], start, end)

            if sys.argv[1] == 'readspi':
                import usb.core
                print("Dumping 16MB of RAW SPI flash data, please be patient, it takes an hour.")
                dfu = init_dfu()
                dfu.enter_spi_usb_mode()
                upload(dfu, sys.argv[2])
                print('Read complete')

            elif sys.argv[1] == 'readfw':
                import usb.core
                dfu = init_dfu()
                upload_firmware(dfu, sys.argv[2])

            elif sys.argv[1] == 'readcfg':
                import usb.core
                dfu = init_dfu()
                upload_config(dfu, sys.argv[2])

            elif sys.argv[1] == 'settime':
                import usb.core
                dfu = init_dfu(dfu_mode=False)
                dfu.set_time(sys.argv[2])

            elif sys.argv[1] == 'writelogo':
                import usb.core
                with open(sys.argv[2], 'rb') as f:
                    data = f.read()
                    dfu = init_dfu()
                    print("Setting Boot logo raw image.")
                    start, end = dfu.verify_addrs(Versions['Logo']) #logo offsets are not available in SPI_USB mode
                    dfu.enter_spi_usb_mode()
                    download(dfu, data, start, end)

            elif sys.argv[1] == 'writefont':
                import usb.core
                with open(sys.argv[2], 'rb') as f:
                    data = f.read()
                    dfu = init_dfu()
                    dfu.enter_spi_usb_mode()
                    print("Setting HZK font data.")
                    start, end = dfu.verify_addrs(Versions['HZKFont'])
                    download(dfu, data, start, end)

            elif sys.argv[1] == 'writevoice':
                import usb.core
                with open(sys.argv[2], 'rb') as f:
                    data = f.read()
                    dfu = init_dfu()
                    if data[:0x1000] == ('\xff' * 0x1000) and data[0x1016:0x101B] == '1.txt':
                        print('Stock voice data from MD, removing first 0x1000 bytes')
                        data = data[0x1000:]
                    dfu.enter_spi_usb_mode()
                    print("Setting Voice data.")
                    start, end = dfu.verify_addrs(Versions['Voices'])
                    download(dfu, data, start, end)

            if sys.argv[1] == 'writecp':
                with open(sys.argv[2], 'rb') as f:
                    data = f.read()
                    if len(data) == 0x3C000:
                        print('According to the size, this is official codeplug, which is presently not supported. Aborting.')
                        return
                    dfu = init_dfu()
                    dfu.enter_spi_usb_mode()
                    print("Writing RAW codeplug.")
                    download(dfu, data, dfu.cps_start, dfu.cps_end)

            elif sys.argv[1] == "upgrade":
                import usb.core
                with open(sys.argv[2], 'rb') as f:
                    data = f.read()
                    dfu = init_dfu(dfu_mode=False)
                    dfu.enter_bootloader_mode()
                    dfu.download_fw(data, sys.argv[2])

        elif len(sys.argv) == 2:
            if sys.argv[1] == 'settime':
                import usb.core
                dfu = init_dfu(dfu_mode=False)
                dfu.set_time()

            elif sys.argv[1] == 'reboot':
                import usb.core
                dfu = init_dfu()
                dfu.reboot()

            elif sys.argv[1] == 'versions':
                import usb.core
                dfu = init_dfu()
                display_versions(dfu)

            elif sys.argv[1] == "upgrade_check":
                import usb.core
                dfu = init_dfu(dfu_mode=False)
                dfu.enter_bootloader_mode()
                print ("Please turn off the radio now.")
            else:
                usage()
        else:
            usage()
    except RuntimeError as e:
        print(e.args[0])
        exit(1)
    except Exception as e:
        print(e)
        # print(dfu.get_status())
        exit(1)


if __name__ == '__main__':
    main()
