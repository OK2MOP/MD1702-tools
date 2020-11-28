# -*- coding: utf-8 -*-

from __future__ import print_function

import struct
from array import array
import sys
import time
import usb

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
        'PCMODE' : '\x02',
}

Models = [ 'DMR1702', 'DM1702S' ]

Deltas = {
        'DMR1702' : 40,
        'DM1702S' : 0x100
}

Statuses = {
        'None' : '\x00',
        'Error' : '\x02',
        'OK' : '\x06',
        'sPasswordSettingOK' : '\x50\x00\x00',
        'sWrongPassword' : '\x15',
        'sCorrectDevice' : 'DMR1702',
        'sCorrectDevice2' : 'DM1702S',
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
        'Unknown1': 8,
        'Recordings' : 9,
        'Settings' : 10,
        'CPSFormat' : 11,
        'Custom' : 13,
        'Logo' : 14,
        'CSVContacts' : 15,
    }

DFUComm = {
        'Ready' : 'R',
        'Model' : 'M',
        'Continue' : 'C',
        'OKContinue' : '\x06C',
        'Erase' : 'E',
        'EraseType' : '1',
        'Stage1' : '\x01',
        'Stage2' : '\x02',
        'OK' : '\x06',
        'Reboot' : '\x04',
        'ModelReply' : 'M\x01\x09',
        'VersionPrefix': 'MD1702-V',
        #'Supported' : [ 1 ], # supported versions of bootloader - disabled V2 as somebody has issues upgrading
        'Supported' : [ 1, 2 ], # supported versions of bootloader, re-enabled V1
    }


class DM1702_DFU(object):
    #verbose = True
    verbose = False
    sector_size = 1 << 12
    max_fw_size = 0xF7000
    min_known_fw_size = 0x9EF00
    delta = 0x40 # Maximum save block size is 64 bytes
    model = Models[0]

    @staticmethod
    def crc16_xmodem(data, crc=0x0000):
        msb = crc >> 8
        lsb = crc & 255
        for c in data:
            if (type(c) == type('c')): # Python 3
                c = ord(c)
            x = c ^ msb
            x ^= (x >> 4)
            msb = (lsb ^ (x >> 3) ^ (x << 4)) & 255
            lsb = (x ^ (x << 5)) & 255
        return chr(msb) + chr(lsb)

    @staticmethod
    def _wait():
        time.sleep(0.1)
        return True

    @staticmethod
    def fladdr2bytes(address):
        return [(address & 0xf0000) >> 12, (address >> 8) & 0xff, (address & 0xff)]

    @staticmethod
    def spiaddr2bytes(address):
        return [(address & 0xff), (address >> 8) & 0xff, (address >> 16) & 0xff]

    @staticmethod
    def dtrim(data):
        last = len(data) - 1;
        while data[last] == 0xff :
            last -= 1
            if last == 0:
                return []
        #print ("Dtrim final length: 0x%0x" % (last+1))
        return data[:(last+1)]

    @staticmethod
    def hd(data):
        import binascii
        return binascii.hexlify(data).decode('ascii')

    @staticmethod
    def to_str(data):
        if isinstance(data,str):
            return data
        elif isinstance(data,list) or isinstance(data,array):
            return ''.join([chr(x) for x in data])
        else:
            raise Exception("Cannot convert data to string")

    def __init__(self, device, alt):
        self.cps_start = 0x001000
        self.cps_end = 0x0c8fff

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
                from dateutil.parser import parse
                t = parse(tstr) #Better date parsing if available
            except (ImportError, ValueError):
                try:
                    t = datetime.strptime(tstr, '%m/%d/%Y %H:%M:%S')
                except ValueError:
                    raise Exception("Use \"mm/dd/yyyy HH:MM:SS\" (with quotes) as the date string")
        else:
            t = datetime.now()
        timedata = [ t.year & 0xff, (t.year & 0xff00) >> 8, t.month, t.day, t.hour, t.minute, t.second ]

        self.send_text(Requests['TIMESET'])
        data = self.read_reply()
        if data != Statuses['OK'] :
            raise Exception('Time settings mode setup failed')
        self.send_data(Requests['TIME'], [0, 0, 0], 7,  timedata) # no addr (0,0,0), l=7, data
        data = self.read_reply()
        if data != Statuses['OK'] :
            raise Exception('Time setting failed')

    def download_fw(self, in_data, name="firmware.bin"):
        if len(in_data) > self.max_fw_size or len(in_data) < self.min_known_fw_size:
            raise Exception("Firmware size %i is not between %i and %i bytes, sanity check failed" % (len(in_data), self.min_known_fw_size, self.max_fw_size))

        cf = "Firmware header sanity check failed, probably trying to flash encrypted firmware (use official app)"
        if isinstance(in_data, str):
            if in_data[3] != '\x20' or in_data[2] > '\x01' or in_data[7] != '\x08' or in_data[0xb] != '\x08' or in_data[0xf] != '\x08':
                raise Exception(cf)
        else:
            if in_data[3] != 0x20 or in_data[2] > 0x01 or in_data[7] != 0x08 or in_data[0xb] != 0x08 or in_data[0xf] != 0x08:
                raise Exception(cf)

        # Generate packet with metadata
        name=name.split('/')[-1]
        header=(B'\x00\xff%s\x00%i' % (name.encode(), len(in_data)))
        header += B'\x00' * (130-len(header))
        #raise Exception('Firmware upgrade is not implemented yet, some parts are missing');

        self.send_data(DFUComm['Erase'], [0, 0, 0] , 0)
        result = self.read_reply()
        if result != DFUComm['OK'] :
            raise Exception('Erase command failed')
        self.send_text(DFUComm['EraseType'])
        result = self.read_reply()
        if result != DFUComm['Continue'] :
            raise Exception('Erase mode selection 1 failed')
        self.send_text(DFUComm['Stage1'])
        result = self.read_reply()
        if result != DFUComm['Continue'] :
            raise Exception('Entering FW update stage 1 failed')
        self.send_text(header)
        self.send_text(self.crc16_xmodem(header[2:]))
        time.sleep(0.1)
        result = self.read_reply()
        if result != DFUComm['OKContinue'] :
            raise Exception('Sending file name failed')
        print('Sending file name succeeded, starting upgrade')
        block_id=1
        caddr=0x8000
        #print("Length of data before padding %i" % len(in_data))
        if len(in_data) % self.sector_size != 0:
            pad_l = self.sector_size - (len(in_data) % self.sector_size)
            if isinstance(in_data, str):
                in_data += '\xff' * pad_l
            else:
                i2 = bytearray(in_data)
                for i in range(0,pad_l):
                    i2.append(0xff)
                in_data = bytes(i2)
        #print("Length of data after padding %i" % len(in_data))
        while len(in_data) > 0:
            if isinstance(in_data, str):
                block=chr(block_id & 0xff) + chr((0xff-(block_id & 0xff))) + in_data[:1024]
            else:
                block=B"%c%c%s" % (block_id & 0xff, 0xff-(block_id & 0xff), in_data[:1024])
            csum16=self.crc16_xmodem(in_data[:1024])
            in_data = in_data[1024:]
            block_id += 1
            self.send_text(DFUComm['Stage2'])
            result = self.read_reply()
            if result != DFUComm['Continue'] :
                raise Exception('Update stage 2 failed')
            self.send_text(block)
            self.send_text(csum16)
            result = self.read_reply()
            if result != DFUComm['OK'] :
                raise Exception('Sending block %i failed' % block_id)
            if self.verbose:
                print("Download request at 0x%06x, l=%i" % (caddr, len(block)-2))
            else:
              sys.stdout.write('.')
              sys.stdout.flush()
        if not self.verbose:
            print('')
        self.reboot_fw()
        print('Upgrade finished, turn the device off and on normally')

    def set_timeout(self, timeout):
        self._device.default_timeout = timeout

    def reboot(self):
        self.send_text(Requests['NEXT'])
        return True

    def reboot_fw(self):
        self.send_text(DFUComm['Reboot'])
        data = self.read_reply()
        if data != DFUComm['Continue'] :
            raise Exception('DFU reboot failed')
        return True

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

    def upload_spi(self, address, length, delta=None, delay=None, crop=True, silent=False):
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
          elif (caddr % self.sector_size) == 0 and not silent:
              sys.stdout.write('.')
              sys.stdout.flush()
          if (address+length-caddr) < self.delta :
              l = address+length-caddr
          self.send_data(Requests['READ'],  self.spiaddr2bytes(caddr),l)
          code, addr, l2, d2 = self.read()
          if code != Requests['WRITE'] or l2 != l :
            raise Exception("Invalid reply for SPI upload: %c, len=%i (asked %i)" % (code, l2, l))
          data += d2
          caddr += l
          self.next_cmd()
          if delay is not None:
              time.sleep(delay)
        if not self.verbose and not silent:
            print('')
        if crop:
            return array('B',(self.dtrim(data)))
        else:
            return array('B',data)

    def download_spi(self, address, data, max_length=0, delta=None, delay=None, silent=False):
        length = len(data)
        if (max_length != 0 and max_length < length):
            raise Exception('Uploaded data size %i is larger than maximum allowed size %i' % (len(data), end-start+1))
        if self.verbose:
            print("Writing %i bytes of data to SPI at 0x%06x." % (length, address))
        caddr = address
        pos = 0
        if delta is None:
            l = self.delta
        else:
            l = delta
        while address + length > caddr :
          if self.verbose:
              print("Download request at 0x%06x, l=%i" % (caddr, l))
          elif (caddr % self.sector_size) == 0 and not silent:
              sys.stdout.write('.')
              sys.stdout.flush()
          if (address+length-caddr) < self.delta :
              l = address+length-caddr
          self.send_data(Requests['WRITE'],  self.spiaddr2bytes(caddr),l, data[pos:(pos+l)])
          code = self.read_reply()
          if code != Statuses['OK']:
            raise Exception("Invalid reply for SPI download: %c, len=%i" % (code, l))
          caddr += l
          pos += l
          if delay is not None:
              time.sleep(delay)
        if not self.verbose and not silent:
            print('')

    def get_cp_map(self):
        results = {}
        for start in range (self.cps_start, self.cps_end, self.sector_size):
            mark = self.upload_spi(start+0xfff, 1,1, crop=False, silent=True)
            if mark is not None and len(mark) > 0 and mark[0] != 0xff and mark[0] != 0x00:
                if (mark[0] in results): sys.stderr.write("Duplicate mark %02x\n", mark[0])
                results[mark[0]] = int(start / self.sector_size)
                assert int(start / self.sector_size) * self.sector_size == start
        return results

    def send_text(self, what):
        #if self.verbose:
        #    print("Send: %s" % what)
        self._ep.write(what)

    def send_data(self, command, addr, length=None, data=None):
        if isinstance(command, str):
            command = ord(command)
        addr.insert(0,command)
        if length is not None:
            addr.append(length % 0x100)
            if self.model == 'DM1702S':
                addr.append(length // 0x100)
        if not isinstance(addr, array):
            addr = array('B', addr)
        if data is not None:
            if not isinstance(data, array):
                data = array('B', data)
            data = addr + data
        else:
            data = addr
        #print("Send: %c, data: %s" % (chr(command), self.hd(data)))
        self._ep.write(data)

    def read_reply(self):
        data=self._device.read(self._ep2.bEndpointAddress,self._ep2.wMaxPacketSize)
        #print("Reply: %s" % self.hd(data))
        return self.to_str(data)

    def read(self, verify=False):
        data=self._device.read(self._ep2.bEndpointAddress,self._ep2.wMaxPacketSize)
        if (verify and len(data) < 3) or (not verify and len(data) < 5) or (not verify and self.model == 'DM1702S' and len(data) < 6):
            data2 = self._device.read(self._ep2.bEndpointAddress,self._ep2.wMaxPacketSize)
            data = data + data2
        if verify:
            dlen=data[2]
            cmd=data[0]
            adr=[0,0,0]
            data=data[3:]
        else:
            cmd=data[0]
            if self.model == 'DM1702S':
                adr=data[1:4]
                dlen=data[4] + (data[5] * 0x100)
                data=data[6:]
            else:
                adr=data[1:4]
                dlen=data[4]
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
        self.send_data(Requests['VERIFY'], [(addr >> 8), (addr & 0xff), rlength, (command)]);
        data=self.read(True)
        if data[0] != Requests['VERIFY'] :
            raise Exception('Invalid reply to VERIFY')
        self.next_cmd()
        if stringify:
            return ''.join([chr(x) for x in data[3]])
        else:
            return data[3]

    def verify_addrs(self, command):
        if command in  [ 6, 7, 8, 9, 0xa, 0xe, 0xf ]:
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
        if data[0] != Statuses['OK'] or not (RxData in Models) :
            raise Exception('Device detection error (status %i, device string %s)' % (ord(data[0]), RxData))
        else:
            self.model = RxData
            self.delta = Deltas [ self.model ]
        self.send_text(Requests['PCHECK'])
        data = self.read_reply()
        if data != Statuses['sPasswordSettingOK'] :
            raise Exception('Device is password protected, password mode is not implemented yet')
        self.send_text(Requests['SINFO'])
        data = self.read_reply()
        if data != Statuses['OK'] :
            raise Exception('System information mode setup failed')
        self.cps_start, self.cps_end = self.verify_addrs(Versions['Settings'])
        self.verify(Versions['Custom'], 0xa, 0x10)
        if self.verify(Versions['Custom'], 0xa, 0x20)[1] != 0xff:
            raise Exception('Verification of second datablock failed')

    def enter_spi_usb_mode(self):
        self.send_text(Requests['MSEL'])
        self.send_text(self.model)
        data = self.read_reply()
        if data != Statuses['OK'] :
            raise Exception('DMR1702 device check failed')
        self.send_text(Requests['PCMODE'])
        data = self.read_reply()
        if data != Statuses['sPCM8FF'] :
            raise Exception('DMR1702 PC Mode selection failed')
        self.next_cmd()

    def enter_bootloader_mode(self):
        self.send_text(DFUComm['Ready']);
        data = self.read_reply()
        if data != DFUComm['OK'] :
            raise Exception('Device not booted with "#" into bootloader mode')
        self.send_data(DFUComm['Model'], [0, 0, 0] , 1)
        data = self.read_reply()
        if data != DFUComm['ModelReply'] :
            raise Exception('Unknow reply to Model verification command')
        self.send_text(DFUComm['OK'])
        data = self.read_reply()
        if data[0:8] != DFUComm['VersionPrefix'] :
            raise Exception('Unknow version %s' % self.to_str(data))
        else:
            print('Bootloader (model) version: %s' % self.to_str(data))
        if int(data[8:]) not in DFUComm['Supported']:
            raise Exception('Not a known working bootloader (model) version, giving up')
