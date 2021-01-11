#!/usr/bin/env python3
#
# [photos.py]
#
# Google Photos Takeout organization tool.
# Copyright (C) 2020, Liam Schumm
#

# for command-line interface
import click
# for handling filesystem paths
from pathlib import Path
# for image conversion and hashing
from PIL import Image as PILImage
# for detecting what is and isn't a photo
from PIL import UnidentifiedImageError
# so we can dispatch to exiftool for
# TIFF manipulation
from subprocess import check_call, PIPE, CalledProcessError, DEVNULL
# so we can manipulate created/modified times
# for importing
from os import utime
# for hashing files
from hashlib import sha256
# for parsing Google's non-standard "formatted" timestamps
from dateutil.parser import parse as parse_date
from json import loads as parse_json
# for handling HEIC files
from pyheif import read as read_heic
# for exiting on error
from sys import exit
# for a progress bar
from tqdm import tqdm
# to copy files
from shutil import copyfile

LOG = ""

def log(message):
    global LOG
    LOG += message + "\n"

class Timestamp:
    def __init__(self, taken, created, modified):
        self.taken = parse_date(taken)
        self.created = parse_date(created)
        self.modified = parse_date(modified)

    def __eq__(self, other):
        if isinstance(other, Timestamp):
            if ((self.taken == other.taken)
                and (self.created == other.created)
                and (self.modified == other.modified)):
                return True
        return False
    
class Location:
    def __init__(self, latitude, longitude, altitude):
        self.latitude = latitude
        self.longitude = longitude
        self.altitude = altitude

    def __eq__(self, other):
        if isinstance(other, Location):
            if ((self.latitude == other.latitude)
                and (self.longitude == other.longitude)
                and (self.altitude == other.altitude)):
                return True
        return False

    def is_zero(self):
        return (self.latitude == 0) and (self.longitude == 0) and (self.altitude == 0)

class Metadatum:
    def __init__(self, path):
        self.path = path
        with open(path, "r") as f:
            self._data = parse_json(f.read())
        try:
            self.title = self._data["title"]
            self.timestamp = Timestamp(self._data["photoTakenTime"]["formatted"],
                                       self._data["creationTime"]["formatted"],
                                       self._data["modificationTime"]["formatted"])
            self.location = Location(self._data["geoDataExif"]["latitude"],
                                     self._data["geoDataExif"]["longitude"],
                                     self._data["geoDataExif"]["altitude"])
        except KeyError:
            raise ValueError(f"warning: insufficient metadata in JSON file {path}. ignoring...")

class Media:
    def __init__(self, path):
        self.path = path
        self.title = self.path.name
        with open(self.path, "rb") as f:
            sha = sha256()
            sha.update(f.read())
            self.shasum = sha.hexdigest()
        self.target_filename = self.shasum + self.path.suffix
        self.timestamp = None
        self.location = None

    def is_metadata_complete(self):
        return (self.timestamp is not None) and (self.location is not None)
        
    def apply_exif(self, path):
        if self.is_metadata_complete():
            # add our metadata
            try:
                command = ["exiftool", path, "-overwrite_original",
                           f"-DateTimeOriginal={self.timestamp.taken}",
                           f"-CreateDate={self.timestamp.created}",
                           f"-ModifyDate={self.timestamp.modified}"]
                if not self.location.is_zero():
                    command += [f"-GPSLatitude {self.location.latitude}",
                                f"-GPSLongitude {self.location.longitude}",
                                f"-GPSAltitude {self.location.altitude}"]
                    check_call(command, stdout=DEVNULL, stderr=DEVNULL)
                    utime(path, (self.timestamp.created.timestamp(),
                                 self.timestamp.modified.timestamp()))
            except CalledProcessError as e:
                print(e)
                log(f"error! could not set metadata on {path}!")
                exit(1)
        else:
            raise ValueError("metadata incomplete.")
        
    def save(self, target_directory):
        target_path = target_directory.joinpath(self.target_filename)
        if target_path.exists():
            log(f"warning: duplicate version of {self.path} detected! ignoring...")
        else:
            copy(self.path, target_path)

class Video(Media):
    def save(self, target_directory):
        if self.is_metadata_complete():
            target_path = target_directory.joinpath(self.target_filename).with_suffix(".mov")
            if self.path.suffix.lower() == ".mp4":
                # do a container transfer with no actual conversion.
                try:
                    check_call(["ffmpeg", "-i", self.path, "-c", "copy",
                                "-f", "mov", target_path, "-y"],
                               stdout=DEVNULL, stderr=DEVNULL)
                    # later, we're gonna copy the file at self.path to
                    # self.target_path, so this assignment nullifies that
                    # operation (since we don't want the original, non-MOV).
                    self.path = target_path
                except CalledProcessError as e:
                    print(e)
                    print(f"error! could not transfer container for {self.path}!")
                    exit(1)

            # we shouldn't be allowing this to be initialized
            # with something that isn't caught by now.
            assert self.path.suffix.lower() == ".mov"

            # copy the file over to the new location
            if self.path != target_path:
                shutil.copy(self.path, target_path)
#            with open(target_path, "wb") as destination:
#                with open(self.path, "rb") as source:
#                    destination.write(source.read())

            # set the metadata.
            self.apply_exif(target_path)
                    
class Image(Media):
    def save(self, target_directory):
        if self.path.suffix.lower() == ".heic":
            heic = read_heic(self.path)
            source = PILImage.frombytes(
                heic.mode, 
                heic.size, 
                heic.data,
                "raw",
                heic.mode,
                heic.stride,
            )
        else:
            source = PILImage.open(self.path, "r")

        target_path = target_directory.joinpath(self.shasum + '.tiff')
        
        if target_path.exists():
            log(f"warning: duplicate version of {self.path} detected! ignoring...")
        else:
            if self.is_metadata_complete():
                source.save(target_path, format='TIFF', quality=100)
                self.apply_exif(target_path)
                    
@click.command()
@click.option("-t", "--takeout-directory", type=Path, required=True, help="Google Takeout directory.")
@click.option("-o", "--output-directory", type=Path, required=True, help="Directory in which to put imported files.")
def main(takeout_directory, output_directory):
    metadata = []
    media = []
    
    for filename in takeout_directory.rglob("*"):
        # blindly suck in all JSON files.
        if filename.name.endswith('.json'):
#            try:
            metadata.append(Metadatum(filename))
            continue
#            except ValueError:
#                pass

        if filename.suffix.lower() == ".heic":
            media.append(Image(filename))

        # let's see if we can load it as an image file.
        # if we can, load it into the images list.
        try:
            if filename.suffix.lower() != ".heic":
                PILImage.open(filename)
                media.append(Image(filename))
                continue
        except UnidentifiedImageError:
            pass

        # i don't have support for all video file formats, so we
        # just check if the file is in the supported list.
        if filename.suffix.lower() in ['.mp4', '.mov']:
            media.append(Video(filename))
                
    # unify metadata and images
    with tqdm(media) as iterator:
        for item in iterator:
            matched  = False
            for metadatum in metadata:
                if item.title == metadatum.title:
                    item.timestamp = metadatum.timestamp
                    item.location = metadatum.location
                    item.save(output_directory)
                    matched = True
            if not matched:
                log(item.title + " not saved.")
            
    # print our accumulated log
    print(LOG)

if __name__ == "__main__":
    main()
