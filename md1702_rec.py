#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Copyright 2019 Pavel Moravec

from __future__ import print_function

import sys
import time

import usb.core
import os.path
from struct import *
from datetime import datetime

from DM1702_DFU import DM1702_DFU, Versions

md1702_vendor = 0x0483
md1702_product = 0x5780
verbose_err = True

# We are defining custom header for DMR recordings in modded DSD

Sector_state = {
    0xa5 : 'Used',
    0xa6 : 'Backup',
    0xff : 'Empty',
    0x00 : 'Default',
    0xffff : '???'
}

R_hdr = {
    'RX_TX_ST' : 0,
    'CH_GRP' : 1,
    'SRC_DMR_ID_L' : 2,
    'SRC_DMR_ID_H' : 3,
    'DST_DMR_ID_L' : 4,
    'DST_DMR_ID_H' : 5,
    'Zone': 6,
    'Zone_CH': 7,
    #'Unknown': 8, #Maybe encryption status?
    'Y_L' : 9,
    'Y_H' : 10,
    'M' : 11,
    'D' : 12,
    'H' : 13,
    'm' : 14,
    's' : 15,
    'DURATION': 16,
}

class recording(object):
    FILE_HEADER = b".dmr"
    FILE_EXT = ".dmr"
    #verbose = True
    verbose = False

    @staticmethod
    def get_size(dfu, block, warn=True):
        data=(dfu.upload_spi((block * 0x1000) + 0xffe, 2, crop=False, silent=True))
        if isinstance(b'',str):
            data=dfu.to_str(data)
        else:
            data=bytes(data)
        if (len(data) < 2):
            if warn:
                print("Invalid size of size information block %04x, size len: %i" % (block, len(data)))
            return 0
        return unpack("<H", data)[0]

    @staticmethod
    def get_recording_block(dfu, block):
        data=(dfu.upload_spi((block * 0x1000), 0x200 , crop=False, silent=True))
        if isinstance(b'',str):
            data=dfu.to_str(data)
        else:
            data=bytes(data)
        return data

    @staticmethod
    def sanity_check(od, next_blocks, valid_blocks):
        #if recording.verbose:
        if (od['M'] not in range(0,12) or od['D'] not in range(0,31) or od['H'] not in range(0,23)
            or od['m'] not in range(0,59) or od['s'] not in range(0,60)):
            return False;
        if od['Zone'] not in range(0,64) or od['DURATION'] < -1 or od['CH_GRP'] & 0x30 == 0x30:
            return False;
        for block in next_blocks:
            if block not in valid_blocks:
                return False
        #print(od)
        return True

    @staticmethod
    def get_recording_info(dfu, block, start, end, scan=False):
        valid_blocks = list(range(start, end))
        if block not in valid_blocks:
            return None
        else:
            valid_blocks.remove(block)
        data=recording.get_recording_block(dfu, block)
        rdata = unpack('<BBHBH11Bh', data[:0x14])
        od = {}
        result= {}
        for hdr in R_hdr:
            od[hdr] = rdata[R_hdr[hdr]]
        next_blocks = unpack('<240H', data[0x20:0x200])
        next_blocks = [value for value in next_blocks if value != 0xffff ]
        if scan and not recording.sanity_check(od, next_blocks, valid_blocks):
            return None
        if od['DURATION'] < -1: return None;
        next_blocks = [value for value in next_blocks if value in valid_blocks ]
        result = recording(od, block, next_blocks)
        #print(result)
        return result

    @staticmethod
    def get_block_if_exists(dfu, block, start, end):
        if recording.get_size(dfu, block) > 0:
            res=recording.get_recording_info(dfu,block, start, end, scan=True)
            return res
        return None

    def __init__(self, od, block, next_blocks) :
        self.block = block
        self.src_dmr_id  = (od['SRC_DMR_ID_H'] << 16) | od['SRC_DMR_ID_L']
        self.dst_dmr_id  = (od['DST_DMR_ID_H'] << 16) | od['DST_DMR_ID_L']
        try:
            self.date_time  = datetime(od['Y_H']*100+od['Y_L'],od['M'], od['D'], od['H'], od['m'], od['s'])
        except ValueError:
            sys.stderr.write('Broken date/time in recording in sector %04x: %s\n' % (block, od))
            self.date_time  = datetime.now()
        self.zone  = od['Zone']
        self.zone_ch  = od['Zone_CH']
        self.next_blocks  = next_blocks
        self.duration  = od['DURATION'] if od['DURATION'] < 0 else od['DURATION'] / 10.0
        self.mode  = "TX" if od['RX_TX_ST' ] & 0x1 else 'RX'
        self.valid  = (od['RX_TX_ST' ] & 0x10 == 0x10)
        self.bank  = 'B' if od['CH_GRP'] & 0x80 else 'A'
        self.type  = 'TG' if od['CH_GRP'] & 0x30 == 0x10 else ('ALL' if od['CH_GRP'] & 0x30 == 0x20 else 'P')

    def __str__(self):
        return "%s_%s_%i_%s%i_%s_Z%sC%i%s%s" % (self.date_time.strftime("%F_%H-%M-%S"), self.bank, self.src_dmr_id,
                                                '' if self.type == 'P' else self.type,
                                                 self.dst_dmr_id, self.mode,
                                                 self.zone, self.zone_ch,
                                                 (("_%.1fs") % self.duration) if self.duration > 0 else '',
                                                 '' if self.is_valid() else '_E')

    def is_valid(self):
        return self.valid and self.duration != 0.0 and abs(self.duration) >= 1.0

    def is_newer_than(self, date):
        return self.date_time > date

    def get_blocks(self):
        return self.next_blocks + [self.block]

    def read_data(self, dfu):
        s1 = self.get_size(dfu, self.block)
        crop = (s1 == 0xffff)
        if self.verbose:
            print("Block 0x%04x, len=0x%04x" % (self.block, s1))
        if s1 == 0:
            return b""
        data=(dfu.upload_spi((self.block * 0x1000) + 0x200, min(s1, 0xdfe), crop=False, silent=True))
        if isinstance(b'',str):
            data=dfu.to_str(data)
        else:
            data=bytearray(data)
        i = 0
        for i in range(len(self.next_blocks)):
            bl = self.next_blocks[i]
            s2 = self.get_size(dfu, bl)
            if self.verbose:
                print("  '-- Next block 0x%04x, len=0x%04x" % (bl,s2))
            crop = (s2 == 0xffff)
            data2=dfu.to_str(dfu.upload_spi((bl * 0x1000), min(s2, 0xffe), crop=crop, silent=True))
            if isinstance(b'',str):
                data2=dfu.to_str(data2)
            else:
                data2=bytes(data2)
            data += data2
        self.data = data
        return bytes(data)

    def save(self, out_f, header=True):
        if header:
            out_f.write(self.FILE_HEADER)
        out_f.write(self.data)

def get_state(dfu, block):
    state=dfu.upload_spi((block * 0x1000) + 0xfff, 1, crop=False, silent=True)[0]
    if isinstance(state,str):
        state = ord(state)
    if state not in Sector_state:
        state = Sector_state.get(state, 0xffff)
    return state

def get_allocated_map(dfu, block):
    data=dfu.to_str(dfu.upload_spi((block * 0x1000), 0xffe , crop=False, silent=True))
    odata = []
    for c in data:
        if isinstance(c,str):
            c = ord(c)
        for j in range(7):
            odata.append(((c >> j) & 0x1 == 0x0))
    return odata

def get_recording_starts(dfu, block):
    data=(dfu.upload_spi((block * 0x1000), 0xffe , crop=False, silent=True))
    if isinstance(b'',str):
        data=dfu.to_str(data)
    else:
        data=bytes(data)
    odata = unpack('<2047H', bytes(data))
    return [value for value in odata if value != 0xffff]

def upload_recs(dfu, prefix, start, end, newer_than=None, scan=False):
    fwversion = int(dfu.to_str(dfu.verify(Versions['FWVersion'])).split('.')[-1])
    sblock = start >> 12
    eblock = end >> 12
    if (sblock << 12) != start:
        raise Exception("Start position (0x%06x) not at sector boundary, something is wrong" % start)
    maxs=6
    if fwversion >= 22: maxs=9
    orecs = {}
    normal=[]
    print("Scanning recordings metadata")
    for i in range(3,maxs):
        state = get_state(dfu, sblock + i)
        if state == 0xa5 or state == 0xa6:
            recs = get_recording_starts(dfu,sblock+i)
            for rec in recs:
                if not rec in orecs:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                    orec = recording.get_recording_info(dfu, rec, sblock, eblock)
                    if orec is not None: orecs[rec] = orec
    if scan:
        for orec_id in orecs:
            normal += orecs[orec_id].get_blocks()
        print("\nScanning for missing records, this may take a lot of time")
        for block in range(maxs+sblock,eblock):
            if block in normal: continue
            sys.stdout.write('.')
            sys.stdout.flush()
            f_rec = recording.get_block_if_exists(dfu, block, sblock, eblock)
            if f_rec is not None:
                print('\nFound recording %s' % f_rec)
                orecs[block] = f_rec
    print("\nDumping records to files")
    for orec_id in orecs:
        if (orec_id > eblock):
            sys.stderr.write("Error: record block %x out of bounds, skipping\n" % orec_id)
        orec = orecs[orec_id]
        if orec.is_valid():
            fn = prefix + str(orec) + str(orec.FILE_EXT)
            if newer_than is None or orec.is_newer_than(newer_than):
                print("Saving record %s" % orec)
                orec.read_data(dfu)
                with open(fn, 'wb') as f:
                    orec.save(f)
                    f.close()
            else:
                print("Skipping old record %s" % orec)
        else:
            print("Skipping invalid record %s" % orec)
    return

def show_record_info(dfu, start):
    """Shows basic information about recordings."""
    #dfu.verbose = True
    fwversion = int(dfu.to_str(dfu.verify(Versions['FWVersion'])).split('.')[-1])
    sblock = start >> 12
    if (sblock << 12) != start:
        raise Exception("Start position (0x%06x) not at sector boundary, something is wrong" % start)
    for i in range(3):
        state = get_state(dfu, sblock + i)
        print('Bitmap sector %i:  %s (0x%02x)' % (i, Sector_state[state], state))
        if state == 0xa5 or state == 0x0:
            print('  \'-- Allocated:  %i' % get_allocated_map(dfu,sblock+i).count(True))
    maxs=6
    if fwversion >= 22: maxs=9
    for i in range(3,maxs):
        state = get_state(dfu, sblock + i)
        print('Mapping sector %i: %s (0x%02x)' % (i, Sector_state[state], state))
        if state == 0xa5 or state == 0xa6:
            recs = get_recording_starts(dfu,sblock+i)
            r = ""
            if len(recs): r = '(first at 0x%04x000)' % recs[0]
            print('  \'-- Recording count:  %i %s' % (len(recs), r))

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

class FileDFU(object):
    """Test class to allow simulation of recording reading on input file."""

    @staticmethod
    def to_str(data):
        if isinstance(data, bytes):
            return data;
        return DM1702_DFU.to_str(data)

    def __init__(self, filename, version, block0):
        with open(filename, 'rb') as f:
            self.data = f.read()
            block0 = int(block0, 16)
            if block0 > 0: # Pad file in the beginning
                empty_data = b'\0' * (0x1000 * block0)
                self.data = bytes(bytearray(empty_data) + self.data)
        self.version = int(version.split('.')[-1])

    def get_addrs(self):
        return (0x186000 if self.version > 14 else 0x154000), len(self.data)-1

    def upload_spi(self, address, length, delta=None, delay=None, crop=False, silent=True):
        return self.data[address:address+length]

    def verify(self, what):
        if (what == Versions['FWVersion']):
            return 'V02.02.0' + str(self.version)
        else:
            return '' #No other verify shoulr be called

def usage():
    print("""
Usage: md1702-rec <command> <arguments>

Read RAW DMR recordings from radio and write them to files with specified prefix.
    md1702-rec readrec <rec_prefix>

Read RAW DMR recordings from radio and write them to files with specified prefix (from specified time).
    md1702-rec readrec <rec_prefix> "mm/dd/yyyy HH:MM:SS" (with quotes)

Scan for all (even deleted) RAW DMR recordings in radio and write them to files with specified prefix.
    md1702-rec readallrec <rec_prefix>

Scan for all (even deleted) RAW DMR recordings in radio and write them to files with specified prefix.
    md1702-rec readallrec <rec_prefix> "mm/dd/yyyy HH:MM:SS" (with quotes)

Information about allocated sectors
    md1702-rec info

Reboot the device.
    md1702-rec reboot
""")

def main():
    try:
        if len(sys.argv) == 3 or len(sys.argv) == 4:
            if (len(sys.argv) == 4):
                try:
                    from dateutil.parser import parse
                    dt = parse(sys.argv[3]) #Better date parsing if available
                except (ImportError, ValueError):
                    try:
                        dt = datetime.strptime(sys.argv[3], '%m/%d/%Y %H:%M:%S')
                    except ValueError:
                        print("Use \"mm/dd/yyyy HH:MM:SS\" (with quotes) as the date string")
                        exit(2)
            else:
                dt = None

            if sys.argv[1].find("file:") == 0:
                version,mode,block0,filename=sys.argv[1][5:].split(':')
                dfu=FileDFU(filename, version, block0)
                start, end = dfu.get_addrs()
                scan = False
                if (mode == 'A'):
                    scan = True
                elif (mode == 'I'):
                    show_record_info(dfu, start);
                    return
                upload_recs(dfu, sys.argv[2], start, end, dt, scan)
                exit(0)

            import usb.core
            dfu = init_dfu()
            dfu.enter_spi_usb_mode()

            start, end = dfu.verify_addrs(Versions['Recordings'])

            if sys.argv[1] == 'readrec':
                print("Dumping recordings.")
                upload_recs(dfu, sys.argv[2], start, end, dt)

            elif sys.argv[1] == 'readallrec':
                print("Looking up recordings, be patient, it may take a while.")
                upload_recs(dfu, sys.argv[2], start, end, dt, scan=True)

            else:
                usage()

        elif len(sys.argv) == 2:
            if sys.argv[1] == 'info':
                import usb.core
                dfu = init_dfu()
                start, end = dfu.verify_addrs(Versions['Recordings'])
                dfu.enter_spi_usb_mode()
                show_record_info(dfu, start)

            elif sys.argv[1] == 'reboot':
                import usb.core
                dfu = init_dfu()
                dfu.reboot()

            else:
                usage()
        else:
            usage()
    except (RuntimeError, Exception) as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        if verbose_err:
            print(exc_type, fname, exc_tb.tb_lineno)
        print(e)
        exit(1)

if __name__ == '__main__':
    main()
