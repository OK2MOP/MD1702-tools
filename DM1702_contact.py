# -*- coding: utf-8 -*-

from __future__ import print_function

from struct import *
from array import array
import sys
from DM1702_data_maps import *

callTypes = {
    'private' : 0x3,
    'group' : 0x4,
    'all' : 0x5
}

MDCallNames = {
    0x3 : 'Private Call',
    0x4 : 'Group Call',
    0x5 : 'All Call'
}

callSorting = {
    'callSign' : 'S',
    'id' : 'I',
    'name' : 'N'
}

specialPrivate = {
    9990
}

contactFormats = {
    'CPS' : {
        # MD1702 internal XLS format for copy & paste
        'fields': ['No.', 'Call Alias' , 'Call Type', 'Call ID'],
        'quotechar' : None,
        'delimiter': ',' ,
        'seek' : None,
        'fixed' : {},
        'number': 'No.',
        'callSign' : 'Call Alias',
        'callTypes' : {'Private Call' : 3, 'Group Call' : 4, 'All Call': 5},
        'callType': 'Call Type',
        'id' : 'Call ID',
        'name': None,
        'country' : None
    },
    'dmrid' : {
        # https://ham-digital.org/user-by-call.php
        'fields': ['num', 'dmrid', 'callsign', 'name', 'country', 'ctry', 'dev_id'],
        'quotechar' : None,
        'delimiter': ';' ,
        'seek' : None,
        'fixed' : {},
        'number': 'num',
        'callSign' : 'callsign',
        'callTypes': None,
        'callType': None,
        'id' : 'dmrid',
        'name': 'name',
        'country' : 'ctry'
    },
    'bmgroup' : {
        # BrandMeister Talkgroups CSV export from https://brandmeister.network/?page=talkgroups
        'fields': ['Country','Talkgroup','Name',''],
        'quotechar' : '"',
        'delimiter': ',' ,
        'seek' : None,
        'fixed' : {},
        'number': None,
        'callSign' : 'Name',
        'callTypes': None,
        'callType': 4,
        'id' : 'Talkgroup',
        'name': None,
        'country' : None
    },
    'RT3S' : {
        # Downloads at https://www.ailunce.com/ResourceCenter
        'fields': ['Radio ID', 'CallSign', 'Name', 'NickName', 'City', 'State', 'Country'],
        'quotechar' : None,
        'delimiter': ',' ,
        'seek' : 3,
        'fixed' : {},
        'number': None,
        'callSign' : 'CallSign',
        'callTypes': None,
        'callType': None,
        'id' : 'Radio ID',
        'name': 'Name',
        'country' : 'Country'
    },
    'MD380CPS' : {
        # MD380 CPS format
        'fields': ['Contact Name', 'Call Type', 'Call ID', 'Call Receive Tone'],
        'quotechar' : None,
        'delimiter': ',' ,
        'seek' : None,
        'fixed' : {'Call Receive Tone' : 1 },
        'number': None,
        'callSign' : 'Contact Name',
        'callTypes' : {'2' : 3, '1' : 4, '3': 5},
        'callType': 'Call Type',
        'id' : 'Call ID',
        'name': None,
        'country' : None
    },

}

class DM1702_contact(object):
    sort_by = callSorting['callSign']
    csv_idx = 0

    def __init__(self, cid, call, name=None, country=None, ctype = None):
        self.call=call
        self.name=name
        self.cid=int(cid)
        self.country=country
        if isinstance(ctype, int):
            self.type = ctype
        elif ctype in callTypes:
            self.type= callTypes[ctype]
        else:
            # Try heuristics to determine type
            if self.cid == 16777215:
                self.type = callTypes['all']
            elif (self.cid > 5000 or self.cid < 4000) and self.cid < 1000000 \
                  and (self.cid not in specialPrivate):
                self.type = callTypes['group']
            else:
                self.type = callTypes['private']

    @staticmethod
    def set_sort(what=callSorting['callSign']):
        DM1702_contact.sort_by = what.upper()

#    @staticmethod
#    def csv_hdr():
#        csv_idx = 0
#        return "Radio ID,CallSign,Name,NickName,City,State,Country"
#
#    @staticmethod
#    def csv_dmrid_hdr():
#        csv_idx = 0
#        return "num;dmrid;callsign;name;country;ctry;dev_id"
#
#    @staticmethod
#    def cps_csv_hdr():
#        csv_idx = 0
#        return "No.,Call Alias,Call Type,Call ID"
#
    @staticmethod
    def from_MD_record(data):
        call, tcid = unpack('<2x16sxL3x', data)
        call = call.decode().rstrip('\x00')
        cid = tcid & 0xffffff
        ctype = (tcid >> 24) & 0xf
        return DM1702_contact(cid, call, ctype = ctype)

    # This will be probably slow :-(
    def cmp(self, other):
        if DM1702_contact.sort_by == 'N' :
            s1 = self.name
            s2 = other.name
        elif DM1702_contact.sort_by == 'I' :
            s1 = self.cid
            s2 = other.cid
        else:
            s1 = "%s%i" % (self.country, self.cid)
            s2 = "%s%i" % (other.country, other.cid)
        return -1 if s1 < s2 else (1 if s1 > s2  else  0)

    def __str__(self):
        return self.call

    def __int__(self):
        return self.cid

    def __lt__(self, other):
        return self.cmp(other) < 0

#    def __gt__(self, other):
#        return self.cmp(other) > 0
#
    def __eq__(self, other):
        if isinstance(other, str):
            s1 = str(self)
        elif isinstance(other, int):
            s1 = int(self)
        else:
            return self.cid == other.cid and self.call == other.call and self.type == other.type
        return s1 == other

    def to_MD_record(self):
        return pack('<2s16scL3s', b'\xff\xff', self.call[:16] if b"" == "" else bytes(self.call[:16],"ascii"),
                 b'\xff', (self.type << 24) | self.cid, b'\xff\xff\xff')

    def to_csv(self):
        return ("%i,%s,%s,,,,%s" % (self.cid, self.call,
                                    self.name if self.name is not None else "",
                                    self.country if self.country is not None else "")
               )

    def to_dmrid_csv(self):
        DM1702_contact.csv_idx += 1
        return ("%i;%i;%s;%s;;%s;" % (DM1702_contact.csv_idx, self.cid, self.call,
                                    self.name if self.name is not None else "",
                                    self.country if self.country is not None else "")
               )

    def to_cps_csv(self):
        DM1702_contact.csv_idx += 1
        return ("%i,%s,%s,%i" % (self.csv_idx, self.call, MDCallNames[self.type], self.cid))

    def __repr__(self):
        return repr({ 'id' : self.cid, 'call' : self.call })

class DM1702_contacts(object):
    def __init__(self, data=None):
        self.clist = []
        self.index = 0
        self.str_map = {}
        self.int_map = {}

    def append(self, DM1702_contact):
        idx = len(self.clist)
        self.clist.append(DM1702_contact)
        self.str_map[str(DM1702_contact)] = self.int_map[int(DM1702_contact)] = idx

    def sort(self, by=None):
        self.str_map = {}
        self.int_map = {}
        if by is not None: DM1702_contact.set_sort(by)
        self.clist.sort()
        for idx in range(0,len(self.clist)) :
            ct = self.clist[idx]
            self.str_map[str(ct)] = self.int_map[int(ct)] = idx

    def load(self, infile, ftype="auto"):
        import csv
        with open(infile, 'r') as f:
            if ftype is "auto":
                l=f.readline()
                sep = ';' if ';' in l else (',' if ',' in l else '@')
                f.seek(0)
                for fmt in contactFormats:
                    if contactFormats[fmt]['callSign'] in l and \
                       contactFormats[fmt]['id'] in l and \
                       contactFormats[fmt]['delimiter'] == sep:
                       sys.stderr.write("Contact format %s detected\n" % fmt)
                       ftype = fmt
                       if contactFormats[fmt]['seek'] is not None and l.index(contactFormats[fmt]['fields'][0]) != 0:
                           f.seek(contactFormats[fmt]['seek'])
                       break
            if ftype is "auto":
                raise Exception('Input contact file format not recognized')
            cf = contactFormats[fmt]
            csv_reader = csv.DictReader(f, delimiter=sep)
            for row in csv_reader:
                #print(row)
                cs=row[cf['callSign']]
                cid=row[cf['id']]
                calltype = name = country = None
                if cf['callType'] is not None:
                    if cf['callType'] in row:
                        calltype=row[cf['callType']]
                    elif isinstance(cf['callType'], int):
                        calltype = cf['callType']
                if calltype == '':
                    calltype = None
                if isinstance(cf['callTypes'], dict) and calltype in cf['callTypes']:
                    calltype = cf['callTypes'][calltype]
                if cf['name'] is not None and cf['name'] in row and row[cf['name']] != '':
                    name = row[cf['name']]
                if cf['country'] is not None and cf['country'] in row and row[cf['country']] != '':
                    country = row[cf['country']]
                self.append(DM1702_contact(cid, cs, name, country, calltype))

    def save(self, outfile, ftype):
        import csv
        if ftype not in contactFormats:
            raise Exception('Output contact file format not recognized')
        cf = contactFormats[ftype]
        ct = None
        if isinstance(cf['callTypes'], dict):
            ct = {}
            for (k,v) in cf['callTypes'].items(): ct[v] = k
        with open(outfile, 'w') as f:
            if cf['quotechar'] is None:
                writer = csv.DictWriter(f, fieldnames=cf['fields'], delimiter=cf['delimiter'])
            else:
                writer = csv.DictWriter(f, fieldnames=cf['fields'], delimiter=cf['delimiter'], quotechar=cf['quotechar'])
            writer.writeheader()
            i = 1
            for item in self.clist:
                row = dict(cf['fixed'])
                if cf['number'] is not None:
                    row[cf['number']] = i
                    i += 1
                if cf['callSign'] is not None: row[cf['callSign']] = item.call
                if cf['id'] is not None: row[cf['id']] = item.cid
                if cf['name'] is not None: row[cf['name']] = item.name
                if cf['country'] is not None: row[cf['country']] = item.country
                if isinstance(cf['callType'], str) and ct is not None and item.type in ct:
                    row[cf['callType']] = ct[item.type]
                writer.writerow(row)

    def __repr__(self):
        return repr(self.clist)
