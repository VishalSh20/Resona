"""PCM WAV decoding and RIFF validation (spec §0.3).

Only the canonical capture contract is supported: RIFF/WAVE, PCM, 16-bit. We
decode with the stdlib ``wave`` module + numpy, so no audio I/O dependency is
needed and the decoder is trivially testable.
"""

from __future__ import annotations

import io
import wave
from dataclasses import dataclass

import numpy as np

SUPPORTED_SAMPLE_WIDTH = 2  # 16-bit PCM


class WavDecodeError(ValueError):
    pass


@dataclass(frozen=True)
class WavData:
    samples: np.ndarray  # (n_samples, channels), float32 in [-1, 1]
    sample_rate: int
    channels: int
    sample_width: int
    n_frames: int

    @property
    def duration_ms(self) -> int:
        if self.sample_rate <= 0:
            return 0
        return int(self.n_frames * 1000 / self.sample_rate)

    def mono(self) -> np.ndarray:
        if self.samples.ndim == 1 or self.channels == 1:
            return self.samples.reshape(-1)
        return self.samples.mean(axis=1)

    def channel(self, index: int) -> np.ndarray:
        if self.channels == 1:
            return self.samples.reshape(-1)
        return self.samples[:, index]


def decode_wav(data: bytes) -> WavData:
    """Decode a 16-bit PCM WAV byte string into float samples."""
    try:
        with wave.open(io.BytesIO(data), "rb") as handle:
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            sample_rate = handle.getframerate()
            n_frames = handle.getnframes()
            raw = handle.readframes(n_frames)
    except (wave.Error, EOFError) as exc:
        raise WavDecodeError(f"malformed WAV: {exc}") from exc

    if sample_width != SUPPORTED_SAMPLE_WIDTH:
        raise WavDecodeError(
            f"unsupported sample width {sample_width * 8}-bit; expected 16-bit PCM"
        )

    ints = np.frombuffer(raw, dtype="<i2")
    if channels > 1:
        usable = (ints.size // channels) * channels
        ints = ints[:usable].reshape(-1, channels)
    samples = (ints.astype(np.float32) / 32768.0)
    return WavData(
        samples=samples,
        sample_rate=sample_rate,
        channels=channels,
        sample_width=sample_width,
        n_frames=int(samples.shape[0]),
    )


def validate_riff(data: bytes) -> list[str]:
    """Return a list of media-contract violations (empty means valid)."""
    errors: list[str] = []
    if len(data) < 12 or data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        return ["not a RIFF/WAVE container"]
    try:
        with wave.open(io.BytesIO(data), "rb") as handle:
            if handle.getcomptype() != "NONE":
                errors.append(f"unsupported compression: {handle.getcomptype()}")
            if handle.getsampwidth() != SUPPORTED_SAMPLE_WIDTH:
                errors.append("not 16-bit PCM")
    except (wave.Error, EOFError) as exc:
        errors.append(f"malformed WAV: {exc}")
    return errors


__all__ = ["SUPPORTED_SAMPLE_WIDTH", "WavData", "WavDecodeError", "decode_wav", "validate_riff"]
