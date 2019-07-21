# MD1702 Boot logo format #
Logo is an image with 16 bytes of header, followed by 20480 bytes of the image
with RGB8 format (3/3/2 bits/subpixel). Header contains 02 A0 80 00 50 00 padded
with 00 to 16 bytes.

```
| Address || 00 01 02 03 | 04 05 06 07 | 08 09 0a 0b | 0c 0d 0e 0f | 
| --------||-------------|-------------|-------------|-------------|
|  0x0000 || 02 A0 80 00 │ 50 00 00 00 │ 00 00 00 00 │ 00 00 00 00 |
|  0x0010 ||                                                       |
|    ...  ||        Image data (1 Byte/pixel, RGB8 - 3/3/2)        |
|  0x5000 ||                                                       |
```
where 02 A0 is the header of the image, 80 00 should be image height (128 px) and 
50 00 the image width divided by 2 (80 px) - probably an error of firmware author.
