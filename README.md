# takeout-google-photos-export

Export Google Photos content from Google Takeout, properly importing metadata into the EXIF of the image files.

## Image Files

All image files (all those recognized by Python's Pillow libray, as well as HEIC) are converted to TIFF format. JPEG has support for EXIF data, but it doesn't have an alpha channel; Although PNG has an alpha channel, EXIF support in PNG is recent and less reliable than that of TIFF. TIFF is a high-quality (so I won't feel bad about converting everything to it) format with good support for (it's actually the source of the standard) EXIF. Therefore, I've chosen to move everything to TIFF.

## Video Files

MP4 files have competing standards for metadata storage, so if I'm writing something that an application is going to automatically import, I don't want to take a risk. I use the MOV format, which I can modify with `exiftool` just like I can images. I can convert MP4 files to MOV by just changing the container, and preserving the actual data. I do not support any formats other than MOV and MP4.
