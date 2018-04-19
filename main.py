"""
Extracts strips of pixels from frames in a movie
"""
import argparse
import os
import json
import math
import subprocess
from PIL import Image
from multiprocessing import Pool

FRAME_FILE_NAME = 'frame_%d.png'

# where to write each frame of the video for later processing
SCRATCH_DIR_NAME = 'scratch'

POOL_SIZE = 8  # Number of parallel processes to use for extraction


def ensure_dir(name):
    if not os.path.exists(name):
        os.makedirs(name)


def get_strip(sampleType, filename):
    """Extract the strip from an image file"""
    i = Image.open(filename)

    location = sampleType['location']
    sampleSize =  sampleType['sampleSize']

    bbox = None
    if sampleType['flipSample']:
        ySampleLoc = math.floor(i.height * location)
        bbox = (0, ySampleLoc, i.width, ySampleLoc + sampleSize)
    else:
        xSampleLoc = math.floor(i.width * location)
        bbox = (xSampleLoc, 0, xSampleLoc + sampleSize, i.height)

    return i.crop(bbox)


def clear_scratch(dir):
    """Delete existing frames in a directory."""
    for f in os.listdir(dir):
        if f.endswith(".png"):
            os.remove(os.path.join(dir, f))


def extract_frames(src, outFile, fromTime, toTime=None):
    """Extract all frames between two times from a video."""

    # Command line injections all over the place :)
    command = [
        'ffmpeg',
        '-hide_banner',
        '-i',
        src,
        "-ss",
        fromTime]

    if (toTime):
        command.append('-to')
        command.append(toTime)

    command.append(outFile)

    with open(os.devnull, 'w') as f:
        subprocess.call(command, stdout=f, stderr=f)


def _do_create_strip(args):
    print(args['i'])
    return get_strip(args['sampleType'], args['source'] % args['i'])


def create_strip(sampleType, source):
    """Build up the strip from the extracted frames"""
    i = 1
    while True:
        file = source % i
        if not os.path.isfile(file):
            break
        i = i + 1

    with Pool(POOL_SIZE) as p:
        data = p.map(_do_create_strip, [
                     {'i': x, 'sampleType': sampleType, 'source': source} for x in range(1, i)])

    sampleSize = sampleType['sampleSize']

    if sampleType['flipSample']:
        out_img = Image.new('RGB', (data[0].width, len(data) * sampleSize))
        i = 0
        for img in data:
            out_img.paste(img, (0, i * sampleSize))
            i = i + 1
        return out_img
    else:
        out_img = Image.new('RGB', (len(data) * sampleSize, data[0].height))
        i = 0
        for img in data:
            out_img.paste(img, (i * sampleSize, 0))
            i = i + 1
        return out_img


def extract_and_create_strip(sampleType, movie, frameOut, outFile, start, end, skipExtract=False):
    """Extract frames, the convert to strip"""
    print("Processing from {0} — {1}".format(start, end))
    frameFileNames = os.path.join(frameOut, FRAME_FILE_NAME)

    if not skipExtract:
        print('Extractring Frames')
        extract_frames(
            movie,
            frameFileNames,
            start,
            end)

    print('Creating strip')
    strip = create_strip(sampleType, frameFileNames)
    strip.save(outFile)


def main():
    parser = argparse.ArgumentParser(
        description='Sample a column or row from each frame in a video.')

    parser.add_argument(
        'video',
        help='Video file to process')

    parser.add_argument(
        '--out',
        dest='out',
        required=True,
        help='File to write out')

    parser.add_argument(
        '--start',
        dest='start',
        default='0:0:0',
        help='Starting time, in ffmpeg time')

    parser.add_argument(
        '--end',
        dest='end',
        default=None,
        help='Ending time, in ffmpeg time')

    parser.add_argument(
        '--location',
        dest='location',
        type=float,
        default=0.5,
        help='Place to sample at. Between 0 and 1')

    parser.add_argument(
        '--flipSample',
        dest='flipSample',
        action='store_true',
        help='Sample rows instead of colums?')

    parser.add_argument(
        '--sampleSize',
        dest='sampleSize',
        type=int,
        default=1,
        help='Number of pixels to grab per sample.')

    parser.add_argument(
        '--skipExtract',
        dest='skipExtract',
        action='store_true',
        help='Skip the extract step and reuse existing frames?')

    args = parser.parse_args()

    framedir = SCRATCH_DIR_NAME
    ensure_dir(framedir)

    if not args.skipExtract:
        clear_scratch(framedir)

    extract_and_create_strip(
        {
            "location": args.location,
            "flipSample": args.flipSample,
            "sampleSize": args.sampleSize
        },
        args.video,
        framedir,
        args.out,
        args.start,
        args.end,
        args.skipExtract)


if __name__ == "__main__":
    main()
