#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Copyright 2019 Pavel Moravec

# This tool is meant to manipulate boot logo images from Baofeng DM-1702/DM-X
# radios to make it possible to create custom own boot logos. Please note
# that present firmware implementations have a bug where a line between light
# blue background and buttons is not drawn and remains with what was in boot
# logo until some editor widget with white background is used.

from PIL import Image
import os.path
import sys

# For now works only with the known DM-1702/DM-X display format. If needed,
# the following two values may have to be changed to reflect other radio
# display dimensions and 16-byte header

gfx_size = 160, 128
logo_hdr = B'\x02\xa0\x80\x00\x50\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

python_v2 = (sys.version.split('.')[0] == '2')

verbose_err = True

def usage():
    print("""
Usage: md1702-gfx <command> <arguments>

Read a Boot image from a file and write it to bootlogo image
    md1702-gfx toimage <bootlogo.bin> <bootlogo.png>

Read a bootlogo image and write it to Boot image
    md1702-gfx fromimage <bootlogo.png> <bootlogo.bin>

Read a bootlogo image and show it on screen
    md1702-gfx show <bootlogo.bin>

""")

def gfx_from_image(data):
    odata = bytearray()
    i = 0
    while i < len(data):
        if python_v2:
            rgb8 = ((ord(data[i]) & 0xe0) | ((ord(data[i+1]) & 0xe0) >> 3) | (ord(data[i+2]) >> 6))
        else:
            rgb8 = (((data[i]) & 0xe0) | (((data[i+1]) & 0xe0) >> 3) | ((data[i+2]) >> 6))
        i += 3
        if python_v2:
            odata += chr(rgb8)
        else:
            odata.append(rgb8)
    return bytes(odata)

def gfx_to_image(data):
    odata = bytearray()
    for b in data:
        if python_v2:
            b = ord(b)
        red = b & 0xe0
        if red == 0xe0:
            red = 0xff;
        else:
            red |= red >> 4

        green = (b << 3) & 0xe0
        if green == 0xe0:
            green = 0xff;
        else:
            green |= green >> 4

        blue = (b << 6) & 0xc0
        if blue == 0xc0:
            blue = 0xff;
        else:
            blue|= blue >> 4

        if python_v2:
            rgb = chr(red) + chr(green) + chr(blue)
            odata += rgb
        else:
            odata.append(red)
            odata.append(green)
            odata.append(blue)
    return bytes(odata)

def main():
    try:
        if len(sys.argv) == 4:
            infile=sys.argv[2]
            outfile=sys.argv[3]

            if sys.argv[1] == 'fromimage':
                hdrfile = infile + '.hdr'
                im = Image.open(infile)
                if im is None:
                    print("The image could not be opened")
                    return
                im.thumbnail(gfx_size)
                im=im.convert("RGB")
                hdr = None
                if os.path.isfile(hdrfile):
                    with open(infile + '.hdr', 'rb') as f:
                        hdr = f.read()
                        f.close()
                if hdr is None:
                    hdr = logo_hdr
                f = open(outfile, 'wb')
                f.write(hdr)
                data = gfx_from_image(im.tobytes())
                f.write(data)
                f.close()

            elif sys.argv[1] == 'toimage':
                with open(infile, 'rb') as f:
                    data = f.read()
                data1 = data[0:16]
                data2 = data[16:gfx_size[1] * gfx_size[0] + 16]
                if data1 != logo_hdr:
                    print("The image header has changed, proceed with caution")
                if len(data2) < gfx_size[1] * gfx_size[0]: # Accept larger image dumps
                    print("The image size does not match, probably a different model, giving up")
                    return
                f2 = open(outfile + '.hdr', 'wb')
                f2.write(data1)
                f2.close()
                data2 = gfx_to_image(data2)
                #im = Image.new("RGB", gfx_size, 0xffffff)
                im = Image.frombytes("RGB", gfx_size, data2)
                im.save(outfile)
            else:
                usage()
        elif len(sys.argv) == 3:
            if sys.argv[1] == 'show':
                with open(sys.argv[2], 'rb') as f:
                    data = f.read()
                data2 = data[16:gfx_size[1] * gfx_size[0] + 16]
                if len(data2) != gfx_size[1] * gfx_size[0]:
                    print("The image size does not match, probably a different model, giving up")
                    return
                im = Image.frombytes("RGB", gfx_size, gfx_to_image(data2))
                im.show()
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
