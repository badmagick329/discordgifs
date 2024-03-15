import os
import re
from typing import Tuple

from utils import get_available_name


def png_to_video(
    filename: str, dirname: str, output_fps: int, out: str
) -> str:
    PNG_TO_VIDEO = (
        'ffmpeg -y -r {} -i "{}" -c:v libx264 -crf 0 -vf fps={} '
        '-pix_fmt yuv420p -loglevel warning "{}"'
    )
    num_of_digits = len(re.findall(r"\d+", filename)[0])
    seq_input = re.sub(r"\d+", f"%0{num_of_digits}d", filename)
    seq_input = os.path.join(dirname, seq_input)
    return PNG_TO_VIDEO.format(output_fps, seq_input, output_fps, out)


def video_to_png(iname: str, fps: int, dir_: str) -> str:
    PNG = r'ffmpeg -i "{}" -vf fps={} -loglevel warning "{}/frame%05d.png"'
    return PNG.format(iname, fps, dir_)


def crop(inp: str, w: int, h: int, x: int, y: int) -> Tuple[str, str]:
    """Return crop string and output file name."""
    CROP = 'ffmpeg -y -i "{}" -filter:v "crop={}:{}:{}:{}" -c:v libx264 -crf 0 -an -loglevel warning "{}"'
    out = get_available_name(inp, "mp4")
    return CROP.format(inp, w, h, x, y, out), out

def ffplay_preview(video: str) -> str:
    return f'ffplay -autoexit -loop 0 -an -loglevel warning "{video}"'
