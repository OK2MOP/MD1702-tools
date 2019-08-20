#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Copyright 2019 Pavel Moravec

# This tool is meant to manipulate codeplug of "Baofeng" DM-1702/DM-X
# radios to make it possible to bulk upload/download settings hard to
# edit in CPS.

import sys
from DM1702_codeplug import *
import os.path

verbose_err = True

def usage():
    print("""
Usage: md1702-codeplug <command> <arguments>

Read a data file and write it to a set of CSV files with given prefix
    md1702-codeplug export <codeplug.data> <export-prefix>

Read a data file and write it to a set of CSV files with given prefix
    md1702-codeplug import <import-prefix> <codeplug.data>

Read a raw codeplug file and write SMS messages to output CSV file
    md1702-codeplug readsms <codeplug.raw> <messages.csv>
    md1702-codeplug readallsms <codeplug.raw> <messages.csv>

Read contacts and append them to the existing codeplug (major CSV contact formats are supported)
    md1702-codeplug add contacts <input.data> <added.csv> <output.data>

Export CPS contacts to major CSV contact formats (use format list to display available formats)
    md1702-codeplug export contacts <input.data> <format> <output.csv>

Convert CPS contacts beteen major CSV contact formats (use format list to display output formats)
    md1702-codeplug convert contacts <input.csv> <format> <output.csv>

""")

def load_cps(infile):
    f = open(infile,"rb")
    data = f.read()
    f.close()
    return DM1702_codeplug(data)

def save_cps(outfile,cp):
    f = open(outfile,"wb")
    f.write(bytes(bytearray(cp.data)))
    f.close()

def save_csv(outfile, header, rows):
    of = open(outfile,"w")
    of.write("%s\n" % header)
    for k in rows:
        of.write(str(rows[k]))
    of.close()

def main():
#    try:
        if len(sys.argv) == 4:
            infile=sys.argv[2]
            outfile=sys.argv[3]
            if sys.argv[1] == 'export':
                print('Exporting codeplug')
                cp = load_cps(infile)
                print('Unfinished, does not work yet.')
            elif sys.argv[1] == 'import':
                print('Importing codeplug')
                print('Unfinished, does not work yet.')
            elif sys.argv[1] in ['readsms', 'readallsms']:
                print('Exporting SMS messages')
                cp = load_cps(infile)
                save_csv(outfile, DM1702_messages.csv_hdr(), cp.get_messages(deleted=(sys.argv[1] == 'readallsms')))
            else:
                usage()
        elif len(sys.argv) == 6:
            infile=sys.argv[3]
            outfile=sys.argv[5]
            if sys.argv[1] == 'convert':
                if sys.argv[2] == 'contacts':
                    print('Export of contacts')
                    contacts = DM1702_contacts()
                    contacts.load(infile)
                    contacts.save(outfile, sys.argv[4])
            elif sys.argv[1] == 'export':
                if sys.argv[2] == 'contacts':
                    print('Export of contacts')
                    cp = load_cps(infile)
                    cp.contacts.save(outfile, sys.argv[4])
            elif sys.argv[1] == 'add':
                csvfile=sys.argv[4]
                if sys.argv[2] == 'contacts':
                    print('Adding additional contacts')
                    cp = load_cps(infile)
                    cp.contacts.load(csvfile)
                    cp.save_contacts()
                    save_cps(outfile, cp)
            else:
                usage()
        else:
            usage()
#    except (RuntimeError, Exception) as e:
#        exc_type, exc_obj, exc_tb = sys.exc_info()
#        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
#        if verbose_err:
#            print(exc_type, fname, exc_tb.tb_lineno)
#        print(e)
#        exit(1)

if __name__ == '__main__':
    main()
