"""Attempt recording: per-speaker mono captures + a stereo call recording.

Two tracks are captured at the audio boundary (migration doc §10):

* ``caller`` — the audio we transmit to the target (mono, pcm_s16le);
* ``agent``  — the audio we receive from the target (mono, pcm_s16le).

Both are kept as immutable originals for overlap analysis. On finalize we also
produce one **stereo** interleaved recording (caller = left, agent = right) as
the human-listenable call recording. Tracks with different sample rates are
resampled to the capture rate before mixing.
"""

from __future__ import annotations

import array
import hashlib
import sys
from dataclasses import dataclass, field

from voiceeval.runtime.connections import AudioChunk
from voiceeval.runtime.media.audio import Resampler, pcm_to_wav
from voiceeval.runtime.media.recorder import MediaArtifactRecord, MediaRecorder


def _pcm_samples(data: bytes, *, endian: str) -> array.array:
    samples = array.array("h")
    samples.frombytes(data[: len(data) - (len(data) % 2)])
    if endian == "big" and sys.byteorder == "little":
        samples.byteswap()
    return samples


def interleave_stereo(left: bytes, right: bytes) -> bytes:
    """Interleave two pcm_s16le mono byte strings into pcm_s16le stereo.

    The shorter track is zero-padded so no audio is dropped.
    """
    total = max(len(left), len(right))
    left = left.ljust(total, b"\x00")
    right = right.ljust(total, b"\x00")
    la = _pcm_samples(left, endian="little")
    ra = _pcm_samples(right, endian="little")
    out = array.array("h", [0] * (len(la) * 2))
    out[0::2] = la
    out[1::2] = ra
    if sys.byteorder == "big":
        out.byteswap()
    return out.tobytes()


@dataclass
class AttemptRecording:
    """Accumulates the caller and agent tracks for one attempt."""

    sample_rate: int = 24_000
    clock_domain: str = "runner_monotonic"
    _caller: MediaRecorder = field(init=False)
    _agent: MediaRecorder = field(init=False)
    _resampler: Resampler = field(init=False)
    _finalized: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        self._caller = MediaRecorder(
            track="caller", sample_rate=self.sample_rate, clock_domain=self.clock_domain
        )
        self._agent = MediaRecorder(
            track="agent", sample_rate=self.sample_rate, clock_domain=self.clock_domain
        )
        self._resampler = Resampler()

    def _normalize(self, chunk: AudioChunk) -> AudioChunk:
        if chunk.sample_rate != self.sample_rate:
            return self._resampler.resample(chunk, self.sample_rate)
        return chunk

    def append_caller(self, chunk: AudioChunk) -> None:
        self._caller.append(self._normalize(chunk))

    def append_agent(self, chunk: AudioChunk) -> None:
        self._agent.append(self._normalize(chunk))

    @property
    def caller_duration_ms(self) -> int:
        return self._caller.duration_ms

    @property
    def agent_duration_ms(self) -> int:
        return self._agent.duration_ms

    def finalize(self) -> list[MediaArtifactRecord]:
        """Seal the tracks and produce the stereo call recording.

        Returns ``[caller(mono), agent(mono), mixed(stereo)]``, each wrapped as a
        playable ``.wav`` (RIFF/WAVE) container.
        """
        if self._finalized:
            raise RuntimeError("attempt recording already finalized")
        self._finalized = True
        raw_caller = self._caller.finalize()
        raw_agent = self._agent.finalize()
        raw_mixed = _stereo_record(raw_caller, raw_agent)
        return [_as_wav(raw_caller), _as_wav(raw_agent), _as_wav(raw_mixed)]


def _as_wav(record: MediaArtifactRecord) -> MediaArtifactRecord:
    """Wrap a raw-PCM capture as a playable WAV artifact."""
    wav = pcm_to_wav(
        record.data or b"", sample_rate=record.sample_rate, channels=record.channels
    )
    return MediaArtifactRecord(
        track=record.track,
        representation=record.representation,
        format="wav",
        sample_rate=record.sample_rate,
        channels=record.channels,
        duration_ms=record.duration_ms,
        size_bytes=len(wav),
        sha256=hashlib.sha256(wav).hexdigest(),
        clock_domain=record.clock_domain,
        data=wav,
    )


def _stereo_record(
    caller: MediaArtifactRecord, agent: MediaArtifactRecord
) -> MediaArtifactRecord:
    stereo = interleave_stereo(caller.data or b"", agent.data or b"")
    duration_ms = max(caller.duration_ms, agent.duration_ms)
    return MediaArtifactRecord(
        track="mixed",
        representation="mixed",
        format="pcm_s16le",
        sample_rate=caller.sample_rate,
        channels=2,
        duration_ms=duration_ms,
        size_bytes=len(stereo),
        sha256=hashlib.sha256(stereo).hexdigest(),
        clock_domain=caller.clock_domain,
        data=stereo,
    )


__all__ = ["AttemptRecording", "interleave_stereo"]
