from cliinput import CLIInput, InputValidator
from encoder import Encoder, EncodingInfo
import os
import re
import shutil
from decimal import Decimal

from typing import List, Tuple, Optional, Union, Callable

MAX_FPS = 50
VALID_EXTS = (
    ".gif",
    ".png",
    ".mp4",
    ".webm",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".mpg",
    ".mpeg",
    ".m4v",
    ".ts",
)


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


def get_crop_info(
    einfo: EncodingInfo, w: int, h: int
) -> Tuple[str, int, int, int, int]:
    prompt = (
        f"\nEnter y value to start cropping at\n"
        f"Top = 0 Video height: {einfo.iheight}\n"
        f"Leave blank to crop at the center "
    )
    y = CLIInput(
        validators=[InputValidator(str.isdigit, "Value must be a number")],
        required=False,
    ).prompt(prompt)

    if y is None:
        y = int((einfo.iheight - h) / 2)
    else:
        y = int(y)
        if y > einfo.iheight - h:
            y = einfo.iheight - h

    prompt = (
        f"\nEnter x value to start cropping at\n"
        f"Left = 0 Video width: {einfo.iwidth}\n"
        f"Leave blank to crop at the center "
    )
    x = CLIInput(
        validators=[InputValidator(str.isdigit, "Value must be a number")],
        required=False,
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
    crop_choice = (
        CLIInput(choices=["crop", "stretch"], prompt_text=prompt).prompt().lower()
    )
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
            # TODO add this to clean up
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
    out_choice = CLIInput(
        choices=out_choices,
        prompt_text=f"Select output type ({', '.join(out_choices)}): ",
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


def get_einfos_and_tempfiles() -> Tuple[List[EncodingInfo], List[str]]:
    einfos = list()
    tempfiles = list()

    # Get input files
    get_more = True
    while get_more:
        iname = CLIInput(
            validators=[
                InputValidator(os.path.isfile, "File not found."),
                InputValidator(valid_ext, "File is not a valid media file."),
            ],
            prompt_text="Enter full path including file name, to video or first image in png sequence: ",
        ).prompt()
        source_fps = Encoder.get_fps(iname)

        einfo = get_encoding_info(iname, source_fps, Encoder.get_codec(iname))

        # if image sequence, create video
        numpng = re.search(r"[^\d]*(\d{1,5}).png", einfo.iname)
        if numpng and einfo.icodec == "png":
            print("\nCreating video from image sequence")
            tempfile = Encoder.png_to_video(einfo.iname, einfo.fps)
            einfo.iname = tempfile
            if tempfile:
                tempfiles.append(tempfile)

        if (
            einfo.out_choice == "sticker"
            and (dur := Encoder.get_duration(einfo.iname)) >= 5
        ):
            print(
                f"\nVideo duration is {dur} seconds. Stickers must be less than 5 seconds."
            )
        else:
            # crop video if needed
            if result := fix_file_dimensions(einfo):
                tempfiles.append(result)
            einfos.append(einfo)
        get_more = CLIInput(
            binary_response=True, prompt_text="\nWould you like to add another file? "
        ).prompt()

    return einfos, tempfiles


def main():
    check_dependancies()

    # get input files
    einfos, tempfiles = get_einfos_and_tempfiles()

    # encode gifs
    output_files = list()
    for einfo in einfos:
        encoder = Encoder(einfo)
        if einfo.out_choice != "emote" and einfo.out_choice != "sticker":
            tempfile = Encoder.video_to_png(einfo)
            tempfiles.append(tempfile)
        output_files.append(encoder.encode_gif())

    # display result

    print("\n\nOutput files:")
    for out in output_files:
        size = os.stat(out).st_size
        size_str = (
            f"{size / 1_000:.2f}KB" if size < 1_000_000 else f"{size / 1_000_000:.2f}MB"
        )
        print(f"{out} ({size_str})")

    # clean up
    clean_up(tempfiles)
    input("Press enter to exit")


if __name__ == "__main__":
    main()
