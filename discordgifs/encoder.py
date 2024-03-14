import os
import re
import subprocess
import sys
from typing import Optional, Tuple

from encoding_info import EncodingInfo
from utils import get_available_name

show_commands = True


class Encoder:
    def __init__(self, einfo: EncodingInfo):
        self.einfo = einfo
        self.output = None

    @staticmethod
    def png_to_video(
        inp: str,
        output_fps: int,
        out: Optional[str] = None,
        show_command: bool = True,
    ) -> str:
        """Create video from a png sequence. Return full path of the video."""
        PNG_TO_VIDEO = (
            'ffmpeg -y -r {} -i "{}" -c:v libx264 -crf 0 -vf fps={} '
            '-pix_fmt yuv420p -loglevel warning "{}"'
        )
        dirname = os.path.dirname(inp)
        filename = os.path.basename(inp)
        num_of_digits = len(re.findall(r"\d+", filename)[0])
        seq_input = re.sub(r"\d+", f"%0{num_of_digits}d", filename)
        seq_input = os.path.join(dirname, seq_input)

        if out is None:
            out = (
                re.sub(r"\d{1,6}$", "", os.path.splitext(filename)[0]) + ".mp4"
            )
            out = os.path.join(dirname, out)
        out = get_available_name(out)

        formatted_str = PNG_TO_VIDEO.format(
            output_fps, seq_input, output_fps, out
        )
        if show_command:
            print(f"\n{formatted_str}")
        subprocess.run(formatted_str, shell=True)
        return out

    @staticmethod
    def video_to_png(einfo: EncodingInfo, show_command: bool = True) -> str:
        """Create png sequence from the source video for gifski"""
        PNG = r'ffmpeg -i "{}" -vf fps={} -loglevel warning "{}/frame%05d.png"'
        dirname = os.path.dirname(einfo.iname)
        folder = get_available_name(os.path.join(dirname, "frames"))
        os.mkdir(folder)
        formatted_str = PNG.format(einfo.iname, einfo.fps, folder)
        if show_command:
            print(f"\n{formatted_str}")
        subprocess.run(formatted_str, shell=True)
        einfo.iname = os.path.join(folder, "frame*.png")
        return folder

    @staticmethod
    def crop(
        inp: str, w: int, h: int, x: int, y: int, out: Optional[str] = None
    ) -> str:
        """Crop the video. Return full path of the cropped video."""
        CROP = 'ffmpeg -y -i "{}" -filter:v "crop={}:{}:{}:{}" -c:v libx264 -crf 0 -an -loglevel warning "{}"'
        if out is None:
            out = get_available_name(inp, "mp4")
        out = get_available_name(out)
        formatted_str = CROP.format(inp, w, h, x, y, out)
        if show_commands:
            print(f"\n{formatted_str}")
        subprocess.run(formatted_str, shell=True)
        return out

    @staticmethod
    def get_dimensions(tar: str) -> Tuple[int, int]:
        """Return video width,height for target"""
        fout = Encoder.ffprobe(tar, "width,height")
        iwidth, iheight = fout.split()
        return int(iwidth), int(iheight)

    @staticmethod
    def get_duration(tar: str) -> float:
        """Return video duration for target"""
        fout = Encoder.ffprobe(tar, "duration")
        return float(fout)

    @staticmethod
    def get_fps(tar: str) -> float:
        """Return video fps for target"""
        fout = Encoder.ffprobe(tar, "r_frame_rate")
        frames, seconds = fout.split("/")
        return round(float(float(frames) / float(seconds)), 3)

    @staticmethod
    def get_codec(tar: str) -> str:
        """Return video codec for target"""
        return Encoder.ffprobe(tar, "codec_name")

    @staticmethod
    def ffprobe(tar: str, stream_value: str) -> str:
        """Return value of stream_value for target"""
        formatted_str = (
            f"ffprobe -v error -select_streams v:0 -show_entries "
            f'stream={stream_value} -of default=nw=1:nk=1 "{tar}"'
        )
        fout = subprocess.run(
            formatted_str, stdout=subprocess.PIPE, shell=True
        ).stdout.decode("utf-8")
        return fout.strip()

    def encode_gif(self) -> str:
        """
        Encode gif until it's the maximum size it can be within the size limit using ffmpeg or gifski
        """
        GIFSKI = self.einfo.iname.endswith("*.png")

        if GIFSKI:
            self.output = self.gifski_encode()
        else:
            self.output = self.ffmpeg_encode()
        return self.output

    def gifski_encode(self) -> str:
        if sys.platform == "win32":
            gifski = "gifski.exe"
        else:
            gifski = "gifski"
        GIFSKI_GIF = '{} {} --fps {} --width {} -o "{}"'

        einfo = self.einfo
        owidth, _ = einfo.init_odims

        einfo.oname = get_available_name(einfo.oname)

        iname = os.path.basename(einfo.iname)
        old_cwd = os.getcwd()
        os.chdir(os.path.dirname(einfo.iname))

        mul = 0.60
        width_margin = (
            1 if einfo.osize_limit == EncodingInfo.EMOTE_SIZE else 20
        )

        old_width = -1
        while old_width != owidth:
            formatted_str = GIFSKI_GIF.format(
                gifski, iname, einfo.fps, owidth, einfo.oname
            )

            if show_commands:
                print(f"\n{formatted_str}")

            subprocess.run(formatted_str, shell=True)
            size = os.stat(einfo.oname).st_size
            print(f"size: {size}")
            size_is_within_range = (
                einfo.osize_limit * einfo.osize_range
                < size
                < einfo.osize_limit
            )
            size_is_close_enough = not einfo.max_width_check(
                owidth
            ) and einfo.max_width_check(owidth + width_margin)

            if size_is_within_range or (size_is_close_enough):
                break
            old_width = owidth
            owidth, mul = self.wsize_and_mul(size, owidth, mul)

        os.chdir(old_cwd)
        return einfo.oname

    def ffmpeg_encode(self) -> str:
        """Encode video using ffmpeg"""
        FFMPEG_GIF = (
            'ffmpeg -y -i "{}" -filter_complex "[0:v] scale={}:{}'
            ' [a];[a] split [b][c];[b] palettegen [p];[c][p] paletteuse" -loglevel warning "{}"'
        )

        FFMPEG_APNG = (
            'ffmpeg -y -i "{}" -f apng -plays 0 -vf '
            '"scale={}:{}:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" '
            '-loglevel warning "{}"'
        )
        ffmpeg_str = (
            FFMPEG_APNG if self.einfo.oname.endswith(".png") else FFMPEG_GIF
        )
        einfo = self.einfo
        owidth, oheight = einfo.init_odims

        einfo.oname = get_available_name(einfo.oname)

        mul = 0.60

        old_width = -1
        while old_width != owidth:
            formatted_str = ffmpeg_str.format(
                einfo.iname, owidth, oheight, einfo.oname
            )
            if show_commands:
                print(f"\n{formatted_str}")

            subprocess.run(formatted_str, shell=True)
            size = os.stat(einfo.oname).st_size
            if (
                einfo.osize_limit * einfo.osize_range
                < size
                < einfo.osize_limit
                or (
                    not einfo.max_width_check(owidth)
                    and einfo.max_width_check(owidth + 1)
                )
            ):
                break
            old_width = owidth
            owidth, mul = self.wsize_and_mul(size, owidth, mul)
            oheight = int(owidth * einfo.ohscale)

        return einfo.oname

    def wsize_and_mul(self, size: int, old_width: int, mul: float):
        """
        Reduce or increase width based on file size and frame size that
        resulted from the old_width. This new_width will be used to calculate
        height as well. Return new_width
        """
        video_is_out_of_bounds = self.einfo.max_width_check(old_width)

        if size >= self.einfo.osize_limit or video_is_out_of_bounds:
            if mul > 0 or video_is_out_of_bounds:
                if mul > 0:
                    mul = mul / 2
                    mul *= -1
            new_width = old_width * (1 + mul)
            new_width = int(new_width)
        else:
            if mul < 0:
                mul = mul / 2
                mul *= -1
            new_width = old_width * (1 + mul)
            new_width = int(new_width)
        return new_width, mul

    @classmethod
    def create_einfo(
        cls, filename: str, fps, output_type: str
    ) -> EncodingInfo:
        codec = cls.get_codec(filename)
        iwidth, iheight = cls.get_dimensions(filename)
        return EncodingInfo.new(
            filename, iwidth, iheight, codec, output_type, fps
        )
