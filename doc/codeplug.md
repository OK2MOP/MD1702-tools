## Analysis of codeplug .data format compared to RAW codeplug ##
Block ID is stored in last byte of each sector, it must match ID of saved block in map. Blocks are 4096 (0x1000) bytes long.

### Special blocks, which are not written to radio normally are: ###
* Data block 0 - contains concatenated verify 10-byte data from FW blocks 0x0, 0x100 and 0x200 at 0x0, 0x10 and 0x20 padded with 0x0s
* Data block 1 - 16 * 0x00, then 0x100 bytes from internal flash block0, padded by 0x0s
* Data block 2 - contains radio calibration data
* Data block 36 - empty block (all 0s)

### Block IDs with specific meaning ###
* 0x00 - Non-synchronized blocks (data blocks 0, 1 and 36, see above), not downloaded to radio by default
* 0x01 - HIDDEN by default: 2-tone system and calls, probably unused (data block 9)
* 0x02 - Radio calibration data (data block 2, see above)
* 0x03 - Filled with zeroes (data block 13)
* 0x04 - Configuration data, starts with channel 373 name - _may be broken_ (data block 5), GPS systems
* 0x06 - HIDDEN by default: Phone systems (data block 14)
* 0x0a - Message templates (data block 10)
* 0x0b - Contacts indices for fast lookup - record allocation map, alphabetic and numeric index (data block 7)
* 0x11 - RX lists, systems, lone worker, privacy (data block 8)
* 0x12 - RX lists 2 (data block 12)
* 0x13 - Scan lists (data block 11)
* 0x16-0x22 - Channel data (data blocks 3, 15-26)
* 0x23 - VFO channel block (data block 27)
* 0x24-0x26 - Channel names (data blocks 4 - _may be broken_, 28-29)
* 0x27 - TX contact mapping to channel and buttons (data block 30)
* 0x28-0x2c - Contacts (data block 31-35)
* 0x3f - HIDDEN by default: 5-tone system (data block 37)
* 0x40 - HIDDEN by default: Broken analog contact lists, probably unused (data block 38)
* 0x41 - HIDDEN by default: ??? (data block 39)
* 0x42 - Filled with zeroes (data block 40)
* 0x43 - HIDDEN by default: Status lists, probably unused (data block 41)
* 0x44 - Filled with zeroes (data block 42)
* 0x45-0x56 - Zone definitions (data blocks 6, 43-59)

### Extra block IDs not stored in data files ###
* 0x08, 0x2d-0x32 - Physical block 0xC2 (0xC1 in codeplug memory area now) - received SMS messages
* 0x09, 0x33-0x38? - Physical block 0xC1 (0xC0 in codeplug memory area now) - sent SMS messages
* 0x0e - Missed calls
* 0x0f - Answered calls
* 0x10 - Outgoing calls
* 0x14 - Draft SMS messages - *broken, works as circular buffer if more than 12 messages*

### Unused block ID ranges ###
* 0x05
* 0x07
* 0x0c-0x0d
* 0x15
* 0x39-0x3e
* 0x56-0xa4
* 0xa5-0xa6 - used in Audio recordings section to mark an active block, probably not to be considered
* 0xa7-0xfe

### Contact Block indices - data block 7 ###
* x + 0x0000[2] - Contact count
* x + 0x0002[2] - Group contact count
* x + 0x0004[1] - All call contact present
* x + 0x0010[0xf0] - Allocation bitmap of indices
* x + 0x0100 - Indices 1 - alphabetic index
* x + 0x0740 - Indices 2 - CSS ID numeric index
