import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple

from consts import BANNER_RATIO, InitialFrameSize, OutputSize
from utils import get_available_name

OUTPUT_CHOICES = ["emote", "pfp", "server icon", "banner", "sticker"]


@dataclass
class EncodingInfo(ABC):
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
    uses_gifski: bool

    def __init__(
        self,
        iname: str,
        iwidth: int,
        iheight: int,
        icodec: str,
        out_choice: str,
        fps: int,
    ):
        self.iname = iname

        self.iwidth = iwidth
        self.iheight = iheight
        self.icodec = icodec
        self.fps = fps
        self.out_choice = out_choice

    @classmethod
    def new(
        cls,
        iname: str,
        iwidth: int,
        iheight: int,
        icodec: str,
        out_choice: str,
        fps: int,
    ):
        out_choice = out_choice.lower().strip()
        if out_choice not in OUTPUT_CHOICES:
            raise ValueError(f"Invalid output choice: {out_choice}")
        if out_choice == "banner":
            return BannerEncodingInfo(iname, iwidth, iheight, icodec, fps)
        elif out_choice == "emote":
            return EmoteEncodingInfo(iname, iwidth, iheight, icodec, fps)
        elif out_choice == "sticker":
            return StickerEncodingInfo(iname, iwidth, iheight, icodec, fps)
        else:
            return PfpEncodingInfo(iname, iwidth, iheight, icodec, fps)

    @property
    def iratio(self) -> float:
        return self.iheight / self.iwidth

    @property
    def oratio(self) -> float:
        return self.ohscale / self.owscale

    @property
    @abstractmethod
    def init_odims(self) -> Tuple[int, int]:
        raise NotImplementedError("init_odims must be implemented")

    @property
    def is_sticker(self) -> bool:
        return self.out_choice == "sticker"

    @property
    def width_change_margin(self) -> int:
        return 1 if self.osize_limit == OutputSize.EMOTE else 20

    def max_width_check(self, width: int) -> bool:
        """
        Return True if given width will take video out of bounds based on the
        input and output widths and heights
        """
        output_height = (width * self.ohscale) * self.oratio
        return width >= self.iwidth or (output_height > self.iheight)


class BannerEncodingInfo(EncodingInfo):
    def __init__(
        self, iname: str, iwidth: int, iheight: int, icodec: str, fps: int
    ):
        super().__init__(iname, iwidth, iheight, icodec, "banner", fps)
        self.owscale, self.ohscale = BANNER_RATIO
        self.osize_limit = OutputSize.BANNER
        self.osize_range = 0.85
        self.oname = get_available_name(iname, ext=".gif")
        self.uses_gifski = shutil.which("gifski") is not None

    @property
    def init_odims(self) -> Tuple[int, int]:
        """Return the initial output dimensions based on the out_choice"""
        return InitialFrameSize.BANNER


class EmoteEncodingInfo(EncodingInfo):
    def __init__(
        self, iname: str, iwidth: int, iheight: int, icodec: str, fps: int
    ):
        super().__init__(iname, iwidth, iheight, icodec, "emote", fps)
        self.owscale, self.ohscale = 1, 1
        self.osize_limit = OutputSize.EMOTE
        self.osize_range = 0.95
        self.oname = get_available_name(iname, ext=".gif")
        self.uses_gifski = False

    @property
    def init_odims(self) -> Tuple[int, int]:
        """Return the initial output dimensions based on the out_choice"""
        return InitialFrameSize.EMOTE


class PfpEncodingInfo(EncodingInfo):
    def __init__(
        self, iname: str, iwidth: int, iheight: int, icodec: str, fps: int
    ):
        super().__init__(iname, iwidth, iheight, icodec, "pfp", fps)
        self.owscale, self.ohscale = 1, 1
        self.osize_limit = OutputSize.PFP
        self.osize_range = 0.85
        self.oname = get_available_name(iname, ext=".gif")
        self.uses_gifski = shutil.which("gifski") is not None

    @property
    def init_odims(self) -> Tuple[int, int]:
        """Return the initial output dimensions based on the out_choice"""
        return InitialFrameSize.PFP


class StickerEncodingInfo(EncodingInfo):
    def __init__(
        self, iname: str, iwidth: int, iheight: int, icodec: str, fps: int
    ):
        super().__init__(iname, iwidth, iheight, icodec, "sticker", fps)
        self.owscale, self.ohscale = 1, 1
        self.osize_limit = OutputSize.STICKER
        self.osize_range = 0.95
        self.oname = get_available_name(iname, ext=".png")
        self.uses_gifski = False

    @property
    def init_odims(self) -> Tuple[int, int]:
        """Return the initial output dimensions based on the out_choice"""
        return InitialFrameSize.STICKER
