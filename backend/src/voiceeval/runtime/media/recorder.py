"""Media recording and artifact metadata.

Original captures are immutable: a :class:`MediaRecorder` accumulates the exact
bytes it is given, and the resulting :class:`MediaArtifactRecord` carries the
content hash and size that make the capture verifiable. Derived representations
(analysis, clip, mixed) are produced from originals, never in place of them.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from voiceeval.runtime.connections import AudioChunk


@dataclass(frozen=True)
class MediaArtifactRecord:
    track: str
    representation: str
    format: str
    sample_rate: int
    channels: int
    duration_ms: int
    size_bytes: int
    sha256: str
    clock_domain: str = "runner_monotonic"
    # Original bytes, retained so the runtime can persist the immutable artifact
    # to the object store. Large captures are not held anywhere else.
    data: bytes | None = None


@dataclass
class MediaRecorder:
    """Accumulates one audio track into a single immutable artifact."""

    track: str
    representation: str = "original"
    format: str = "pcm_s16le"
    sample_rate: int = 16000
    channels: int = 1
    clock_domain: str = "runner_monotonic"
    _hash: "hashlib._Hash" = field(init=False, repr=False)
    _buffer: bytearray = field(init=False, repr=False)
    _size: int = field(init=False, default=0)
    _duration_ms: int = field(init=False, default=0)
    _started: bool = field(init=False, default=False)
    _closed: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        self._hash = hashlib.sha256()
        self._buffer = bytearray()

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def size_bytes(self) -> int:
        return self._size

    @property
    def duration_ms(self) -> int:
        return self._duration_ms

    def append(self, chunk: AudioChunk) -> None:
        if self._closed:
            raise RuntimeError("cannot append to a finalized media recorder")
        self._started = True
        self._hash.update(chunk.data)
        self._buffer.extend(chunk.data)
        self._size += len(chunk.data)
        self._duration_ms += (
            chunk.duration_ms
            if chunk.duration_ms is not None
            else int(len(chunk) * 1000 / max(1, chunk.sample_rate))
        )

    def finalize(self) -> MediaArtifactRecord:
        """Seal the artifact. Finalizing twice is a programming error."""
        if self._closed:
            raise RuntimeError("media recorder already finalized")
        self._closed = True
        return MediaArtifactRecord(
            track=self.track,
            representation=self.representation,
            format=self.format,
            sample_rate=self.sample_rate,
            channels=self.channels,
            duration_ms=self._duration_ms,
            size_bytes=self._size,
            sha256=self._hash.hexdigest(),
            clock_domain=self.clock_domain,
            data=bytes(self._buffer),
        )
