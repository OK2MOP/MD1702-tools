# -*- coding: utf-8 -*-

from __future__ import print_function

import struct
from array import array
import sys
import time
import usb


class Enumeration(object):
    def __init__(self, id, name):
        self._id = id
        self._name = name
        setattr(self.__class__, name, self)
        self.map[id] = self

    def __int__(self):
        return self.id

    def __repr__(self):
        return self.name

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @classmethod
    def create_from_map(cls):
        for id, name in cls.map.items():
            cls(id, name)


Requests = {
        'NEXT' : B'\x06',
        'READ' : 'R',
        'WRITE' : 'W',
        'TIME' : 'T',
        'GET' : 'G',
        'SET' : 'S',
        'VERIFY' : 'V',
        'CLEAR' : 'C',
        'SEARCH' : 'PSEARCH',
        'PCHECK' : 'PASSSTA',
        'PASSWORD_SEND' : 'PASSWORD',
        'SINFO' : 'SYSINFO',
        'TIMESET' : 'RTCITEM',
        'MSEL' : B'\xff\xff\xff\xff\x0c',
        'MODEL' : 'DMR1702',
        'PCMODE' : '\x02',
}

Statuses = {
        'None' : '\x00',
        'Error' : '\x02',
        'OK' : '\x06',
        'sPasswordSettingOK' : '\x50\x00\x00',
        'sWrongPassword' : '\x15',
        'sCorrectDevice' : 'DMR1702',
        'sPCM8FF' : '\xff' * 8,
    }


Versions = {
        'None' : 0,
        'FWVersion' : 1,
        'DeviceID' : 2,
        'RefDate' : 3,
        'DataFormat' : 4,
        'GPSFormat' : 5,
        'Voices' : 6,
        'HZKFont' : 7,
        'Recordings' : 9,
        'Settings' : 10,
        'CPSFormat' : 11,
        'Custom' : 13,
        'Logo' : 14,
    }


class State(Enumeration):
    map = {
        0: 'None',
        2: 'Error',
        6: 'OK',
    }


State.create_from_map()


class DFU(object):
    #verbose = True
    verbose = False
    cps_start = 0x001000
    cps_end = 0x0c8fff
    sector_size = 1 << 12
    delta = 0x40 # Maximum save block size is 64 bytes

    def __init__(self, device, alt):
        self._device = device
        device.set_configuration(1)
        # get an endpoint instance
        cfg = device.get_active_configuration()
        intf = cfg[(0,0)]
        ep = usb.util.find_descriptor(
            intf,
            # match the first OUT endpoint
            custom_match = \
            lambda e: \
                usb.util.endpoint_direction(e.bEndpointAddress) == \
                usb.util.ENDPOINT_OUT)
        
        assert ep is not None
        
        ep2 = usb.util.find_descriptor(
            intf,
            # match the first OUT endpoint
            custom_match = \
            lambda e: \
                usb.util.endpoint_direction(e.bEndpointAddress) == \
                usb.util.ENDPOINT_IN)
        
        assert ep2 is not None
        self._ep=ep
        self._ep2=ep2

    def set_time(self, tstr=None):
        from datetime import datetime
        if tstr is not None:
            try:
                t = datetime.strptime(tstr, '%m/%d/%Y %H:%M:%S')
            except ValueError:
                raise Exception("Usage: set_time \"mm/dd/yyyy HH:MM:SS\" (with quotes)")
                exit()
        else:
            t = datetime.now()
        timedata = [ 0, 0, 0, 7, t.year & 0xff, (t.year & 0xff00) >> 8, t.month, t.day, t.hour, t.minute, t.second ] # no addr (0,0,0), l=7, data

        self.send_text(Requests['TIMESET'])
        data = self.read_reply()
        if data != Statuses['OK'] :
            raise Exception('Time settings mode setup failed')
        self.send_data(Requests['TIME'], timedata)
        data = self.read_reply()
        if data != Statuses['OK'] :
            raise Exception('Time setting failed')

    def download(self, block_number, data):
        print('Download block %i' % block_number);
        # time.sleep(0.1);

        return True

    def md1702_reboot(self):
        self.send_text(Requests['NEXT'])
        return True

    def fladdr2bytes(self, address):
        return [(address & 0xf0000) >> 12, (address >> 8) & 0xff, (address & 0xff)]

    def spiaddr2bytes(self, address):
        return [(address & 0xff), (address >> 8) & 0xff, (address >> 16) & 0xff]

    def dtrim(self, data):
        last = len(data) - 1;
        while data[last] == 0xff : 
            last -= 1
            if last == 0:
                return []
        #print ("Dtrim final length: 0x%0x" % (last+1))
        return data[:(last+1)]

    def upload(self, address, length, delta=None, delay=None):
        if self.verbose:
            print("Fetching %i bytes of data from internal flash at 0x%06x." % (length, address))
        caddr = address
        if delta is None:
            l = self.delta
        else:
            l = delta
        data = []
        while address + length > caddr : 
          if self.verbose:
              print("Upload request at 0x%06x, l=%i" % (caddr, l))
          elif (caddr % self.sector_size) == 0:
              sys.stdout.write('.')
              sys.stdout.flush()
          if (address+length-caddr) < self.delta :
              l = address+length-caddr
          bdata=self.fladdr2bytes(caddr)
          self.send_data(Requests['GET'],  self.fladdr2bytes(caddr),l)
          code, addr, l2, d2 = self.read()
          if code != Requests['SET'] or l2 != l :
            raise Exception("Invalid reply for upload: %c, len=%i (asked %i)" % (code, l2, l))
          data += d2
          caddr += l
          self.next_cmd()
          if delay is not None:
              time.sleep(delay)
        if not self.verbose:
            print('')
        return array('B',(self.dtrim(data)))

    def upload_spi(self, address, length, delta=None, delay=None):
        if self.verbose:
            print("Fetching %i bytes of data from SPI at 0x%06x." % (length, address))
        caddr = address
        if delta is None:
            l = self.delta
        else:
            l = delta
        data = []
        while address + length > caddr : 
          if self.verbose:
              print("Upload request at 0x%06x, l=%i" % (caddr, l))
          elif (caddr % self.sector_size) == 0:
              sys.stdout.write('.')
              sys.stdout.flush()
          if (address+length-caddr) < self.delta :
              l = address+length-caddr
          bdata=self.fladdr2bytes(caddr)
          self.send_data(Requests['READ'],  self.spiaddr2bytes(caddr),l)
          code, addr, l2, d2 = self.read()
          if code != Requests['WRITE'] or l2 != l :
            raise Exception("Invalid reply for upload: %c, len=%i (asked %i)" % (code, l2, l))
          data += d2
          caddr += l
          self.next_cmd()
          if delay is not None:
              time.sleep(delay)
        if not self.verbose:
            print('')
        return array('B',(self.dtrim(data)))

    def send_text(self, what):
        #print("Send: %s" % what)
        self._ep.write(what)

    def send_data(self, command, data, length=None):
        if isinstance(command, str):
            command = ord(command)
        data.insert(0,command)
        if length is not None:
            data.append(length)
        if not isinstance(data, array):
            data = array('B', data)
        #print("Send: %c, data: %s" % (chr(command), self.hd(data)))
        self._ep.write(data)

    def hd(self, data):
        import binascii
        return binascii.hexlify(data).decode('ascii')

    def to_str(self, data):
        if isinstance(data,str):
            return data
        elif isinstance(data,list) or isinstance(data,array):
            return ''.join([chr(x) for x in data])
        else:
            raise Exception("Cannot convert data to string")

    def read_reply(self):
        data=self._device.read(self._ep2.bEndpointAddress,self._ep2.wMaxPacketSize)
        #print("Reply: %s" % self.hd(data))
        return self.to_str(data)

    def read(self, verify=False):
        data=self._device.read(self._ep2.bEndpointAddress,self._ep2.wMaxPacketSize)
        if (verify and len(data) < 3) or (not verify and len(data) < 5):
            data2 = self._device.read(self._ep2.bEndpointAddress,self._ep2.wMaxPacketSize)
            data = data + data2
        if verify:
            dlen=data[2]
            cmd=data[0]
            adr=[0,0,0]
            data=data[3:]
        else:
            dlen=data[4]
            cmd=data[0]
            adr=data[1:4]
            data=data[5:]
        while len(data) < dlen:
            data=data + self._device.read(self._ep2.bEndpointAddress,self._ep2.wMaxPacketSize)
        #print("Reply: %s" % self.hd(data))
        return (chr(cmd), adr, dlen, data)

    def next_cmd(self):
        self.send_text(Requests['NEXT'])
        data = self.read_reply()
        if data != Statuses['OK'] :
            raise Exception('Next command selection failed')

    def verify(self, command, rlength=0, addr=0, stringify=False):
        self.send_data(Requests['VERIFY'], [rlength, (addr & 0xff), (addr >> 8), (command)]); 
        data=self.read(True)
        if data[0] != Requests['VERIFY'] :
            raise Exception('Invalid reply to VERIFY')
        self.next_cmd()
        if stringify:
            return ''.join([chr(x) for x in data[3]])
        else:
            return data[3]

    def verify_addrs(self, command):
        if command in  [ 6, 7, 8, 9, 0xa, 0xe ]:
            resp = self.verify(command)
            if len(resp) == 8 :
                addresses=struct.unpack("<LL",resp)
                if self.verbose:
                    print("Addresses %i: 0x%06x - 0x%06x" % (command, addresses[0], addresses[1]) )
                return addresses;
            else:
                raise Exception('Verification of addresses failed, invalid length')
        else:
            raise Exception('Verification of addresses cannot be done on text entries')

    def enter_dfu_mode(self):
        self.send_text(Requests['SEARCH'])
        data = self.read_reply()
        RxData = data[1:]
        if data[0] != Statuses['OK'] or RxData != Statuses['sCorrectDevice'] :
            raise Exception('Device detection error (status %i, device string %s)' % (ord(data[0]), RxData))
        self.send_text(Requests['PCHECK'])
        data = self.read_reply()
        if data != Statuses['sPasswordSettingOK'] :
            raise Exception('Device is password protected, password mode is not implemented yet')
        self.send_text(Requests['SINFO'])
        data = self.read_reply()
        if data != Statuses['OK'] :
            raise Exception('System information mode setup failed')
        self.cps_start, self.cps_end = self.verify_addrs(Versions['Settings'])
        self.verify(Versions['Custom'], 0, 0xa10)
        if self.verify(Versions['Custom'], 0, 0xa20)[1] != 0xff:
            raise Exception('Verification of second datablock failed')

    def enter_spi_usb_mode(self):
        self.send_text(Requests['MSEL'])
        self.send_text(Requests['MODEL'])
        data = self.read_reply()
        if data != Statuses['OK'] :
            raise Exception('DMR1702 device check failed')
        self.send_text(Requests['PCMODE'])
        data = self.read_reply()
        if data != Statuses['sPCM8FF'] :
            raise Exception('DMR1702 PC Mode selection failed')
        self.next_cmd()

    def _wait(self):
        time.sleep(0.1)
