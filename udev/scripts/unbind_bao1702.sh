#!/bin/sh
DRIVER="/sys/bus/usb/drivers/usblp"
LIST=`grep -l "PRODUCT=${PRODUCT}" "${DRIVER}"/*/uevent 2> /dev/null | cut -f 7 -d/`
IFS="
"
for USBID in $LIST ; do
    echo "$USBID" > /sys/bus/usb/drivers/usblp/unbind
done
