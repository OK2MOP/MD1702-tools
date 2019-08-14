# -*- coding: utf-8 -*-

from __future__ import print_function

import sys
from struct import *
from array import array
from DM1702_contact import contacts, contact

DATA_map = {
#    0x00: 'FW_info',
#    0x01: 'Meta',
    0x02: 0x02, #Calibration
    0x03: 0x16, 0x04: 0x24, 0x05: 0x04, 0x06: 0x45, 0x07: 0x0b, 0x08: 0x11,
    0x09: 0x01, 0x0a: 0x0a, 0x0b: 0x13, 0x0c: 0x12, 0x0d: 0x03, 0x0e: 0x06,
    0x0f: 0x17, 0x10: 0x18, 0x11: 0x19, 0x12: 0x1a, 0x13: 0x1b, 0x14: 0x1c,
    0x15: 0x1d, 0x16: 0x1e, 0x17: 0x1f, 0x18: 0x20, 0x19: 0x21, 0x1a: 0x22,
    0x1b: 0x23, 0x1c: 0x25, 0x1d: 0x26, 0x1e: 0x27, 0x1f: 0x28, 0x20: 0x29,
    0x21: 0x2a, 0x22: 0x2b, 0x23: 0x2c, 0x24: None, 0x25: 0x3f, 0x26: 0x40,
    0x27: 0x41, 0x28: 0x42, 0x29: 0x43, 0x2a: 0x44, 0x2b: 0x46, 0x2c: 0x47,
    0x2d: 0x48, 0x2e: 0x49, 0x2f: 0x4a, 0x30: 0x4b, 0x31: 0x4c, 0x32: 0x4d,
    0x33: 0x4e, 0x34: 0x4f, 0x35: 0x50, 0x36: 0x51, 0x37: 0x52, 0x38: 0x53,
    0x39: 0x54, 0x3a: 0x55, 0x3b: 0x56
}

DATA_chains = {
    #'Channel_names': [0x24, 0x4, 0x25, 0x26], #Broken in CPS
    'Channel_names': [0x24, 0x25, 0x26],
    'Channel_data': range(0x16, 0x23),
    'VFO_Channel_data': [0x23],
    'Scan_lists' : [0x13],
    'RX_lists' : [0x11, 0x12],
    'Systems' : [0x11],
    'Lone_worker' : [0x11],
    'Privacy' : [0x11],
    'Contact_meta' : [0xb],
    'Contact_data' : range(0x28,0x2d),
    'Message_templates' : [0xa], #Done implemening reading
    'Message_sent' : [0x9,0x33,0x34,0x35,0x36,0x37,0x38], # Done implementing - still not enough messages?
    'Message_received' : [0x8, 0x2d, 0x2e, 0x2f, 0x30, 0x31, 0x32], # Done implementing - still not enough messages?
    'Message_drafts' : [0x14], # Done implementing
    'Call_missed' : [0xe],
    'Call_answered' : [0xf],
    'Call_outgoing' : [0x10],
    'Buttons' : [0x27],
    'Zone_data': range(0x45,0x57),
    'Config' : [0x4],
    'GPS' : [0x4],
}

DATA_ranges = {
    #'Channel_names': [range(0x0, 0x1000), range(0x0, 0x7), range(0x000b, 0xfff), range(0x0, 0xfff)], #Broken data in CPS, maybe not in radio?
    'Channel_names': [range(0x0, 0xfff), range(0x0003, 0xfff), range(0x0, 0xfff)], #How it should be in radio?
    'Channel_data': [range(0x0, 0xfff)] * 0xd, # Fix: Probably not exactly this range!
    'VFO_Channel_data': [range(0xf9f, 0xfff)], # Done
    'Scan_lists' : [range(0x0, 0xfff)], # Probably to 0x721
    'RX_lists' : [range(0x0, 0x606), range(0x0, 0x73d)], # Probably done, but may be dynamic
    'Systems' : [range(0x606, 0x6ac)], #Data from 0x6a0
    'Lone_worker' : [range(0x700, 0x800)], #???
    'Privacy' : [range(0x800, 0xc00)], # Done
    'Contact_meta' : [range(0x0, 0xfff)],
    'Contact_data' : [range(0x0, 0xfff)] * 5, # Last ends at 0xB42?
    'Message_templates' : [range(0x0, 0xfff)], # In reality ends at 0xa24?
    'Message_sent' : [range(0x0, 0xf00), range(0x0,0xff0), range(0x0,0xff0), range(0x0,0xff0), range(0x0,0xff0), range(0x0,0xff0), range(0x0,0xff0)],
    'Message_received' : [range(0x0, 0xf00), range(0x0,0xff0), range(0x0,0xff0), range(0x0,0xff0), range(0x0,0xff0), range(0x0,0xff0), range(0x0,0xff0)],
    'Message_drafts' : [range(0x0, 0xf00)], # Done with buggy implementation, fix once FW is corrected
    'Call_missed' : [range(0x0, 0xfff)],
    'Call_answered' : [range(0x0, 0xfff)],
    'Call_outgoing' : [range(0x0, 0xfff)],
    'Buttons' : [range(0x0, 0xfff)], # Done, contains 0xff from 0x81e
    'Zone_data': [range(0x0, 0xf0c), range(0x0, 0xefc), range(0x0, 0xefc), range(0x0, 0xefc), range(0x0, 0xefc), range(0x0, 0xefc), range(0x0, 0xefc), range(0x0, 0xefc), range(0x0, 0xefc), range(0x0, 0xefc), range(0x0, 0xefc), range(0x0, 0xefc)], # Done
    'Config' : [range(0x0, 0x500)],# Done
    'GPS' : [range(0x500, 0x600)], # Done
}

class DM1702_util(object):
    @staticmethod
    def get_data_bitmap(data, inverted=False):
        odata = []
        bit = 0x1 if inverted else 0x0
        for c in data:
            if isinstance(c,str):
                c = ord(c)
            for j in range(7):
                odata.append(((c >> j) & 0x1 == bit))
        return odata

    @staticmethod
    def dtrim(data):
        last = len(data) - 1;
        while data[last] == 0xff :
            last -= 1
            if last == 0:
                return []
        return data[:(last+1)]

    @staticmethod
    def to_str(data, start, length, trim=False):
        sub = data[start:start+length-1]
        if trim:
            sub = DM1702_util.dtrim(sub)
        return "".join([chr(c) for c in sub])

class DM1702_messages(object):
    tmpl_len = 0x81
    bmap_len = 0x30
    idx_max  = 0x110
    data_start = 0x130
    data_skip = 0x110
    message_flags = { 1 : 'OK', 3 : 'unread' }

    def __init__(self, data, mtype, scan=False):
        self.messages = []
        self.mtype = mtype
        if mtype == 'templates':
            count=data[0]
            for i in range(0,count):
                start=0x10+i * self.tmpl_len
                #print("Messages: Data len=0x%06x, start = 0x%06x, count=%i" % (len(data), start, count))
                length = min(data[start] + 1, self.tmpl_len)
                self.messages += [ {'text' : DM1702_util.to_str(data, start+1, length)} ]
        else:
            used = DM1702_util.get_data_bitmap(data[0:self.bmap_len])
            if scan:
                indexes = range(1,int((len(data)-self.data_start)/self.data_skip) + 1)
                indexes = [x for x in indexes if x != 0xff]
            else:
                indexes = DM1702_util.dtrim(data[self.bmap_len:self.idx_max])
            #sys.stderr.write("Indexes: %s\n" %  str(indexes))
            for i in indexes:
                pos = self.data_start + (i-1) * self.data_skip
                if pos+self.data_skip > len(data) and i < 28:
                    sys.stderr.write("Message storage bug detected, trying to extract %s message %i anyway\n" %  (self.mtype, i))
                    pos = ((i%14) * self.data_skip) % DM1702_codeplug.sector_size
                d2 = data[pos:pos+self.data_skip]
                ##Code for byte strings which was originally used, just in case
                #flags, mlen, did_l, did_h, msg = unpack("<BB11xHB256s", d2)
                #dmr_id = did_l | (did_h << 16)
                #mlen -= 3 if mlen > 3 else 0
                #msg = msg[0:mlen] # 3 bytes for DMR ID
                flags = d2[0]
                if flags not in DM1702_messages.message_flags:
                    if not scan: sys.stderr.write("Broken %s message %i: type 0x%02x, skipping.\n" %  (self.mtype, i, flags))
                    continue
                mlen = d2[1]
                dmr_id = d2[13] | (d2[14] << 8) | (d2[15] << 16)
                mlen -= 3 if mlen > 3 else 0 # 3 bytes for DMR ID
                msg = DM1702_util.to_str(d2, 0x10, mlen)
                self.messages += [ {'text' : msg, 'call' : dmr_id, 'status': DM1702_messages.message_flags[flags]} ]

    def __repr__(self):
        return str(self.messages)

    def __get__(self, index):
        return self.messages[index]

    def append(self, message):
        self.messages.append(message)

    def remove(self, index):
        del self.messages[index]

    def __str__(self):
        str = ""
        for i in range(0,len(self.messages)):
            str += "MSG;%s;%i;%s;%s;%s\n" % (self.mtype, i, \
                        "%i" % self.messages[i]["call"] if "call" in self.messages[i] else "",\
                        self.messages[i]["status"] if "status" in self.messages[i] else "",\
                                      self.messages[i]["text"])
        return str

class DM1702_codeplug(object):
    sector_size = 1 << 12

    @staticmethod
    def get_data_map(data):
        results = {}
        for start in range(0, len(data), DM1702_codeplug.sector_size):
            mark = data[start+0xfff]
            if mark != 0xff and mark != 0x00:
                if (mark in results): sys.stderr.write("Duplicate mark %02x\n" % mark)
                results[mark] = int(start / DM1702_codeplug.sector_size)
        return results

    def __init__(self, data):
        self.data=[ord(x) for x in data] if isinstance(data[0],str) else data
        self.marks = self.get_data_map(self.data)

    def get_block(self, bid):
        #print("Get block id=0x%02x, start = 0x%06x, end = 0x%06x" % (bid, bid * self.sector_size, (bid+1) * self.sector_size))
        return self.data[bid * self.sector_size:(bid+1) * self.sector_size]

    def get_data(self, block_ids):
        chains = DATA_chains[block_ids]
        ranges = DATA_ranges[block_ids]
        assert len(ranges) == len(chains)
        data= []
        for i in range(0, len(ranges)):
            if chains[i] not in self.marks:
                if i == 0:
                    sys.stderr.write("Block with ID 0x%02x not found, returning empty data.\n" % chains[i])
                data += ([0xff] * (ranges[i][-1]-ranges[i][0]+1))
                break
            else:
                data += self.get_block(self.marks[chains[i]])[ranges[i][0]:ranges[i][-1]+1]
        #print("Get Data len=0x%06x, count=%i" % (len(data), len(ranges)))
        return data

    def get_messages(self, mtypes='all', deleted=False):
        result = {}
        if mtypes == 'all':
            mtypes = ['sent', 'received', 'drafts', 'templates' ]
        elif isinstance(mtypes, str):
            mtypes = [ mtypes ]
        for mtype in mtypes:
            mt2 = "Message_" + mtype
            if mt2 not in DATA_chains:
                sys.stderr.write("Unknown message type %s, skipping.\n" % mtype)
            elif DATA_chains[mt2][0] in self.marks:
                result[mtype] = DM1702_messages(self.get_data(mt2), mtype, deleted)
        return result
