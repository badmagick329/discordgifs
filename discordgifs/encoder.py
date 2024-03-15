import os
import re
import subprocess
import sys
from abc import ABC, abstractmethod
from typing import Tuple

import ffmpeg_cmds
from encoding_info import EncodingInfo
from utils import get_available_name

show_commands = True


class Encoder(ABC):
    einfo: EncodingInfo

    def __init__(self, einfo: EncodingInfo):
        self.einfo = einfo

    @staticmethod
    def new(einfo: EncodingInfo):
        if einfo.uses_gifski:
            return GifskiEncoder(einfo)
        return FFmpegEncoder(einfo)

    @classmethod
    def png_to_video(
        cls,
        inp: str,
        output_fps: int,
        show_command: bool = True,
    ) -> str:
        """Create video from a png sequence. Return full path of the video."""
        dirname = os.path.dirname(inp)
        filename = os.path.basename(inp)
        out = re.sub(r"\d{1,6}$", "", os.path.splitext(filename)[0]) + ".mp4"
        out = os.path.join(dirname, out)
        out = get_available_name(out)

        cmd = ffmpeg_cmds.png_to_video(filename, dirname, output_fps, out)
        Encoder._run_cmd(cmd, show_command)
        return out

    @classmethod
    def video_to_png(
        cls, einfo: EncodingInfo, show_command: bool = True
    ) -> str:
        """Create png sequence from the source video for gifski.
        Return full path of the folder."""
        dirname = os.path.dirname(einfo.iname)
        folder = get_available_name(os.path.join(dirname, "frames"))
        os.mkdir(folder)

        cmd = ffmpeg_cmds.video_to_png(einfo.iname, einfo.fps, folder)
        Encoder._run_cmd(cmd, show_command)
        einfo.iname = os.path.join(folder, "frame*.png")
        return folder

    @classmethod
    def crop(cls, inp: str, w: int, h: int, x: int, y: int) -> str:
        """Crop the video. Return full path of the cropped video."""
        cmd, out = ffmpeg_cmds.crop(inp, w, h, x, y)
        Encoder._run_cmd(cmd, show_commands)
        return out

    @classmethod
    def get_dimensions(cls, tar: str) -> Tuple[int, int]:
        """Return video width,height for target"""
        fout = Encoder._ffprobe(tar, "width,height")
        iwidth, iheight = fout.split()
        return int(iwidth), int(iheight)

    @classmethod
    def get_duration(cls, tar: str) -> float:
        """Return video duration for target"""
        fout = Encoder._ffprobe(tar, "duration")
        return float(fout)

    @classmethod
    def get_fps(cls, tar: str) -> float:
        """Return video fps for target"""
        fout = Encoder._ffprobe(tar, "r_frame_rate")
        frames, seconds = fout.split("/")
        return round(float(float(frames) / float(seconds)), 3)

    @classmethod
    def get_codec(cls, tar: str) -> str:
        """Return video codec for target"""
        return Encoder._ffprobe(tar, "codec_name")

    @abstractmethod
    def encode(self) -> str:
        """
        Encode gif until it's the maximum size it can be within the size limit
        using ffmpeg or gifski
        """
        raise NotImplementedError("encode must be implemented")

    @classmethod
    def create_einfo(
        cls, filename: str, fps, output_type: str
    ) -> EncodingInfo:
        codec = cls.get_codec(filename)
        iwidth, iheight = cls.get_dimensions(filename)
        return EncodingInfo.new(
            filename, iwidth, iheight, codec, output_type, fps
        )

    @classmethod
    def preview(cls, video: str):
        """Preview the video"""
        cmd = ffmpeg_cmds.ffplay_preview(video)
        proc = subprocess.Popen(cmd, shell=True)
        return proc

    def _wsize_and_mul(self, size: int, old_width: int, mul: float):
        """
        Reduce or increase width based on file size and frame size that
        resulted from the old_width. This new_width will be used to calculate
        height as well. Return new_width
        """
        video_is_out_of_bounds = self.einfo.max_width_check(old_width)

        if size >= self.einfo.osize_limit or video_is_out_of_bounds:
            return self._get_reduced_size(
                old_width, mul, video_is_out_of_bounds
            )
        else:
            return self._get_increased_size(old_width, mul)

    def _get_reduced_size(
        self,
        old_width: int,
        mul: float,
        video_is_out_of_bounds: bool,
    ):
        if mul > 0 or video_is_out_of_bounds:
            if mul > 0:
                mul = mul / 2
                mul *= -1
        new_width = old_width * (1 + mul)
        new_width = int(new_width)
        return new_width, mul

    def _get_increased_size(
        self,
        old_width: int,
        mul: float,
    ):
        if mul < 0:
            mul = mul / 2
            mul *= -1
        new_width = old_width * (1 + mul)
        new_width = int(new_width)
        return new_width, mul

    @classmethod
    def _run_cmd(cls, cmd: str, show_command: bool = True):
        if show_command:
            print(f"\n{cmd}")
        subprocess.run(cmd, shell=True)

    @classmethod
    def _ffprobe(cls, tar: str, stream_value: str) -> str:
        """Return value of stream_value for target"""
        formatted_str = (
            f"ffprobe -v error -select_streams v:0 -show_entries "
            f'stream={stream_value} -of default=nw=1:nk=1 "{tar}"'
        )
        fout = subprocess.run(
            formatted_str, stdout=subprocess.PIPE, shell=True
        ).stdout.decode("utf-8")
        return fout.strip()


class GifskiEncoder(Encoder):
    def __init__(self, einfo: EncodingInfo):
        super().__init__(einfo)

    def encode(self) -> str:
        """Encode video using gifski"""
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
        old_width = -1
        while old_width != owidth:
            formatted_str = GIFSKI_GIF.format(
                gifski, iname, einfo.fps, owidth, einfo.oname
            )

            if show_commands:
                print(f"\n{formatted_str}")

            subprocess.run(formatted_str, shell=True)
            size = os.stat(einfo.oname).st_size
            print(f"size: {size//1024}KB")
            size_is_within_range = (
                einfo.osize_limit * einfo.osize_range
                < size
                < einfo.osize_limit
            )
            size_is_close_enough = not einfo.max_width_check(
                owidth
            ) and einfo.max_width_check(owidth + einfo.width_change_margin)

            if size_is_within_range or (size_is_close_enough):
                break
            old_width = owidth
            owidth, mul = self._wsize_and_mul(size, owidth, mul)

        os.chdir(old_cwd)
        return einfo.oname


class FFmpegEncoder(Encoder):
    def __init__(self, einfo: EncodingInfo):
        super().__init__(einfo)

    def encode(self) -> str:
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
            print(f"size: {size//1024}KB")
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
            owidth, mul = self._wsize_and_mul(size, owidth, mul)
            oheight = int(owidth * einfo.ohscale)

        return einfo.oname
