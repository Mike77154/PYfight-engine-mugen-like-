# PYfight-engine-mugen-like-
WIP for making my own clone of mugen 


SOME USEFUL Byte structure:


´´´´




/*--| SFF file structure
|--------------------------------------------------*\
  Version 1.01
HEADER (512 bytes)
------
Bytes
00-11  "ElecbyteSpr\0" signature				[12]
12-15  1 verhi, 1 verlo, 1 verlo2, 1 verlo3			[04]
16-19  Number of groups						[04]
20-24  Number of images						[04]
24-27  File offset where first subfile is located		[04]
28-31  Size of subheader in bytes				[04]
32     Palette type (1=SPRPALTYPE_SHARED or 0=SPRPALTYPE_INDIV)	[01]
33-35  Blank; set to zero					[03]
36-511 Blank; can be used for comments				[476]

SUBFILEHEADER (32 bytes)
-------
Bytes
00-03 File offset where next subfile in the "linked list" is	[04] 
      located.  Null if last subfile

04-07 Subfile length (not including header)			[04]
      Length is 0 if it is a linked sprite
08-09 Image axis X coordinate					[02]
10-11 Image axis Y coordinate					[02]
12-13 Group number						[02]
14-15 Image number (in the group)				[02]
16-17 Index of previous copy of sprite (linked sprites only)	[02]
      This is the actual
18    True if palette is same as previous image			[01]
19-31 Blank; can be used for comments				[14]
32-   PCX graphic data. If palette data is available, it is the last
      768 bytes.
\*--------------------------------------------------------------------------*/

NOTES:
24bit, missed;


SFFv2 Header

+--------+------------------------------+------+
| Offset | Description                  | Size |
+--------+------------------------------+------+
|  +$00  | ElecbyteSpr signature        |  12  |
+--------+------------------------------+------+
|  +$0C  | VersionLo3                   |   1  |
+--------+------------------------------+------+
|  +$0D  | VersionLo2                   |   1  |
+--------+------------------------------+------+
|  +$0E  | VersionLo1                   |   1  |
+--------+------------------------------+------+
|  +$0F  | VersionHi                    |   1  |
+--------+------------------------------+------+
|  +$10  | ??? set to 0                 |  10  |
+--------+------------------------------+------+
|  +$1A  | Palette map offset           |   4  |
+--------+------------------------------+------+
|  +$1E  | ??? set to 0                 |   6  |
+--------+------------------------------+------+
|  +$24  | SpriteList offset            |   4  |
+--------+------------------------------+------+
|  +$28  | Number of sprites            |   4  |
+--------+------------------------------+------+
|  +$2C  | ??? set to 0x200             |   4  |
+--------+------------------------------+------+
|  +$30  | Number of palettes           |   4  |
+--------+------------------------------+------+
|  +$34  | Palette bank offset          |   4  |
+--------+------------------------------+------+
|  +$38  | OnDemand DataSize            |   4  | <- Palettes + SpritesData(OnDemand)
+--------+------------------------------+------+
|  +$3C  | OnDemand DataSize Total      |   4  | <- Header + PaletteMap + SpriteList + OnDemand DataSize
+--------+------------------------------+------+
|  +$40  | OnLoad DataSize              |   4  | <- SpritesData(OnLoad)
+--------+------------------------------+------+
|  +$44  | unused???                    | 444  |
+--------+------------------------------+------+



SpriteList Node Header

+--------+-----------------------+------+
| Offset | Description           | Size |
+--------+-----------------------+------+
|  +$00  | Sprite group          |   2  |
+--------+-----------------------+------+
|  +$02  | Sprite number         |   2  |
+--------+-----------------------+------+
|  +$04  | Sprite image width    |   2  |
+--------+-----------------------+------+
|  +$06  | Sprite image height   |   2  |
+--------+-----------------------+------+
|  +$08  | Sprite image Xaxis    |   2  |
+--------+-----------------------+------+
|  +$0A  | Sprite image Yaxis    |   2  |
+--------+-----------------------+------+
|  +$0C  | Sprite linked index   |   2  |
+--------+-----------------------+------+
|  +$0E  | Compression method    |   1  |
+--------+-----------------------+------+
|  +$0F  | Color depth           |   1  |
+--------+-----------------------+------+
|  +$10  | Offset to data*,**    |   4  |  see notes
+--------+-----------------------+------+
|  +$14  | Data length**         |   4  |  see notes
+--------+-----------------------+------+
|  +$18  | Palette number        |   2  |
+--------+-----------------------+------+
|  +$1A  | Load Mode             |   2  |
+--------+-----------------------+------+
 
Palette map:
+--------+-----------------------+------+
| Offset | Description           | Size |
+--------+-----------------------+------+
|  +$00  | Palette group         |   2  |
+--------+-----------------------+------+
|  +$02  | Palette number        |   2  |
+--------+-----------------------+------+
|  +$04  | Total of colors       |   4  |
+--------+-----------------------+------+
|  +$08  | Offset to data*       |   4  |  see notes
+--------+-----------------------+------+
|  +$0C  | Palette length        |   4  |
+--------+-----------------------+------+
 
NOTES:
-------
 *   To calcule effective file address:
     OnDemand:  (PaletteBank Offset + Offset to data)
     OnLoad:    (SpriteData Section Start Offset + Offset to data)

 **  Linked sprites has length 0, but the offset is
     the same of his parent;
 
Load Modes:
 OnDemand(default) - 0x00 (sprite.decompressonload=0)
 OnLoad            - 0x01 (sprite.decompressonload=1)

Compression Method:
 NONE  - 0x00
 ???   - 0x01
 RLE8  - 0x02
 RLE5  - 0x03
 LZ5   - 0x04

 
SFFv2 file structure:
------------------------------------

 +---------------------------------+
 | SFFv2 Header                    |
 +---------------------------------+
 | Palette Map, linear             |
 | 16bytes per map                 |
 +---------------------------------+
 | Sprite List, linear             |
 | 28bytes per node                |
 +---------------------------------+ PaletteBank Section
 | Palette bank, linear            |
 | size is 4*colors of current pal |
 +---------------------------------+ SpriteData Section
 | Sprite data OnLoad, linear      |
 +---------------------------------+
 | Sprite data OnDemand, linear    |
 +---------------------------------+






  
It is also important to note that the images are not saved in the PNG file they are turned into raw data and then compressed with algorithms.


/*--| SND file structure
|--------------------------------------------------*\
  Version 1.01
HEADER
------
Bytes
00-11  "ElecbyteSnd\0" signature				[12]
12-15  4 verhi, 4 verlo						[04]
16-19  Number of sounds						[04]
20-23  File offset where first subfile is located.		[04]
24-511 Blank; can be used for comments.				[488]

SUBFILEHEADER
-------
Bytes
00-03 File offset where next subfile in the linked list is	[04]
      located. Null if last subfile.
04-07 Subfile length (not including header.)			[04]
08-11 Group number						[04]
12-15 Sample number						[04]
08-   Sound data (WAV)

\*--------------------------------------------------------------------------*/


/*--| FNT file structure |--------------------------------------------------*\
/*
 * Very simple file format, formed by concatenating a pcx file and a text
 * file together and prepending a header.
 * May be optimized for size by stripping the text file of comments before
 * adding it to the .fnt file. Be sure text data comes last in the file.
 */

  Version 1.0
HEADER
------
Bytes
00-11  "ElecbyteFnt\0" signature                                         [12]
12-15  2 verhi, 2 verlo                                                  [04]
16-20  File offset where PCX data is located.                            [04]
20-23  Length of PCX data in bytes.                                      [04]
24-27  File offset where TEXT data is located.                           [04]
28-31  Length of TEXT data in bytes.                                     [04]
32-63  Blank; can be used for comments.                                  [40]




´´´´


License:

CC0, do whatever you want with this thing
