#!/usr/bin/env python3

import datetime
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import typing

from PIL import Image


CATALOGUE_ROOT = pathlib.Path("/Volumes/Media (Sapphire)/books")


Format = typing.Literal["PDF", "EPUB", "MOBI"]


class BookInfo(typing.TypedDict):
    title: str
    author: str
    series: str | None
    publication_date: datetime.date
    format: Format


class Dimensions(typing.TypedDict):
    width: int
    height: int


class Book(BookInfo):
    filename: str
    thumbnail: str
    thumbnail_dimensions: Dimensions
    tint_color: str


def get_format(path: pathlib.Path) -> Format:
    if path.suffix == ".epub":
        return "EPUB"
    elif path.suffix == ".mobi":
        return "MOBI"
    elif path.suffix == ".pdf":
        return "PDF"
    else:
        raise ValueError(f"Unrecognised path suffix! {path.suffix!r}")


def get_thumbnail(path: pathlib.Path) -> pathlib.Path:
    """
    Create a thumbnail for the file, and return the path to the
    newly-created thumbnail file.
    """
    tmp_dir = tempfile.mkdtemp()

    subprocess.check_call(
        ["qlmanage", "-t", str(path), "-s", "500", "-o", tmp_dir],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=5,
    )

    thumbnail_path = next(f for f in os.listdir(tmp_dir))

    return pathlib.Path(tmp_dir) / thumbnail_path


def get_dimensions(thumbnail: pathlib.Path) -> Dimensions:
    im = Image.open(thumbnail)
    return {'width': im.width, 'height': im.height}


def get_tint_color(thumbnail: pathlib.Path) -> str:
    """
    Get the tint color for the thumbnail.  Returns a hex string.
    """
    output = subprocess.check_output([
        'dominant_colours', str(thumbnail),  '--compared-to', '#ffffff', '--no-palette'
    ])

    return output.strip().decode("utf8")


def ask_for_book(path: pathlib.Path) -> Book:
    title = input("What’s the title of the book?\n> ")
    print("")
    author = input("Who’s the author?\n> ")
    print("")
    series = input("Is the book part of a series?\n> ") or None
    print("")
    publication_date = datetime.datetime.strptime(input("When was the book published?\n> "), "%Y-%m-%d").date()

    format = get_format(path)

    return {
        "title": title,
        "author": author,
        "series": series,
        "publication_date": publication_date,
        "publication_year": publication_date.year,
        "format": format,
    }


class DatetimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.date):
            return obj.isoformat()


if __name__ == "__main__":
    try:
        path = pathlib.Path(sys.argv[1])
    except IndexError:
        sys.exit(f"Usage: {__file__} PATH")

    if not path.exists():
        sys.exit("No such file!")

    book_info = ask_for_book(path)

    thumbnail_path = get_thumbnail(path)
    thumbnail_dimensions = get_dimensions(thumbnail_path)
    tint_color = get_tint_color(thumbnail_path)

    try:
        with open(CATALOGUE_ROOT / "metadata.js") as in_file:
            contents = in_file.read()

        existing_catalogue = json.loads(contents.strip().strip(';').replace('window.books = ', ''))
    except FileNotFoundError:
        existing_catalogue = []

    stem = pathlib.Path(book_info['author']) / f"{book_info['title']} ({book_info['publication_date'].year})"

    # Copy the file into place
    filename = f"{stem}.{book_info['format'].lower()}"
    assert not (CATALOGUE_ROOT / filename).exists()
    (CATALOGUE_ROOT / filename).parent.mkdir(exist_ok=True, parents=True)
    shutil.move(path, CATALOGUE_ROOT / filename)

    # Copy the thumbnail into place
    thumbnail = pathlib.Path(".thumbnails") / f"{filename}.png"
    assert not (CATALOGUE_ROOT / thumbnail).exists()
    (CATALOGUE_ROOT / thumbnail).parent.mkdir(exist_ok=True, parents=True)
    shutil.move(thumbnail_path, CATALOGUE_ROOT / thumbnail)

    existing_catalogue.append({
        **book_info,
        'filename': str(filename),
        'thumbnail': str(thumbnail),
        'thumbnail_dimensions': thumbnail_dimensions,
        'tint_color': tint_color,
    })

    js_string = f"window.books = {json.dumps(existing_catalogue, indent=2, sort_keys=True, cls=DatetimeEncoder)};\n"

    with open(CATALOGUE_ROOT / "metadata.js", "w") as out_file:
        out_file.write(js_string)
