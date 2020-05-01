from absl import app
from PIL import Image
from typing import Iterable, Iterator, List, Set

import cv2
import difflib
import json
import logging
import numpy
import pytesseract


def read_frames(filename: str) -> Iterator[numpy.ndarray]:
    """Parses frames of the given video and returns the relevant region in grayscale."""
    cap = cv2.VideoCapture(filename)
    while True:
        ret, frame = cap.read()
        if not ret:
            break  # Video is over

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        yield gray[150:630, 635:1050]  # The region containing the items
    cap.release()


def parse_frame(frame: numpy.ndarray) -> Iterator[numpy.ndarray]:
    """Parses an individual frame and extracts item rows from the list."""
    # Detect the dashed lines and iterate over pairs of dashed lines
    # Last line has dashes after but first line doesn't have dashes before,
    # therefore we prepend the list with zero for the starting line.
    lines = [0] + list((frame[:, 0] < 200).nonzero()[0])
    for y1, y2 in zip(lines, lines[1:]):
        if not (40 < y2 - y1 < 60):
            continue  # skip lines that are too close or far
        # Cut slightly below and above the dashed line
        yield frame[y1 + 5:y2 - 5, :]


def parse_video(filename: str) -> List[numpy.ndarray]:
    """Parses a whole video and returns all the item rows found."""
    all_rows: List[numpy.ndarray] = []
    for i, frame in enumerate(read_frames(filename)):
        if i % 3 != 0:
            continue  # Only parse every third frame
        all_rows.extend(parse_frame(frame))
    return all_rows


def run_tesseract(item_rows: List[numpy.ndarray]) -> Set[str]:
    """Runs tesseract on the row images and returns list of unique items found."""
    # Concatenate all rows and send a single image to Tesseract (OCR)
    concat_rows = cv2.vconcat(item_rows)
    parsed_text = pytesseract.image_to_string(Image.fromarray(concat_rows))

    # Cleanup results a bit and try matching them again items using string distance
    return {t.strip().lower() for t in parsed_text.split('\n') if t}


def match_items(parsed_names: Iterable[str], item_db: Set[str]) -> Set[str]:
    """Matches a list of names against a database of items, finding best matches."""
    matched_items = set()
    for item in parsed_names:
        if item in item_db:
            # If item name exists is in the DB, add it as is
            matched_items.add(item)
            continue

        # Otherwise, try to find closest name in the DB witha cutoff
        matches = difflib.get_close_matches(item, item_db, n=1, cutoff=0.8)
        if not matches:
            logging.warning('No match found for %r', item)
            continue
        logging.info('Matched %r to %r', item, matches[0])
        matched_items.add(matches[0])  # type: ignore
    return matched_items


def scan_catalog(video_file: str) -> List[str]:
    """Scans a video of scrolling through a catalog and returns all items found."""
    item_rows = parse_video(video_file)
    item_names = run_tesseract(item_rows)

    item_db = set(json.load(open('items/items_en-US.json')))
    clean_names = match_items(item_names, item_db)
    return sorted(clean_names)


def main(argv):
    video_file = argv[1] if len(argv) > 1 else 'catalog3.mp4'
    all_items = scan_catalog(video_file)
    print('\n'.join(all_items))


if __name__ == "__main__":
    app.run(main)