from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple

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

    BANNER_RATIO: tuple = 1, 0.4
    ONE_TO_ONE_RATIO: tuple = 1, 1

    # Starting frame sizes when encoding to gif
    EMOTE_FSIZE = 110, 100
    PFP_FSIZE = 500, 500
    BANNER_FSIZE = 800, 320
    STICKER_FSIZE = 200, 200

    EMOTE_SIZE = 256_000
    STICKER_SIZE = 500_000
    PFP_SIZE = 10_000_000

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
    @abstractmethod
    def uses_gifski(self) -> bool:
        raise NotImplementedError("uses_gifski must be implemented")

    @property
    def is_sticker(self) -> bool:
        return self.out_choice == "sticker"

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
        self.owscale, self.ohscale = EncodingInfo.BANNER_RATIO
        self.osize_limit = EncodingInfo.PFP_SIZE
        self.osize_range = 0.85
        self.oname = get_available_name(iname, ext=".gif")

    @property
    def init_odims(self) -> Tuple[int, int]:
        """Return the initial output dimensions based on the out_choice"""
        return EncodingInfo.BANNER_FSIZE

    @property
    def uses_gifski(self) -> bool:
        return True


class EmoteEncodingInfo(EncodingInfo):
    def __init__(
        self, iname: str, iwidth: int, iheight: int, icodec: str, fps: int
    ):
        super().__init__(iname, iwidth, iheight, icodec, "emote", fps)
        self.owscale, self.ohscale = EncodingInfo.ONE_TO_ONE_RATIO
        self.osize_limit = EncodingInfo.EMOTE_SIZE
        self.oname = get_available_name(iname, ext=".gif")
        self.osize_range = 0.95

    @property
    def init_odims(self) -> Tuple[int, int]:
        """Return the initial output dimensions based on the out_choice"""
        return EncodingInfo.EMOTE_FSIZE

    @property
    def uses_gifski(self) -> bool:
        return False


class PfpEncodingInfo(EncodingInfo):
    def __init__(
        self, iname: str, iwidth: int, iheight: int, icodec: str, fps: int
    ):
        super().__init__(iname, iwidth, iheight, icodec, "pfp", fps)
        self.owscale, self.ohscale = EncodingInfo.ONE_TO_ONE_RATIO
        self.osize_limit = EncodingInfo.PFP_SIZE
        self.osize_range = 0.85
        self.oname = get_available_name(iname, ext=".gif")

    @property
    def init_odims(self) -> Tuple[int, int]:
        """Return the initial output dimensions based on the out_choice"""
        return EncodingInfo.PFP_FSIZE

    @property
    def uses_gifski(self) -> bool:
        return True


class StickerEncodingInfo(EncodingInfo):
    def __init__(
        self, iname: str, iwidth: int, iheight: int, icodec: str, fps: int
    ):
        super().__init__(iname, iwidth, iheight, icodec, "sticker", fps)
        self.owscale, self.ohscale = EncodingInfo.ONE_TO_ONE_RATIO
        self.osize_limit = EncodingInfo.STICKER_SIZE
        self.osize_range = 0.95
        self.oname = get_available_name(iname, ext=".png")

    @property
    def init_odims(self) -> Tuple[int, int]:
        """Return the initial output dimensions based on the out_choice"""
        return EncodingInfo.STICKER_FSIZE

    @property
    def uses_gifski(self) -> bool:
        return False
