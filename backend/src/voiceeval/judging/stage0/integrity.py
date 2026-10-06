"""Media integrity validation (spec §2.1.1).

A failure prevents silent substitution of a different file: the object bytes are
checked against the ``media_artifact`` row (sha256, size, sample rate, channels,
duration, format) and against the WAV container contract.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from voiceeval.judging.stage0.wav import WavData

EXPECTED_CHANNELS = {
    "caller_original": 1,
    "agent_original": 1,
    "mixed": 2,
}


@dataclass
class IntegrityResult:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.ok = False
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def _sha12(value: str) -> str:
    return value[:12].lower()


def validate_artifact(
    role: str,
    *,
    object_uri: str | None,
    sha256: str | None,
    size_bytes: int | None,
    sample_rate: int | None,
    channels: int | None,
    duration_ms: int | None,
    format_: str | None,
    data: bytes | None,
    wav: WavData | None,
    duration_tolerance_ms: int = 1500,
) -> IntegrityResult:
    result = IntegrityResult()

    if object_uri is None:
        result.fail("object_uri missing")
    if data is None:
        result.fail("object bytes missing")
        return result

    # Hash + size against the media_artifact row.
    digest = hashlib.sha256(data).hexdigest()
    if sha256 and digest.lower() != sha256.lower():
        result.fail(f"sha256 mismatch (object={digest[:12]}, row={sha256[:12]})")
    if size_bytes is not None and len(data) != size_bytes:
        result.fail(f"size mismatch (object={len(data)}, row={size_bytes})")
    if object_uri and sha256 and _sha12(sha256) not in object_uri:
        result.warn("sha12 not present in object key")

    if format_ is not None and format_ not in {"wav", "pcm_s16le"}:
        result.fail(f"unexpected format {format_!r}")
    if wav is None:
        result.fail("malformed WAV")
        return result

    if sample_rate is not None and wav.sample_rate != sample_rate:
        result.fail(f"sample rate mismatch (wav={wav.sample_rate}, row={sample_rate})")
    if channels is not None and wav.channels != channels:
        result.fail(f"channel count mismatch (wav={wav.channels}, row={channels})")

    expected = EXPECTED_CHANNELS.get(role)
    if expected is not None and wav.channels != expected:
        result.fail(f"{role} must have {expected} channel(s), got {wav.channels}")

    if duration_ms is not None:
        drift = abs(wav.duration_ms - duration_ms)
        if drift > duration_tolerance_ms:
            result.fail(f"duration drift {drift}ms exceeds tolerance")
        elif drift > 0:
            result.warn(f"duration drift {drift}ms within tolerance")

    return result


__all__ = ["EXPECTED_CHANNELS", "IntegrityResult", "validate_artifact"]
