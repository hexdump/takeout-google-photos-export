#!/usr/bin/env python

import click
from shutil import move
from os import mkdir
from sys import argv
from pathlib import Path

@click.command()
@click.option("-d", "--directory", required=True, type=click.Path())
@click.option("-s", "--size", default=512, type=int)
def main(directory, size):
    files = list(Path(directory).rglob("*"))

    json_files = []
    other_files = []

    for file in files:
        if file.suffix == ".json":
            json_files.append(file)
        else:
            other_files.append(file)

    for i in range(0, len(other_files), size):
        mkdir(f"section_{i}")
        for file in other_files[i: i + size]:
            move(file, f"section_{i}/.")
        
if __name__ == '__main__':
    main()
