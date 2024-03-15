import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import dearpygui.dearpygui as dpg
from encoder import Encoder
from encoding_info import OUTPUT_CHOICES, EncodingInfo


@dataclass(frozen=True)
class Tags:
    """Dataclass to store tags for gui components"""

    # Main window
    main_window: str = "main"
    filename_input: str = "filename_input"
    fps_text: str = "fps_text"
    fps_input: str = "fps_input"
    output_radio_button: str = "output_radio_button"
    crop_checkbox: str = "crop_checkbox"
    auto_crop_checkbox: str = "auto_crop_checkbox"
    encode_button: str = "encode_button"
    queue_button: str = "queue_button"
    messages: str = "messages"
    # Crop modal
    crop_window: str = "crop_window"
    crop_message: str = "crop_message"
    crop_x_slider: str = "crop_x_slider"
    crop_y_slider: str = "crop_y_slider"
    preview_file_button: str = "preview_file_button"
    crop_confirm_button: str = "crop_confirm_button"
    preview_message: str = "preview_message"


class GuiHandler:
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
    DEBUG = False
    STYLE = False

    def __init__(self):
        self.dependency_message = None
        self.title = "DiscordGifs"
        self.messages = list()

        self.files_to_process = list()
        self.to_crop = list()
        self.temp_files = list()
        self.cropped_filenames = list()
        self.output_files = list()

        self.current_file = None

    def reset_values(self):
        self.files_to_process = list()
        self.to_crop = list()
        self.temp_files = list()
        self.cropped_filenames = list()
        self.output_files = list()
        self.current_file = None

    #########
    # Helpers
    #########

    def is_valid_file(self, path):
        return path.endswith(self.VALID_EXTS) and os.path.isfile(path)

    def show_message(self, msg: str):
        self.messages.insert(0, msg)
        dpg.set_value(Tags.messages, "\n".join(self.messages))

    def clean_up(self):
        """Delete temp files"""
        for f in self.temp_files + self.cropped_filenames:
            try:
                if os.path.isfile(f):
                    os.remove(f)
                else:
                    shutil.rmtree(f)
            except (FileNotFoundError, OSError, PermissionError) as e:
                self.show_message(f"Error removing {f}: {e}")

    def show_crop_modal(self, hide_x: bool):
        dpg.configure_item(Tags.crop_x_slider, show=True)
        dpg.configure_item(Tags.crop_y_slider, show=True)

        if hide_x:
            dpg.configure_item(Tags.crop_x_slider, show=False)
            cood = "y"
        else:
            dpg.configure_item(Tags.crop_y_slider, show=False)
            cood = "x"
        einfo = self.current_file
        dpg.configure_item(Tags.crop_window, show=True)
        dpg.set_value(
            Tags.crop_message,
            f"Set {cood} value for cropping. Preview. Confirm or readjust value",
        )
        dpg.configure_item(Tags.crop_x_slider, max_value=einfo.iwidth)
        dpg.configure_item(Tags.crop_y_slider, max_value=einfo.iheight)

    def auto_crop_file(self, einfo: EncodingInfo):
        if einfo.iratio > einfo.oratio:
            w = einfo.iwidth
            h = int(einfo.iwidth * einfo.ohscale)
        else:
            h = einfo.iheight
            w = int(einfo.iheight * (einfo.owscale / einfo.ohscale))
        y = int((einfo.iheight - h) / 2)
        x = int((einfo.iwidth - w) / 2)
        cropped_filename = Encoder.crop(einfo.iname, w, h, x, y)
        self.cropped_filenames.append(cropped_filename)
        einfo.iname = cropped_filename
        einfo.iwidth, einfo.iheight = Encoder.get_dimensions(cropped_filename)
        self.current_file = None

    ###########
    # Callbacks
    ###########

    # Main window callbacks

    def filename_callback(self, sender, path, user_data):
        """
        Expected keys in user_data
        "default_prompt" - Default text attached to the fps input
        "default_fps" - Default fps when input file has no fps value
        """
        path = path.strip('"')
        valid_file = self.is_valid_file(path)

        png_codec = ""
        if not valid_file:
            if path.strip() != "":
                label = (
                    f"Invalid file type: {os.path.splitext(path)[1]}"
                    if os.path.isfile(path)
                    else "File not found"
                )
                dpg.configure_item(sender, label=label)
            else:
                dpg.configure_item(sender, label="")
            dpg.set_value(Tags.fps_text, user_data["default_prompt"])
            dpg.set_value(Tags.fps_input, user_data["default_fps"])
            return

        # if valid file update label
        if path.endswith(".gif"):
            label = "Gif found"
        elif path.endswith(".png"):
            png_codec = Encoder.get_codec(path)
            label = "apng found" if png_codec == "apng" else "png found"
        else:
            label = "Video found"
        dpg.configure_item(sender, label=label)

        # display source fps unless it's an image sequence
        if png_codec == "png":
            dpg.set_value(Tags.fps_text, user_data["default_prompt"])
            return

        fps = Encoder.get_fps(path)
        dpg.set_value(
            Tags.fps_text, f"{user_data['default_prompt']}, Source is {fps}fps"
        )
        dpg.set_value(Tags.fps_input, round(fps))

    def add_file_callback(self):
        filename = dpg.get_value(Tags.filename_input).strip('"')
        print(f"{filename=}")
        print(f"{Tags.filename_input=}")
        if not self.is_valid_file(filename):
            return
        # Get data
        dpg.configure_item(Tags.queue_button, enabled=False)
        einfo = Encoder.create_einfo(
            filename,
            dpg.get_value(Tags.fps_input),
            dpg.get_value(Tags.output_radio_button),
        )

        # png to video
        numpng = re.search(r"[^\d]*(\d{1,5}).png", einfo.iname)
        if einfo.icodec == "png" and numpng:
            self.show_message("Converting png sequence to video")
            tmp = Encoder.png_to_video(einfo.iname, einfo.fps)
            self.temp_files.append(tmp)
            einfo.iname = tmp

        # sticker check
        if (
            einfo.is_sticker
            and (dur := Encoder.get_duration(einfo.iname)) >= 5
        ):
            self.show_message(
                f"Video duration is {dur} seconds. Stickers must be less than 5 seconds"
            )
            dpg.configure_item(Tags.queue_button, enabled=True)
            return

        einfo.crop = dpg.get_value(Tags.crop_checkbox)
        einfo.auto_crop = dpg.get_value(Tags.auto_crop_checkbox)
        self.files_to_process.append(einfo)
        self.show_message(f"Added {einfo.iname} to queue")

        assert (
            len(self.files_to_process) > 0
        ), "file_to_process should not be empty"

        dpg.configure_item(
            Tags.encode_button,
            enabled=True,
            label=f"Encode ({len(self.files_to_process)} queued)",
        )
        dpg.configure_item(Tags.queue_button, enabled=True)

    def encode_callback(self):
        dpg.configure_item(Tags.encode_button, enabled=False)
        dpg.configure_item(Tags.queue_button, enabled=False)
        self.to_crop = [
            ei
            for ei in self.files_to_process
            if ei.iratio != ei.oratio and ei.crop
        ]
        while self.to_crop:
            self.show_message("Cropping files")
            self.current_file = self.to_crop.pop(0)
            if self.current_file.auto_crop:
                self.auto_crop_file(self.current_file)
                self.encode_callback()
            else:
                self.show_crop_modal(
                    hide_x=self.current_file.iratio > self.current_file.oratio
                )
            return

        self.output_files = list()

        while self.files_to_process:
            einfo = self.files_to_process.pop(0)
            self.current_file = einfo
            encoder_ = Encoder.new(einfo)

            dpg.configure_item(
                Tags.encode_button,
                label=f"Encoding ({len(self.files_to_process)} more in queue)",
            )

            if einfo.uses_gifski:
                self.show_message(
                    f"Creating image sequence from {os.path.basename(einfo.iname)} for gifski"
                )
                tmp = Encoder.video_to_png(einfo)
                self.temp_files.append(tmp)
            self.show_message(f"Encoding {einfo.iname}")

            self.output_files.append(encoder_.encode())
            self.current_file = None

        assert len(self.files_to_process) == 0, "files_to_process not cleared"
        dpg.configure_item(
            Tags.encode_button,
            label=f"Encode ({len(self.files_to_process)} queued)",
        )

        for out in self.output_files:
            size = os.stat(out).st_size
            size_str = (
                f"{size / 1_000:.2f}KB"
                if size < 1_000_000
                else f"{size / 1_000_000:.2f}MB"
            )
            self.show_message(f"Created {out} ({size_str})")
        self.clean_up()
        self.reset_values()
        dpg.configure_item(Tags.encode_button, enabled=True)
        dpg.configure_item(Tags.queue_button, enabled=True)

    # Crop modal callbacks

    def preview_file_callback(self):
        dpg.set_value(
            Tags.preview_message,
            "Cropping...",
        )
        dpg.configure_item(Tags.preview_file_button, enabled=False)
        dpg.configure_item(Tags.crop_confirm_button, enabled=False)
        einfo = self.current_file

        if einfo.iratio > einfo.oratio:
            w = einfo.iwidth
            # stretch this by default
            h = int(einfo.iwidth * einfo.ohscale)
        else:
            h = einfo.iheight
            # stretch this by default
            w = int(einfo.iheight * (einfo.owscale / einfo.ohscale))
        y = dpg.get_value(Tags.crop_y_slider)
        x = dpg.get_value(Tags.crop_x_slider)
        if y > einfo.iheight - h:
            y = einfo.iheight - h
        if x > einfo.iwidth - w:
            x = einfo.iwidth - w
        cropped_file = Encoder.crop(einfo.iname, w, h, x, y)
        self.cropped_filenames.append(cropped_file)
        dpg.set_value(
            Tags.preview_message,
            "File Cropped. Remember to close file after viewing so it can be removed during cleanup at the end",
        )
        os.startfile(self.cropped_filenames[-1])
        dpg.configure_item(Tags.preview_file_button, enabled=True)
        dpg.configure_item(Tags.crop_confirm_button, enabled=True)

    def crop_confirm_callback(self):
        einfo = self.current_file
        einfo.iname = self.cropped_filenames[-1]
        einfo.iwidth, einfo.iheight = Encoder.get_dimensions(
            self.cropped_filenames[-1]
        )
        dpg.configure_item(Tags.crop_window, show=False)
        self.current_file = None
        self.encode_callback()

    def print_value(self, sender, app_data, user_data):
        """For debugging"""
        print(f"{sender=}")
        print(f"{app_data=}")
        print(f"{user_data=}")


class GuiClient:
    WIDTH = 960
    HEIGHT = 595
    FONT = Path(__file__).parent / "fonts" / "Roboto-Medium.ttf"
    FONT_SIZE = 18

    def __init__(self, gh: GuiHandler):
        dpg.create_context()
        self.gh = gh

        if self.gh.dependency_message:
            self.exit_message(self.gh.dependency_message)
        else:
            self.init_gui()

        dpg.create_viewport(
            title=self.gh.title, width=self.WIDTH, height=self.HEIGHT
        )
        dpg.setup_dearpygui()
        dpg.show_viewport()

    def run(self):
        dpg.set_primary_window(Tags.main_window, True)
        if self.gh.DEBUG:
            dpg.show_item_registry()
            dpg.show_debug()
        if self.gh.STYLE:
            dpg.show_style_editor()
        while dpg.is_dearpygui_running():
            dpg.render_dearpygui_frame()
        dpg.destroy_context()

    def exit_message(self, message):
        with dpg.window(tag=Tags.main_window, label="Exit"):
            dpg.add_text(message)

    def init_gui(self):
        with dpg.font_registry():
            font = dpg.add_font(self.FONT, self.FONT_SIZE, tag="roboto")
            dpg.bind_font(font)

        with dpg.window(tag=Tags.main_window, label="DiscordGifs"):
            default_fps = 30
            t = Tags()
            # Filename
            dpg.add_text(
                "Enter full path to video file or first image in a png sequence",
            )

            fps_prompt = "Enter output fps"
            dpg.add_input_text(
                tag=t.filename_input,
                label="",
                default_value="",
                callback=self.gh.filename_callback,
                user_data={
                    "default_prompt": fps_prompt,
                    "default_fps": default_fps,
                },
                width=self.WIDTH - 200,
            )

            # FPS
            dpg.add_spacer(height=10)
            dpg.add_text(fps_prompt, tag=t.fps_text)
            dpg.add_input_int(
                tag=t.fps_input,
                label="",
                default_value=default_fps,
                min_value=10,
                max_value=50,
                min_clamped=True,
                max_clamped=True,
                width=self.WIDTH - 200,
            )

            # Output type
            dpg.add_spacer(height=10)
            dpg.add_text("Enter output type:")
            dpg.add_radio_button(
                tag=t.output_radio_button,
                items=OUTPUT_CHOICES,
                horizontal=True,
                default_value=OUTPUT_CHOICES[0],
            )

            # Crop or stretch
            dpg.add_spacer(height=10)
            dpg.add_text(
                "Crop if dimensions don't match output? (recommended)"
            )
            dpg.add_checkbox(
                tag=t.crop_checkbox,
                label="Crop",
            )
            dpg.set_value(t.crop_checkbox, True)

            # Auto crop
            dpg.add_spacer(height=10)
            dpg.add_text(
                "Select to auto crop evenly at the edges (when needed). "
                "Uncheck to choose crop manually"
            )
            dpg.add_checkbox(
                tag=t.auto_crop_checkbox,
                label="Auto crop",
            )

            # Main window Buttons
            dpg.add_spacer(height=10)
            with dpg.group(horizontal=True):
                # Queue file
                dpg.add_button(
                    tag=t.queue_button,
                    label="Queue file",
                    callback=self.gh.add_file_callback,
                )

                # Encode file
                dpg.add_button(
                    tag=t.encode_button,
                    label=f"Encode ({len(self.gh.files_to_process)} queued)",
                    callback=self.gh.encode_callback,
                )

            # Crop Modal
            crop_width = self.WIDTH - 200
            crop_height = int(self.HEIGHT / 2) - 100

            midw = int(self.WIDTH / 2) - int(crop_width / 2)
            midh = int(self.HEIGHT / 2) - int(crop_height / 1.25)

            with dpg.window(
                tag=t.crop_window,
                label="Crop",
                modal=True,
                show=False,
                pos=(midw, midh),
                width=crop_width,
                height=crop_height,
                no_close=True,
            ):
                dpg.add_text(tag=t.crop_message, wrap=crop_width)
                dpg.add_slider_int(
                    tag=t.crop_y_slider,
                    label="Y value to start cropping at. Top=0",
                    min_value=0,
                    max_value=1,
                    clamped=True,
                )
                dpg.add_slider_int(
                    tag=t.crop_x_slider,
                    label="X value to start cropping at. Left=0",
                    min_value=0,
                    max_value=1,
                    clamped=True,
                )
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        tag=t.preview_file_button,
                        label="Crop and Preview",
                        callback=self.gh.preview_file_callback,
                    )
                    dpg.add_button(
                        tag=t.crop_confirm_button,
                        label="Confirm",
                        callback=self.gh.crop_confirm_callback,
                        enabled=False,
                    )

                dpg.add_text(tag=t.preview_message, wrap=crop_width)

            # Output
            dpg.add_input_text(
                tag=t.messages,
                multiline=True,
                width=self.WIDTH,
                readonly=True,
            )


def check_dependencies():
    if not shutil.which("ffmpeg"):
        return "ffmpeg is not installed. Please install it from https://ffmpeg.org/"
    if not shutil.which("ffprobe"):
        return "ffprobe is not installed. Please install it from https://ffmpeg.org/"
    if not shutil.which("gifski"):
        return (
            "gifski is not installed. Please install it from https://gif.ski/"
        )


def main():
    gh = GuiHandler()
    gh.dependency_message = check_dependencies()
    gui = GuiClient(gh)
    gui.run()


if __name__ == "__main__":
    main()
