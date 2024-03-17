from dataclasses import dataclass

@dataclass(frozen=True)
class OutputSize:
    EMOTE = 256_000
    STICKER = 500_000
    BANNER = 10_000_000
    SERVER_ICON = 8_000_000
    PFP = 8_000_000

@dataclass(frozen=True)
class InitialFrameSize:
    EMOTE = 110, 100
    STICKER = 200, 200
    BANNER = 800, 320
    PFP = 500, 500

BANNER_RATIO = 1, 0.4
