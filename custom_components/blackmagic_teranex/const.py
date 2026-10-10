"""Constants for the Blackmagic Teranex integration."""

from __future__ import annotations

DOMAIN = "blackmagic_teranex"
DEFAULT_PORT = 9800
DEFAULT_NAME = "Teranex"

MANUFACTURER = "Blackmagic Design"

CONF_VIDEO_MODES = "video_modes"

# Last known identity of the unit, stored in the config entry so the device
# keeps its name, model and firmware in Home Assistant while it is switched off.
CONF_MODEL = "model"
CONF_SW_VERSION = "sw_version"

# How long setup waits for the first state dump before carrying on without
# it. Setup never fails on an unreachable unit; this only avoids entities
# briefly showing unknown when the unit is online.
SETUP_GRACE_PERIOD = 5.0

# Output formats offered by default. The device cannot enumerate its own
# format list, so this is a sensible starting set for a Teranex 2D; it can be
# replaced per config entry through the options flow. Whatever the device
# currently reports is always added to the list at runtime.
DEFAULT_VIDEO_MODES: tuple[str, ...] = (
    "625i50",
    "525i5994",
    "720p50",
    "720p5994",
    "720p60",
    "1080i50",
    "1080i5994",
    "1080i60",
    "1080p23976",
    "1080p24",
    "1080p25",
    "1080p2997",
    "1080p30",
    "1080p50",
    "1080p5994",
    "1080p60",
    "1080PsF23976",
    "1080PsF24",
    "1080PsF25",
    "1080PsF2997",
    "1080PsF30",
)

# Documented values for the Teranex 2D. The unit under test reports "SDI1"
# where the manual says "SDI", which is exactly why the current value is
# always merged into the option list.
VIDEO_SOURCES: tuple[str, ...] = ("SDI", "HDMI", "Composite", "Component")
AUDIO_SOURCES: tuple[str, ...] = ("Embedded", "AES", "RCA", "DB25")
ASPECT_RATIOS: tuple[str, ...] = (
    "Anamorphic",
    "Letterbox",
    "CentreCut",
    "14x9",
    "Smart",
)
ANALOG_OUTPUTS: tuple[str, ...] = ("Composite", "Component")

TEST_PATTERNS: tuple[str, ...] = (
    "None",
    "Black",
    "SMPTEBars",
    "Bars",
    "Multiburst",
    "Grid",
)
NO_SIGNAL_OUTPUTS: tuple[str, ...] = ("Black", "Bars")
TIMECODE_MODES: tuple[str, ...] = (
    "Off",
    "Input",
    "InputRegen",
    "Generate",
    "JamSync",
)
TIMECODE_DROP_FRAME: tuple[str, ...] = ("DF", "NDF")
TIMECODE_START_SOURCES: tuple[str, ...] = ("Input", "User")
AFD_INSERT_TYPES: tuple[str, ...] = ("Off", "Auto", "Bypass")

AUDIO_CHANNELS = 16
# Sources that can be mapped to an output channel.
AUDIO_ROUTING_SOURCES: tuple[str, ...] = (
    *(f"AudioIn{index}" for index in range(1, 17)),
    *(f"AudioDD{index}" for index in range(1, 9)),
    "TT750",
    "TT1500",
    "TT3000",
    "TT6000",
    "TTMute",
)

SERVICE_SAVE_PRESET = "save_preset"
ATTR_PRESET = "preset"
