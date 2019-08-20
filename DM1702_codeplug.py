# -*- coding: utf-8 -*-

from __future__ import print_function

import sys
from struct import *
from array import array
from DM1702_contact import DM1702_contacts, DM1702_contact
from DM1702_data_maps import *

class DM1702_messages(object):
    tmpl_len = 0x81
    bmap_len = 0x30
    idx_max  = 0x110
    data_start = 0x130
    data_skip = 0x110
    message_flags = { 1 : 'OK', 3 : 'unread', 5: 'OK (group)', 7: 'unread (group)'}

    @staticmethod
    def csv_hdr():
        return "message_group,DMR_ID,callsign,status,message"

    def __init__(self, data, mtype, scan=False, contacts=None):
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
                m = {'text' : msg, 'status': DM1702_messages.message_flags[flags]}
                if dmr_id != 0:
                    m['call'] = dmr_id
                if contacts is not None and dmr_id != 0:
                    c = contacts[float(dmr_id) + (0.1 if flags & 0x4 else 0.0)]
                    if c is None: #Try the oposite record type in case of change
                        c = contacts[float(dmr_id) + (0.0 if flags & 0x4 else 0.1)]
                    if c is not None:
                        m['callsign' ] = str(c)
                self.messages.append(m) # += [ m ]

    def __repr__(self):
        return str(self.messages)

    def __getitem__(self, index):
        return self.messages[index]

    def append(self, message):
        self.messages.append(message)

    def __delitem__(self, index):
        del self.messages[index]

    def __str__(self):
        str = ""
        for i in range(0,len(self.messages)):
            str += '%s,%s,%s,%s,%s\n' % (self.mtype, \
                        "%i" % self.messages[i]["call"] if "call" in self.messages[i] else "",\
                        DM1702_util.csv_esc(self.messages[i]["callsign"]) if "callsign" in self.messages[i] else "",\
                        self.messages[i]["status"] if "status" in self.messages[i] else "",\
                        DM1702_util.csv_esc(self.messages[i]["text"]))
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
        self.data=[ord(x) for x in data] if isinstance(data[0],str) else [x for x in data]
        self.marks = self.get_data_map(self.data)
        self.channels = None
        self.zones = None
        self.scan_lists = None

        self.load_contacts()

    def get_block(self, bid):
        #print("Get block id=0x%02x, start = 0x%06x, end = 0x%06x" % (bid, bid * self.sector_size, (bid+1) * self.sector_size))
        return self.data[bid * self.sector_size:(bid+1) * self.sector_size]

    def set_block_data(self, bid, data, offset):
        start = bid * self.sector_size + offset
        #print("Set block id=0x%02x, start = 0x%06x, end = 0x%06x" % (bid, start, start+len(data)))
        assert len(self.data[start:start+len(data)]) == len(data)
        for i in range(0, len(data)):
            self.data[start +i] = data[i]
        #self.data[start:start+len(data)] == data

    def get_data_size(self, block_ids):
        chains = DATA_ranges[block_ids]
        total = 0
        for chain in chains:
            total += max(chain) - min(chain) + 1
        return total

    def get_data(self, block_ids):
        chains = DATA_chains[block_ids]
        ranges = DATA_ranges[block_ids]
        assert len(ranges) == len(chains)
        data= []
        for i in range(0, len(ranges)):
            if chains[i] not in self.marks:
                if i == 0:
                    sys.stderr.write("Block with ID 0x%02x not found, returning empty data.\n" % chains[i])
                #data += ([0xff] * (ranges[i][-1]-ranges[i][0]+1))
                data += ([0xff] * (max(ranges[i])-min(ranges[i])+1))
                break
            else:
                #data += self.get_block(self.marks[chains[i]])[ranges[i][0]:ranges[i][-1]+1]
                data += self.get_block(self.marks[chains[i]])[min(ranges[i]):max(ranges[i])+1]
        #print("Get Data len=0x%06x, count=%i" % (len(data), len(ranges)))
        return data

    def set_data(self, block_ids, data):
        chains = DATA_chains[block_ids]
        ranges = DATA_ranges[block_ids]
        assert len(ranges) == len(chains)

        if len(data) > 0 and isinstance(data[0], str): # Python2 normalization - move to data setting
            data = [ ord(x) for x in data ]

        skip = 0
        for i in range(0,len(ranges)):
            rlen = (max(ranges[i])-min(ranges[i])+1)
            rmin = min(ranges[i])
            if chains[i] not in self.marks:
                sys.stderr.write("Block with ID 0x%02x not found adding to the end (This won't work for CPS data file)!\n" % chains[i])
                self.data += [0xff] * (self.sector_size-1) + [chains[i]]
                self.marks = self.get_data_map(self.data)
            bid = self.marks[chains[i]]
            self.set_block_data(bid, data[skip:rlen+skip+1], rmin)
            skip += rlen

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
                result[mtype] = DM1702_messages(self.get_data(mt2), mtype, deleted, self.contacts)
        return result

    def get_cbc_map(self, mapping, ch_mode=True):
        data = []
        for i in range(0, int(len(mapping)/2)):
            if ch_mode:
                cidx = ((mapping[2*i] >> 4) << 8) | (mapping[2*i+1])
            else:
                cidx = mapping[2*i] | (mapping[2*i+1] << 8)

            if cidx == 0xffff or cidx == 0xfff:
                continue
            elif cidx == 0:
                cid = None
                contact = None
            elif cidx <= len(self.contacts.clist):
                #cid = float(self.contacts.clist[cidx-1])
                #cstr = str(self.contacts.clist[cidx-1])
                contact = self.contacts.clist[cidx-1]
            else:
                sys.stderr.write("Contact %c_%i does not exist, setting to None\n" % ('C' if ch_mode else 'B', i))
                contact = None
            #print ("C %i -> %s/%i @%i" % (i, cstr, cid, cidx))
            data.append(contact)
        return data

    def set_cbc_map(self, data, dlen, ch_mode=True):
        mapping = []
        idx=0
        for contact in data:
            idx += 1
            if contact is None:
                mapping += [0, 0]
                continue
            cid = float(contact)
            cpos = self.contacts.get_index(cid)
            if cpos is None:
                self.contacts.append(contact)
                cpos = self.contacts.get_index(cid) + 1 # Contacts numbered from 1
            cpos += 1 # Contacts numbered from 1
            if cpos >= self.contacts.max_internal_contacts:
                sys.stderr.write("Contact %s @ %c_%i placed beyond maximum allowed position, setting to None\n" % (str(contact),'C' if ch_mode else 'B', idx))
                mapping += [0, 0]

            if ch_mode:
                cidi = int(cid)
                mapping += [(cpos >> 8) << 4 | 0 if cidi == cid else 1, cpos & 0xff]
                # 1/0 indication seems not to be provided in CPS editor, only on radio?
            else:
                mapping += [cpos & 0xff, cpos >> 8]
        if len(mapping) < dlen:
            mapping += [0xff] * (dlen - len(mapping))
        elif dlen < len(mapping):
            sys.stderr.write("Warning: Contact mapping data too large (%i < %i)\n" % (dlen, len(mapping)))
        return mapping

    def load_contacts(self):
        cm = self.get_data('Contact_meta')
        cd = self.get_data('Contact_data')
        self.contacts = DM1702_contacts(cd, cm)

        self.btn_map = self.get_cbc_map(self.get_data('Buttons'), False)
        self.c_c_map = self.get_cbc_map(self.get_data('Channel_contact'), True)

    def save_contacts(self):
        cmap, cdata, skipped = self.contacts.export_CP()
        if skipped > 0:
            sys.stderr.write("Warning: Contact data too large, %i contacts ignored\n" % (skipped))
        btn=self.set_cbc_map(self.btn_map, self.get_data_size('Buttons'), False)
        cc=self.set_cbc_map(self.c_c_map, self.get_data_size('Channel_contact'), True)

        self.set_data('Contact_meta', cmap)
        self.set_data('Contact_data', cdata)
        self.set_data('Buttons', btn)
        self.set_data('Channel_contact', cc)

    def get_msg_templates(self):
        return self.get_messages('templates')['templates']

    def get_contacts(self):
        return self.contacts

