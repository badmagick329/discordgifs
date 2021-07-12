import os
import subprocess
import re
import shutil
from typing import List, Callable, Union, Tuple
from dataclasses import dataclass

video_to_out_str = ('ffmpeg -y -i "{}" -filter_complex "[0:v] scale={}:{}'
                    ' [a];[a] split [b][c];[b] palettegen [p];[c][p] paletteuse" "{}"')
png_to_video_str = 'ffmpeg -y -r {} -i "{}" -c:v libx264 -crf 0 -vf fps={} -pix_fmt yuv420p "{}"'

crop_str = 'ffmpeg -y -i "{}" -filter:v "crop={}:{}:{}:{}" -c:v libx264 -crf 0 "{}"'
gifski_str = 'gifski.exe {} --fps {} --width {} -o "{}"'

EMOTESIZE = 256000
PFPSIZE = 10000000
cleanup_files = list()

@dataclass
class OutInfo:
    iwidth: int
    iheight: int
    owratio: float
    ohratio: float
    osize_limit: int
    fps: int
    iname: str
    oname_noext: str
    oext: str = ".gif"

    @property
    def oname(self):
        return f"{self.oname_noext}{self.oext}"


def crop_check(user_input: str):
    return user_input.isdigit() or user_input == ""


def get_input(msg: str, check: Union[Callable, List[str]]):
    while True:
        user_input = input(msg)
        if ((isinstance(check, Callable) and check(user_input))
                or (isinstance(check, list) and user_input.lower() in check)):
            return user_input
        print(f"Invalid input: {user_input}")


def get_out_info(target: str) -> OutInfo:
    """Take target file and get output info. Return OutInfo"""
    # get out size
    out_choices = ['emote', 'pfp', 'banner']
    out_choice = get_input(f"Select output ({','.join(out_choices)}): ", out_choices)
    out_choice = out_choice.lower()
    owratio, ohratio = (1, 1) if out_choice != 'banner' else (1, 0.4)
    osize_limit = EMOTESIZE if out_choice == 'emote' else PFPSIZE
    # get out fps
    fps_choices = ['10','15', '24', '30', '33', '50']
    fps_choice = get_input(f"Select FPS ({','.join(fps_choices)}): ", fps_choices)
    iwidth, iheight = get_dimensions(target)

    ibasename = os.path.basename(target)
    oname_noext = f'{ibasename[:ibasename.rindex(".")]}'

    oinfo = OutInfo(iwidth=iwidth, iheight=iheight,
                    owratio=owratio, ohratio=ohratio, osize_limit=osize_limit,
                    fps=int(fps_choice), iname=target, oname_noext=oname_noext)
    return oinfo


def get_dimensions(target: str) -> Tuple[int, int]:
    """Return video width,height for target"""
    scale_str = "ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of default=nw=1:nk=1 {}"
    fout = subprocess.run(scale_str.format(f'"{target}"'), stdout=subprocess.PIPE).stdout.decode("utf-8")
    iwidth, iheight = int(fout.split()[0]), int(fout.split()[1])
    return iwidth, iheight


def available_file_name(filename: str):
    """Get a filename that doesn't exist"""
    name = filename[:filename.rindex(".")]
    ext = filename[filename.rindex("."):]
    for i in range(10000):
        if os.path.exists(filename):
            filename = f"{name}({i}){ext}"
        else:
            break
    return filename

def available_folder_name(folder: str):
    """Get a folder name that doesn't exist"""
    for i in range(10000):
        if os.path.exists(folder):
            folder = f"{folder}({i})"
        else:
            break
    return folder

def encode_gif(oinfo: OutInfo):
    """Encode gif until it's the maximum size it can be within the size limit using ffmpeg"""
    # get starting frame size
    EMOTE_FSIZE = 110, 100
    PFP_FSIZE = 500, 500
    BANNER_FSIZE = 800, 320
    if oinfo.owratio == oinfo.ohratio:
        # if emote
        if oinfo.osize_limit == EMOTESIZE:
            owidth, oheight = EMOTE_FSIZE if oinfo.iwidth > EMOTE_FSIZE[0] else (oinfo.iwidth, oinfo.iheight)
        # if pfp
        else:
            owidth, oheight = PFP_FSIZE if oinfo.iwidth > PFP_FSIZE[0] else (oinfo.iwidth, oinfo.iheight)
    # if banner
    else:
        owidth, oheight = BANNER_FSIZE if oinfo.iwidth > BANNER_FSIZE[0] else (oinfo.iwidth, oinfo.iheight)
    mul = 0.60
    size_range = 0.95 if oinfo.osize_limit == EMOTESIZE else 0.85
    available_name = available_file_name(oinfo.oname)
    oinfo.oname_noext = available_name[:available_name.rindex(".")]
    oinfo.oext = available_name[available_name.rindex("."):]
    old_width = -1
    while old_width != owidth:
        ffmpeg_cmd = video_to_out_str.format(oinfo.iname, owidth, oheight, oinfo.oname)
        print(f"{ffmpeg_cmd}")
        subprocess.run(ffmpeg_cmd, stderr=subprocess.PIPE)
        size = os.stat(oinfo.oname).st_size
        if (oinfo.osize_limit * size_range < size < oinfo.osize_limit or
                (not max_fsize_check(owidth, oinfo) and max_fsize_check(owidth + 1, oinfo))):
            print(f"{oinfo.oname} file size is {size}")
            break
        old_width = owidth
        owidth, mul = wsize_and_mul(size, oinfo, owidth, mul)
        oheight = int(owidth * oinfo.ohratio)

def gifski(oinfo: OutInfo):
    """Encode gif until it's the maximum size it can be within the size limit using gifski"""
    video_to_png(oinfo)
    # get starting frame size
    EMOTE_FSIZE = 110, 100
    PFP_FSIZE = 500, 500
    BANNER_FSIZE = 800, 320
    if oinfo.owratio == oinfo.ohratio:
        # if emote
        if oinfo.osize_limit == EMOTESIZE:
            owidth, oheight = EMOTE_FSIZE if oinfo.iwidth > EMOTE_FSIZE[0] else (oinfo.iwidth, oinfo.iheight)
        # if pfp
        else:
            owidth, oheight = PFP_FSIZE if oinfo.iwidth > PFP_FSIZE[0] else (oinfo.iwidth, oinfo.iheight)
    # if banner
    else:
        owidth, oheight = BANNER_FSIZE if oinfo.iwidth > BANNER_FSIZE[0] else (oinfo.iwidth, oinfo.iheight)
    mul = 0.60
    size_range = 0.95 if oinfo.osize_limit == EMOTESIZE else 0.85
    width_margin = 1 if oinfo.osize_limit == EMOTESIZE else 20
    available_name = available_file_name(oinfo.oname)
    oinfo.oname_noext = available_name[:available_name.rindex(".")]
    oinfo.oext = available_name[available_name.rindex("."):]
    old_width = -1
    while old_width != owidth:
        gifski_cmd = gifski_str.format(oinfo.iname, oinfo.fps, owidth, oinfo.oname)
        print(gifski_cmd)
        subprocess.run(gifski_cmd)
        size = os.stat(oinfo.oname).st_size
        if (oinfo.osize_limit * size_range < size < oinfo.osize_limit or
                (not max_fsize_check(owidth, oinfo) and max_fsize_check(owidth + width_margin, oinfo))):
            print(f"{oinfo.oname} file size is {size}")
            break
        old_width = owidth
        owidth, mul = wsize_and_mul(size, oinfo, owidth, mul)
        # oheight = int(owidth * oinfo.ohratio)

def video_to_png(oinfo: OutInfo):
    """Create png sequence from the source video for gifski"""
    folder = available_folder_name("frame")
    os.mkdir(folder)
    video_to_seq_str = r'ffmpeg -i "{}" -vf fps={} {}/frame%d.png'
    print(video_to_seq_str.format(oinfo.iname,oinfo.fps,folder))
    subprocess.run(video_to_seq_str.format(oinfo.iname,oinfo.fps,folder), stderr=subprocess.PIPE)
    oinfo.iname=f"{folder}/frame*.png"
    cleanup_files.append(folder)

def wsize_and_mul(size: int, oinfo: OutInfo, old_width: int, old_mul: float):
    """
    Reduce or increase width based on file size and frame size that resulted from the old_width.
    This new_width will be used to calculate height as well. Return new_width
    """
    new_mul = old_mul
    if size >= oinfo.osize_limit or max_fsize_check(old_width, oinfo):
        if old_mul > 0 or max_fsize_check(old_width, oinfo):
            if new_mul > 0:
                new_mul = old_mul / 2
                new_mul *= -1
        print(f"Reducing ", end="")
        new_width = old_width * (1 + new_mul)
        new_width = int(new_width)
    else:
        if old_mul < 0:
            new_mul = old_mul / 2
            new_mul *= -1
        print(f"Increasing ", end="")
        new_width = old_width * (1 + new_mul)
        new_width = int(new_width)

    print(f"frame width to {new_width}")
    return new_width, new_mul


def max_fsize_check(width: int, oinfo: OutInfo):
    """Return True if given width will take video out of bounds based on the ratios in oinfo"""
    return (width >= oinfo.iwidth or
            int(((width * oinfo.ohratio) * (oinfo.owratio / oinfo.ohratio)) > oinfo.iheight))


def png_to_video(oinfo: OutInfo):
    """Create video from a png sequence and set video as input file in oinfo.iname. Return oinfo.iname"""
    filename = os.path.basename(oinfo.iname)
    num_to_use = len(re.findall(r"\d+", filename)[0])
    sq_str_name = re.sub(r"\d+", f"%0{num_to_use}d", filename)
    oinfo.iname = re.sub(filename, sq_str_name, oinfo.iname)
    oinfo.oname_noext = re.sub(r"\d{1,4}$", "", oinfo.oname_noext)
    print(png_to_video_str.format(oinfo.fps, oinfo.iname, oinfo.fps, f"{oinfo.oname_noext}.mp4"))
    subprocess.run(png_to_video_str.format(oinfo.fps, oinfo.iname, oinfo.fps, f"{oinfo.oname_noext}.mp4"),
                   stderr=subprocess.PIPE)
    oinfo.iname = f"{oinfo.oname_noext}.mp4"
    return oinfo.iname


def crop_to_ratio(oinfo: OutInfo, w, h, user_y=None, user_x=None):
    """Crop file at oinfo.iname with given settings and return cropped file name"""
    x = user_x if user_x is not None else int((oinfo.iwidth - w) / 2)
    y = user_y if user_y is not None else int((oinfo.iheight - h) / 2)
    new_name = f"{oinfo.oname_noext}_cropped.mp4"
    print(crop_str.format(oinfo.iname, w, h, x, y, new_name))
    subprocess.run(crop_str.format(oinfo.iname, w, h, x, y, new_name),
                   stderr=subprocess.PIPE)
    return new_name


def ratio_check(oinfo: OutInfo, target_ratio: float):
    """
    Check height/width ratio for the source video. Ask for crop if it's not the right ratio
    Return new file name if file was cropped
    """
    if oinfo.iheight / oinfo.iwidth != target_ratio:
        crop_choices = ['crop', 'stretch']
        crop_choice = get_input(f"Source video is not {'5:2' if target_ratio == 0.4 else '1:1'}. "
                                f"Would you like to crop it or let it stretch? ({','.join(crop_choices)}): ",
                                crop_choices)
        if crop_choice.lower() == 'crop':

            if oinfo.iheight / oinfo.iwidth > target_ratio:
                w = oinfo.iwidth
                h = int(oinfo.iwidth * oinfo.ohratio)
            else:
                h = oinfo.iheight
                w = int(oinfo.iheight * (oinfo.owratio / oinfo.ohratio))
            user_input = 'n'
            new_name = None
            while user_input == 'n':
                y_choice = get_input(f"Enter y value to start cropping from\n"
                                     f"Top = 0 (Video height is {oinfo.iheight}) "
                                     f"Leave blank to crop at center ",
                                     crop_check)
                if y_choice.isdigit():
                    y_choice = int(y_choice)
                if y_choice == "" or y_choice < 0:
                    y_choice = None
                elif y_choice > oinfo.iheight - h:
                    y_choice = oinfo.iheight - h
                x_choice = get_input(f"Enter x value to start cropping from\n"
                                     f"Left edge = 0 (Video width is {oinfo.iwidth}) "
                                     f"crop with right edge on boundary. "
                                     f"Leave blank to crop at center ",
                                     crop_check)
                if x_choice.isdigit():
                    x_choice = int(x_choice)
                if x_choice == "" or x_choice < 0:
                    x_choice = None
                elif x_choice > oinfo.iwidth - w:
                    x_choice = oinfo.iwidth - w
                new_name = crop_to_ratio(oinfo, w, h, y_choice, x_choice)
                user_input = get_input(f"File has been cropped as {new_name}. Press y to continue or n to redo crop ",
                                       ['y', 'n']).lower()
            oinfo.iname = new_name if new_name else oinfo.iname
            oinfo.iwidth, oinfo.iheight = get_dimensions(oinfo.iname)
            return oinfo.iname
    return None


def main():
    source = get_input("Enter full path (including file name) to video or first image in sequence: ",
                       os.path.isfile)
    oinfo = get_out_info(source)
    # if image sequence, create video
    numpng = re.findall(r"[^\d]*(\d{1,4}).png", oinfo.iname)
    if numpng:
        tempfile = png_to_video(oinfo)
        if tempfile:
            cleanup_files.append(tempfile)
    # if banner
    if oinfo.owratio != oinfo.ohratio:
        tempfile = ratio_check(oinfo, target_ratio=0.4)
        if tempfile:
            cleanup_files.append(tempfile)
    # if pfp
    elif oinfo.osize_limit == PFPSIZE:
        tempfile = ratio_check(oinfo, target_ratio=1)
        if tempfile:
            cleanup_files.append(tempfile)

    # if emote use gifski else use ffmpeg
    if oinfo.osize_limit != EMOTESIZE:
        # encode_gif(oinfo)
        gifski(oinfo)
    else:
        encode_gif(oinfo)

    # clean up
    for f in cleanup_files:
        if os.path.isfile(f):
            os.remove(f)
        else:
            shutil.rmtree(f)


if __name__ == '__main__':
    main()
