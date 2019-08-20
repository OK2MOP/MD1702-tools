# MD1702 USB Tools #

by Pavel Moravec, OK2MOP

# Introduction #

This repository contains tools for working with the MD-1702 based radios
over USB. It is based on the reverse-engineered communication protocol and
can be used with Baofeng DM-1702 and DM-X radios (theoretically also with
DM-1703 and other radios sharing this codebase).

I have tried to make the tool similar to popular `md380-dfu` tool by Travis
Goodspeed, KK4VCZ. The `stm32-dfu` from his repository could be used if somebody
wants to switch the CPU to internal STM32 bootloader mode, but it is not
necessary.

As the radio is detected by Linux incorrectly as an USB lp port, the driver
must be removed for the device.

Client Tools:
* `md1702-dfu` reads and writes MD1702 codeplugs, firmware and time. Run it without
an argument to show help.
* `md1702-codeplug` allows you to import contacts to CPS and split CPS into several
CSV files which can be merged together with the CPS later to allow easier batch editing
* `md1702-gfx` allows you to convert the boot logo graphics into an image editable in
external tool and back, and to show the boot logo image extracted from the radio.
* `md1702-rec` allows you to extract RAW DMR audio files, which can be decoded using
a modified dsd code found in my repository
* `linux_remove_usblp.sh` calls script `udev/scripts/unbind_bao1702.sh` with sudo.

## Using md1702-rec ##
Clone and build patched dsd from https://github.com/OK2MOP/dsd/ to be used with the
recordings

```
md1702-rec readrec prefix # you may also add start date, e.g. "2019-01-02 22:00:11"
for i in prefix*.dmr ; do path_to_built_dsd/dsd -w $i.wav -r $i ; done
```

## Requirements: ##

* Python 2.7 or newer:
  http://www.python.org

* PyUSB 1.0:  (0.4 does not work.)
  https://github.com/pyusb/pyusb

* libusb 1.0: (0.4 does not work.)
  http://www.libusb.org/

Optionally, if you want to specify date on command line in other formats

* dateutil:
  https://github.com/dateutil/dateutil/

If you wish to manipulate the Boot logo graphics, you will also need

* pillow 1.1.4 or newer:
  https://python-pillow.org

This project should work across Linux, and should work on Mac OS, and Windows, but has
not been tested on them platforms.  A separate client,

### Additional steps for Linux-based installations with udev rules ###

```
# Clone the repository to MD1702-tools
cd MD1702-tools
sudo cp -r udev/* /etc/udev/
```
(The ```59-baofeng-1702.rules``` and ```unbind_bao1702.sh``` files are copied to /etc/udev/ in order to allow users to access the radio over USB without having to use sudo or root permissions and remove the driver. User should be a member of dialout group. If it is not, you may use ```sudo usermod -a -G dialout $USER``` to add your user, then log in and out).

If you do not wish to modify the udev, and you do not use any other usblp device, you can
prefix the `md1702-dfu` each time with ```sudo modprobe -r usblp;```

### Flash updated firmware for Linux-based installations ###

To update firmware, an unencrypted firmware image is required.

Turn on radio in DFU mode to begin firmware update with USB cable:
* insert cable into USB.
* connect cable to DM-X/DM-1702.
* power-on the device by turning volume knob, while holding '#' button. The device screen will
remain black and it will stay in firmware update mode.
* run the ```md1702_dfu.py``` in upgrade mode supplying the firmware.
