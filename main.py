from cliinput import CLIInput, InputValidator
from dataclasses import dataclass, field
import os
import subprocess
import re
import shutil
from decimal import Decimal

from typing import List, Tuple, Optional, Union, Callable

show_commands = True
MAX_FPS = 50
VALID_EXTS = (".gif", ".png", ".mp4", ".webm", ".mkv", ".webm", ".avi", ".mov", ".wmv", ".flv", ".mpg", ".mpeg",
              ".m4v", ".ts")


def get_available_name(name: str, ext: str = None) -> str:
    """
    Returns a file or folder name that is currently not in use.
    """
    postfix_pat = re.compile(r".+\((\d+)\).*")
    if os.path.isfile(name) and ext:
        ext = ext.replace(".", "")
        name = f"{os.path.splitext(name)[0]}.{ext}"
    new_name = name
    while os.path.exists(new_name):
        match = re.search(postfix_pat, new_name)
        if match:
            new_num = int(match.groups()[-1]) + 1
            new_name = new_name[:match.start(1)] + str(new_num) + new_name[match.end(1):]
        else:
            name, ext = os.path.splitext(new_name)
            new_name = name + "(0)" + ext
    return new_name


@dataclass
class EncodingInfo:
    iname: str
    iwidth: int
    iheight: int
    icodec: str
    oname: str
    owscale: float
    ohscale: float
    osize_limit: int
    osize_range: float
    fps: int
    out_choice: str

    OUTPUT_CHOICES: str = "emote,pfp,server icon,banner,sticker"

    BANNER_RATIO: tuple = 1, 0.4
    EMOTE_RATIO: tuple = 1, 1

    # Starting frame sizes when encoding to gif
    EMOTE_FSIZE = 110, 100
    PFP_FSIZE = 500, 500
    BANNER_FSIZE = 800, 320
    STICKER_FSIZE = 200, 200

    EMOTE_SIZE = 256000
    STICKER_SIZE = 500000
    PFP_SIZE = 10000000

    def __init__(self, iname: str, iwidth: int, iheight: int, icodec: str, out_choice: str, fps: int):
        self.iname = iname

        self.iwidth = iwidth
        self.iheight = iheight
        self.icodec = icodec
        self.fps = fps
        self.out_choice = out_choice.lower()
        if self.out_choice == "banner":
            self.owscale, self.ohscale = EncodingInfo.BANNER_RATIO
        else:
            self.owscale, self.ohscale = EncodingInfo.EMOTE_RATIO
        if self.out_choice == "emote":
            self.osize_limit = EncodingInfo.EMOTE_SIZE
            self.osize_range = 0.95
        elif self.out_choice == "sticker":
            self.osize_limit = EncodingInfo.STICKER_SIZE
            self.osize_range = 0.95
        else:
            self.osize_limit = EncodingInfo.PFP_SIZE
            self.osize_range = 0.85

        self.oname = get_available_name(iname,
                                        ext=".png" if self.out_choice == "sticker" else ".gif")

    @property
    def iratio(self) -> float:
        return self.iheight / self.iwidth

    @property
    def oratio(self) -> float:
        return self.ohscale / self.owscale

    @property
    def init_odims(self) -> Tuple[int, int]:
        """Return the initial output dimensions based on the out_choice"""
        if self.out_choice == "banner":
            return EncodingInfo.BANNER_FSIZE
        elif self.out_choice == "emote":
            return EncodingInfo.EMOTE_FSIZE
        elif self.out_choice == "sticker":
            return EncodingInfo.STICKER_FSIZE
        else:
            return EncodingInfo.PFP_FSIZE

    def max_width_check(self, width: int) -> bool:
        """Return True if given width will take video out of bounds based on the input and output
        widths and heights"""
        return (width >= self.iwidth or
                int(((width * self.ohscale) * (self.owscale / self.ohscale)) > self.iheight))


class Encoder:

    def __init__(self, einfo: EncodingInfo):
        self.einfo = einfo
        self.output = None

    @staticmethod
    def png_to_video(inp: str, output_fps: int,
                     out: str = None, show_command: bool = True) -> str:
        """Create video from a png sequence. Return full path of the video."""
        PNG_TO_VIDEO = ('ffmpeg -y -r {} -i "{}" -c:v libx264 -crf 0 -vf fps={} '
                        '-pix_fmt yuv420p -loglevel warning "{}"')
        dirname = os.path.dirname(inp)
        filename = os.path.basename(inp)
        num_of_digits = len(re.findall(r"\d+", filename)[0])
        seq_input = re.sub(r"\d+", f"%0{num_of_digits}d", filename)
        seq_input = os.path.join(dirname, seq_input)

        if out is None:
            out = re.sub(r"\d{1,6}$", "", os.path.splitext(filename)[0]) + ".mp4"
            out = os.path.join(dirname, out)
        out = get_available_name(out)

        formatted_str = PNG_TO_VIDEO.format(output_fps, seq_input, output_fps, out)
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
        einfo.iname = f"{folder}/frame*.png"
        return folder

    @staticmethod
    def crop(inp: str, w: int, h: int, x: int, y: int,
             out: str = None) -> str:
        """Crop the video. Return full path of the cropped video."""
        CROP = 'ffmpeg -y -i "{}" -filter:v "crop={}:{}:{}:{}" -c:v libx264 -crf 0 -loglevel warning "{}"'
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
        return round(float(float(frames) / float(seconds)),3)

    @staticmethod
    def get_codec(tar: str) -> str:
        """Return video codec for target"""
        return Encoder.ffprobe(tar, "codec_name")

    @staticmethod
    def ffprobe(tar: str, stream_value: str) -> str:
        """Return value of stream_value for target"""
        formatted_str = (f'ffprobe -v error -select_streams v:0 -show_entries '
                         f'stream={stream_value} -of default=nw=1:nk=1 "{tar}"')
        # if show_commands:
        #     print(f"\n{formatted_str}")
        fout = subprocess.run(formatted_str, stdout=subprocess.PIPE).stdout.decode("utf-8")
        return fout.strip()

    def encode_gif(self) -> str:
        """Encode gif until it's the maximum size it can be within the size limit using ffmpeg"""
        GIFSKI = self.einfo.iname.endswith("*.png")

        if GIFSKI:
            self.gifski_encode()
        else:
            self.ffmpeg_encode()
        return self.output

    def gifski_encode(self) -> str:
        GIFSKI_GIF = 'gifski.exe {} --fps {} --width {} -o "{}"'

        einfo = self.einfo
        owidth, oheight = einfo.init_odims

        iname = os.path.basename(einfo.iname)
        old_cwd = os.getcwd()
        os.chdir(os.path.dirname(einfo.iname))

        mul = 0.60
        width_margin = 1 if einfo.osize_limit == EncodingInfo.EMOTE_SIZE else 20

        old_width = -1
        while old_width != owidth:
            formatted_str = GIFSKI_GIF.format(iname, einfo.fps, owidth, einfo.oname)

            if show_commands:
                print(f"\n{formatted_str}")

            subprocess.run(formatted_str, shell=True)
            size = os.stat(einfo.oname).st_size
            if (einfo.osize_limit * einfo.osize_range < size < einfo.osize_limit or
                    (not einfo.max_width_check(owidth) and einfo.max_width_check(owidth + width_margin))):
                print(f"\n{einfo.oname} file size is {size}")
                break
            old_width = owidth
            owidth, mul = self.wsize_and_mul(size, owidth, mul)

        os.chdir(old_cwd)
        self.output = einfo.oname
        return self.output

    def ffmpeg_encode(self) -> str:
        """Encode video using ffmpeg"""
        FFMPEG_GIF = ('ffmpeg -y -i "{}" -filter_complex "[0:v] scale={}:{}'
                      ' [a];[a] split [b][c];[b] palettegen [p];[c][p] paletteuse" -loglevel warning "{}"')

        FFMPEG_APNG = ('ffmpeg -y -i "{}" -f apng -plays 0 -vf '
                       '"scale={}:{}:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" '
                       '-loglevel warning "{}"')
        ffmpeg_str = FFMPEG_APNG if self.einfo.oname.endswith(".png") else FFMPEG_GIF
        einfo = self.einfo
        owidth, oheight = einfo.init_odims

        # iname = os.path.basename(einfo.iname)
        # old_cwd = os.getcwd()
        # os.chdir(os.path.dirname(einfo.iname))

        mul = 0.60

        old_width = -1
        while old_width != owidth:
            formatted_str = ffmpeg_str.format(einfo.iname, owidth, oheight, einfo.oname)
            if show_commands:
                print(f"\n{formatted_str}")

            subprocess.run(formatted_str, shell=True)
            size = os.stat(einfo.oname).st_size
            if (einfo.osize_limit * einfo.osize_range < size < einfo.osize_limit or
                    (not einfo.max_width_check(owidth) and einfo.max_width_check(owidth + 1))):
                print(f"\n{einfo.oname} file size is {size}")
                break
            old_width = owidth
            owidth, mul = self.wsize_and_mul(size, owidth, mul)
            oheight = int(owidth * einfo.ohscale)

        # os.chdir(old_cwd)
        self.output = einfo.oname
        return self.output

    def wsize_and_mul(self, size: int, old_width: int, old_mul: float):
        """
        Reduce or increase width based on file size and frame size that resulted from the old_width.
        This new_width will be used to calculate height as well. Return new_width
        """
        einfo = self.einfo
        new_mul = old_mul
        if size >= einfo.osize_limit or einfo.max_width_check(old_width):
            if old_mul > 0 or einfo.max_width_check(old_width):
                if new_mul > 0:
                    new_mul = old_mul / 2
                    new_mul *= -1
            new_width = old_width * (1 + new_mul)
            new_width = int(new_width)
        else:
            if old_mul < 0:
                new_mul = old_mul / 2
                new_mul *= -1
            new_width = old_width * (1 + new_mul)
            new_width = int(new_width)

        return new_width, new_mul

def check_dependancies():
    if not shutil.which("ffmpeg"):
        print("\nffmpeg is not installed. Please install it from https://ffmpeg.org/")
        input("Press enter to exit")
        exit(1)
    if not shutil.which("ffprobe"):
        print("\nffprobe is not installed. Please install it from https://ffmpeg.org/")
        input("Press enter to exit")
        exit(1)
    if not shutil.which("gifski"):
        print("\ngifski is not installed. Please install it from https://gif.ski/")
        input("Press enter to exit")
        exit(1)


def get_crop_info(einfo: EncodingInfo, w: int, h: int) -> Tuple[str, int, int, int, int]:
    prompt = (f"\nEnter y value to start cropping at\n"
              f"Top = 0 Video height: {einfo.iheight}\n"
              f"Leave blank to crop at the center ")
    y = CLIInput(validators=[InputValidator(str.isdigit, "Value must be a number")],
                 required=False
                 ).prompt(prompt)

    if y is None:
        y = int((einfo.iheight - h) / 2)
    else:
        y = int(y)
        if y > einfo.iheight - h:
            y = einfo.iheight - h

    prompt = (f"\nEnter x value to start cropping at\n"
              f"Left = 0 Video width: {einfo.iwidth}\n"
              f"Leave blank to crop at the center ")
    x = CLIInput(validators=[InputValidator(str.isdigit, "Value must be a number")],
                 required=False
                 ).prompt(prompt)

    if x is None:
        x = int((einfo.iwidth - w) / 2)
    else:
        x = int(x)
        if x > einfo.iwidth - w:
            x = einfo.iwidth - w

    return einfo.iname, w, h, x, y


def fix_file_dimensions(einfo: EncodingInfo) -> Optional[str]:
    """Crop video to match output ratio if needed. If video is cropped return cropped video path"""
    if einfo.iratio == einfo.oratio:
        return None
    ratio = Decimal(str(einfo.oratio)).as_integer_ratio()
    ratio = f"{ratio[1]}:{ratio[0]}"
    prompt = f"\nSource is not {ratio}. Would you like to crop or let it stretch? "
    crop_choice = CLIInput(choices=["crop", "stretch"], prompt_text=prompt).prompt().lower()
    if crop_choice == "crop":
        if einfo.iratio > einfo.oratio:
            w = einfo.iwidth
            h = int(einfo.iwidth * einfo.ohscale)
        else:
            h = einfo.iheight
            w = int(einfo.iheight * (einfo.owscale / einfo.ohscale))
        new_name = None
        user_input = False
        while not user_input:
            cname, cw, ch, cx, cy = get_crop_info(einfo, w, h)
            new_name = Encoder.crop(cname, cw, ch, cx, cy)
            prompt = f"\nCrop preview at {new_name}\nPress y to use this file or n to re-crop "
            user_input = CLIInput(binary_response=True, prompt_text=prompt).prompt()
        if new_name:
            einfo.iname = new_name
            einfo.iwidth, einfo.iheight = Encoder.get_dimensions(new_name)
            return new_name


def get_encoding_info(tar: str, source_fps: float, codec_name: str) -> EncodingInfo:
    """
    Ask user for output type and fps. Return EncodingInfo object
    """

    out_choices = EncodingInfo.OUTPUT_CHOICES.split(",")
    out_choice = CLIInput(choices=out_choices, prompt_text=f"Select output type ({', '.join(out_choices)}): "
                          ).prompt()
    fps_choices = [str(n) for n in range(10, MAX_FPS + 1)]
    prompt_text = ""
    if not (tar.endswith(".png") and codec_name == "png"):
        prompt_text = f"\nSource fps is {source_fps}\n"
    prompt_text += f"Select output FPS (10-{MAX_FPS}): "
    fps = CLIInput(choices=fps_choices, prompt_text=prompt_text).prompt()
    fps = int(fps)

    iwidth, iheight = Encoder.get_dimensions(tar)

    return EncodingInfo(tar, iwidth, iheight, codec_name, out_choice, fps)


def clean_up(tempfiles: List[str]):
    """Delete temp files"""
    for f in tempfiles:
        try:
            if os.path.isfile(f):
                os.remove(f)
            else:
                shutil.rmtree(f)
        except (FileNotFoundError, OSError, PermissionError) as e:
            print(f"Error removing {f}: {e}")


def valid_ext(f: str) -> bool:
    return f.endswith(VALID_EXTS)


def main():
    check_dependancies()

    iname = CLIInput(validators=[InputValidator(os.path.isfile, "File not found."),
                                 InputValidator(valid_ext, "File is not a valid media file.")],
                     prompt_text="Enter full path including file name, to video or first image in png sequence: "
                     ).prompt()
    source_fps = Encoder.get_fps(iname)

    einfo = get_encoding_info(iname, source_fps, Encoder.get_codec(iname))

    tempfiles = list()

    # if image sequence, create video
    numpng = re.search(r"[^\d]*(\d{1,5}).png", einfo.iname)
    if numpng and einfo.icodec == "png":
        print("\nCreating video from image sequence")
        tempfile = Encoder.png_to_video(einfo.iname, einfo.fps)
        einfo.iname = tempfile
        if tempfile:
            tempfiles.append(tempfile)

    if einfo.out_choice == "sticker" and (dur := Encoder.get_duration(einfo.iname)) >= 5:
        print(f"\nVideo duration is {dur} seconds. Stickers must be less than 5 seconds.")
        clean_up(tempfiles)
        input("Press enter to exit")
        exit(1)

    # crop video if needed
    result = fix_file_dimensions(einfo)
    if result:
        tempfiles.append(result)

    # encode gif
    encoder = Encoder(einfo)
    if einfo.out_choice != "emote" and einfo.out_choice != "sticker":
        tempfile = Encoder.video_to_png(einfo)
        tempfiles.append(tempfile)
    output = encoder.encode_gif()
    print(f"\nOutput file: {output}")

    # clean up
    clean_up(tempfiles)
    input("Press enter to exit")


if __name__ == "__main__":
    main()
