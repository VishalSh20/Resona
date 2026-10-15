"""TargetLink implementations (room / SIP / protocol bridge / WHIP)."""

from __future__ import annotations

from voiceeval.runtime.livekit.target_links.base import TargetLink, TargetLinkCapabilities
from voiceeval.runtime.livekit.target_links.bridge import BridgeLink
from voiceeval.runtime.livekit.target_links.registry import (
    TargetLinkRegistry,
    get_target_link_registry,
    set_target_link_registry,
)
from voiceeval.runtime.livekit.target_links.room import RoomLink
from voiceeval.runtime.livekit.target_links.sip import SIP_STATUS_TO_REASON, SipLink
from voiceeval.runtime.livekit.target_links.whip import WhipLink

__all__ = [
    "BridgeLink",
    "RoomLink",
    "SIP_STATUS_TO_REASON",
    "SipLink",
    "TargetLink",
    "TargetLinkCapabilities",
    "TargetLinkRegistry",
    "WhipLink",
    "get_target_link_registry",
    "set_target_link_registry",
]
