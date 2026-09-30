"""Sarvam provider implementations (Bulbul TTS, Saaras ASR).

Sarvam exposes streaming WebSocket endpoints; these providers translate that
protocol into the provider-agnostic :mod:`base` contracts. The official
``sarvamai`` SDK is used as the transport because it is the vendor-recommended
client and handles the streaming framing correctly (in particular the Python
SDK's per-message helper accepts only WAV, so raw caller PCM is wrapped in a WAV
container before it is sent).

Credentials come from configuration (``SARVAM_API_KEY``), never hardcoded.
Without a key the providers fail fast rather than silently producing nothing.
"""

from __future__ import annotations

import asyncio
import base64
import struct
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass, field

from sarvamai import AsyncSarvamAI, AudioOutput, ErrorResponse, EventResponse
from sarvamai.types.speech_to_text_streaming_response import (
    SpeechToTextStreamingResponse,
)

from voiceeval.core.config import get_settings
from voiceeval.core.errors import DependencyUnavailableError, ValidationError
from voiceeval.runtime.connections import AudioChunk
from voiceeval.runtime.languages import normalize_bcp47
from voiceeval.runtime.providers.base import SynthesisRequest, Transcript

# v1 models. bulbul:v3 is the current TTS model; saaras:v4 is the current STT
# model. Both are overridable per provider instance.
DEFAULT_TTS_MODEL = "bulbul:v3"
DEFAULT_ASR_MODEL = "saaras:v4"
# bulbul:v3's default speaker; speaker names are model-specific and lowercase.
DEFAULT_SPEAKER = "shubh"
DEFAULT_SAMPLE_RATE = 16000
_RECV_TIMEOUT_S = 20.0


@dataclass(frozen=True)
class SarvamConnection:
    """Connection parameters shared by the Sarvam providers."""

    api_key: str | None = None
    tts_model: str = DEFAULT_TTS_MODEL
    asr_model: str = DEFAULT_ASR_MODEL
    speaker: str = DEFAULT_SPEAKER
    language: str = "en-IN"
    timeout_s: float = _RECV_TIMEOUT_S
    idle_timeout_s: float = 1.5
    extra: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_settings(cls) -> "SarvamConnection":
        return cls(api_key=get_settings().sarvam_api_key)

    def require_key(self) -> str:
        if not self.api_key:
            raise ValidationError(
                "SARVAM_API_KEY is not configured; Sarvam providers are unavailable"
            )
        return self.api_key

    def client(self) -> AsyncSarvamAI:
        return AsyncSarvamAI(api_subscription_key=self.require_key())


async def _aclose_client(client: AsyncSarvamAI) -> None:
    """Best-effort teardown of the SDK's underlying httpx client.

    ``AsyncSarvamAI`` exposes no ``close()``; the streaming sockets are closed by
    their context managers, but the shared httpx client must be released too.
    The lookup is defensive so a future SDK that renames the attribute degrades
    to a no-op instead of raising.
    """
    wrapper = getattr(client, "_client_wrapper", None)
    httpx_client = getattr(wrapper, "httpx_client", None)
    aclose = getattr(httpx_client, "aclose", None)
    if aclose is not None:
        await aclose()


def pcm_to_wav(
    pcm: bytes, *, sample_rate: int = DEFAULT_SAMPLE_RATE, channels: int = 1
) -> bytes:
    """Wrap raw little-endian 16-bit PCM in a minimal RIFF/WAVE container.

    The Sarvam Python SDK's transcription helper accepts WAV, so caller PCM is
    wrapped rather than sent raw.
    """
    byte_rate = sample_rate * channels * 2
    header = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE"
    header += b"fmt " + struct.pack(
        "<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, channels * 2, 16
    )
    header += b"data" + struct.pack("<I", len(pcm))
    return header + pcm


class SarvamBulbulTTS:
    """Streaming TTS over Sarvam Bulbul.

    Requests linear16 PCM at the target sample rate so returned audio drops
    straight into :class:`AudioChunk` with no transcoding.
    """

    name = "sarvam_bulbul"

    def __init__(self, connection: SarvamConnection | None = None) -> None:
        self._connection = connection or SarvamConnection.from_settings()

    async def synthesize(self, request: SynthesisRequest) -> AsyncIterator[AudioChunk]:
        connection = self._connection
        client = connection.client()
        try:
            async with client.text_to_speech_streaming.connect(
                model=connection.tts_model,
                send_completion_event="true",
                api_subscription_key=connection.require_key(),
            ) as socket:
                await socket.configure(
                    target_language_code=normalize_bcp47(
                        request.language or connection.language
                    ),
                    speaker=request.voice or connection.speaker,
                    speech_sample_rate=request.sample_rate or DEFAULT_SAMPLE_RATE,
                    output_audio_codec="linear16",
                )
                await socket.convert(request.text)
                await socket.flush()

                while True:
                    try:
                        message = await asyncio.wait_for(
                            socket.recv(), timeout=connection.timeout_s
                        )
                    except asyncio.TimeoutError:
                        break
                    if isinstance(message, AudioOutput):
                        audio = base64.b64decode(message.data.audio)
                        if not audio:
                            continue
                        yield AudioChunk(
                            data=audio,
                            sample_rate=request.sample_rate or DEFAULT_SAMPLE_RATE,
                            channels=request.channels,
                            format="pcm_s16le",
                        )
                    elif isinstance(message, EventResponse):
                        if message.data.event_type == "final":
                            break
                    elif isinstance(message, ErrorResponse):
                        raise DependencyUnavailableError(
                            f"sarvam tts error: {message.data.message}"
                        )
        finally:
            await _aclose_client(client)


class SarvamBulbulStreamingTTS:
    """Persistent-connection Bulbul TTS: one socket per call.

    The per-utterance :class:`SarvamBulbulTTS` pays a fresh websocket connect +
    configure on every caller turn (~1 s of dead air); this keeps the socket
    open for the whole call and issues ``convert``/``flush`` per utterance.
    The socket is dropped on error so the caller's retry reconnects cleanly.
    """

    name = "sarvam_bulbul_persistent"

    def __init__(self, connection: SarvamConnection | None = None) -> None:
        self._connection = connection or SarvamConnection.from_settings()
        self._client: AsyncSarvamAI | None = None
        self._ctx: object | None = None
        self._socket: object | None = None
        self._lock = asyncio.Lock()
        self._mid_stream = False

    async def open(self) -> None:
        """Pre-open the socket (call start) so turn one pays no connect cost."""
        async with self._lock:
            await self._ensure_open()

    async def _ensure_open(self) -> None:
        if self._socket is not None:
            return
        self._client = self._connection.client()
        self._ctx = self._client.text_to_speech_streaming.connect(
            model=self._connection.tts_model,
            send_completion_event="true",
            api_subscription_key=self._connection.require_key(),
        )
        self._socket = await self._ctx.__aenter__()  # type: ignore[attr-defined]
        self._mid_stream = False

    async def _drain_stale(self) -> None:
        """Finish an abandoned utterance so its audio is not read next turn."""
        while True:
            try:
                message = await asyncio.wait_for(self._socket.recv(), timeout=2.0)  # type: ignore[attr-defined]
            except (asyncio.TimeoutError, Exception):
                break
            if isinstance(message, EventResponse) and message.data.event_type == "final":
                break

    async def synthesize(self, request: SynthesisRequest) -> AsyncIterator[AudioChunk]:
        async with self._lock:
            await self._ensure_open()
            try:
                if self._mid_stream:
                    await self._drain_stale()
                    self._mid_stream = False
                await self._socket.configure(  # type: ignore[attr-defined]
                    target_language_code=normalize_bcp47(
                        request.language or self._connection.language
                    ),
                    speaker=request.voice or self._connection.speaker,
                    speech_sample_rate=request.sample_rate or DEFAULT_SAMPLE_RATE,
                    output_audio_codec="linear16",
                )
                await self._socket.convert(request.text)  # type: ignore[attr-defined]
                await self._socket.flush()  # type: ignore[attr-defined]
                self._mid_stream = True
                while True:
                    try:
                        message = await asyncio.wait_for(
                            self._socket.recv(),  # type: ignore[attr-defined]
                            timeout=self._connection.timeout_s,
                        )
                    except asyncio.TimeoutError:
                        break
                    if isinstance(message, AudioOutput):
                        audio = base64.b64decode(message.data.audio)
                        if audio:
                            yield AudioChunk(
                                data=audio,
                                sample_rate=request.sample_rate or DEFAULT_SAMPLE_RATE,
                                channels=request.channels,
                                format="pcm_s16le",
                            )
                    elif isinstance(message, EventResponse):
                        if message.data.event_type == "final":
                            break
                    elif isinstance(message, ErrorResponse):
                        raise DependencyUnavailableError(
                            f"sarvam tts error: {message.data.message}"
                        )
            except Exception:
                await self._drop()
                raise
            finally:
                self._mid_stream = False

    async def _drop(self) -> None:
        ctx, client = self._ctx, self._client
        self._ctx = self._socket = self._client = None
        if ctx is not None:
            try:
                await ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - best-effort teardown
                pass
        if client is not None:
            await _aclose_client(client)

    async def aclose(self) -> None:
        await self._drop()


class SarvamSaarasASR:
    """Streaming ASR over Sarvam Saaras."""

    name = "sarvam_saaras"

    def __init__(self, connection: SarvamConnection | None = None) -> None:
        self._connection = connection or SarvamConnection.from_settings()

    async def transcribe(
        self, audio: Iterable[AudioChunk], *, language: str | None = None
    ) -> AsyncIterator[Transcript]:
        connection = self._connection
        chunks = list(audio)
        sample_rate = chunks[0].sample_rate if chunks else DEFAULT_SAMPLE_RATE
        pcm = b"".join(chunk.data for chunk in chunks)
        wav = pcm_to_wav(pcm, sample_rate=sample_rate)

        client = connection.client()
        try:
            async with client.speech_to_text_streaming.connect(
                language_code=normalize_bcp47(language or connection.language),
                model=connection.asr_model,
                mode="transcribe",
                sample_rate=str(sample_rate),
                input_audio_codec="wav",
                flush_signal="true",
                high_vad_sensitivity="true",
                api_subscription_key=connection.require_key(),
            ) as socket:
                await socket.transcribe(
                    audio=base64.b64encode(wav).decode("ascii"),
                    encoding="audio/wav",
                    sample_rate=sample_rate,
                )
                await socket.flush()

                # A single audio stream may be split into several endpointed
                # utterances, each with its own final transcript; accumulate
                # them and emit one consolidated result when the stream goes
                # idle. The first message waits the full receive timeout; later
                # ones use the shorter idle timeout so the tail is not slow.
                segments: list[str] = []
                detected_language: str | None = None
                confidence: float | None = None
                first = True
                while True:
                    wait_s = connection.timeout_s if first else connection.idle_timeout_s
                    try:
                        message = await asyncio.wait_for(socket.recv(), timeout=wait_s)
                    except asyncio.TimeoutError:
                        break
                    first = False
                    if not isinstance(message, SpeechToTextStreamingResponse):
                        continue
                    if message.type == "events":
                        continue
                    data = message.data
                    text = getattr(data, "transcript", None)
                    if text:
                        segments.append(text.strip())
                        detected_language = (
                            getattr(data, "language_code", None) or detected_language
                        )
                        probability = getattr(data, "language_probability", None)
                        if probability is not None:
                            confidence = probability

                joined = " ".join(segment for segment in segments if segment).strip()
                if joined:
                    yield Transcript(
                        text=joined,
                        is_final=True,
                        language=detected_language,
                        confidence=confidence,
                    )
        finally:
            await _aclose_client(client)


@dataclass(frozen=True)
class StreamingAsrEvent:
    """One observation from the streaming ASR: text or a VAD speech signal."""

    kind: str  # "transcript" | "speech_start" | "speech_end"
    text: str = ""


class SarvamStreamingASR:
    """Live streaming ASR over Sarvam Saaras.

    Audio chunks are pushed as they arrive; endpointed utterances surface as
    transcripts. This transcribes the *target's* audio ourselves, so the caller
    listens to the audio instead of trusting the provider's own captions.

    ``vad_signals`` is enabled, so the stream also carries server-side
    START_SPEECH / END_SPEECH events — the caller's floor tracker runs on these
    rather than guessing turn ends from transcript timing.
    """

    name = "sarvam_streaming_asr"

    def __init__(
        self,
        connection: SarvamConnection | None = None,
        *,
        language: str = "en-IN",
        sample_rate: int = DEFAULT_SAMPLE_RATE,
    ) -> None:
        self._connection = connection or SarvamConnection.from_settings()
        self._language = language
        self._sample_rate = sample_rate
        self._client: AsyncSarvamAI | None = None
        self._ctx: object | None = None
        self._socket: object | None = None

    async def __aenter__(self) -> "SarvamStreamingASR":
        self._client = self._connection.client()
        self._ctx = self._client.speech_to_text_streaming.connect(
            # "unknown" lets Saaras auto-detect the language, which is what a
            # code-switching scenario needs; anything else is normalized.
            language_code=(
                "unknown"
                if self._language == "unknown"
                else normalize_bcp47(self._language)
            ),
            model=self._connection.asr_model,
            sample_rate=str(self._sample_rate),
            input_audio_codec="pcm_s16le",
            # Less eager endpointing: high sensitivity splits a single agent turn
            # into many one-phrase fragments, which makes the caller reply to
            # half-sentences.
            high_vad_sensitivity="false",
            flush_signal="true",
            vad_signals="true",
            api_subscription_key=self._connection.require_key(),
        )
        self._socket = await self._ctx.__aenter__()  # type: ignore[attr-defined]
        return self

    async def push(self, chunk: AudioChunk) -> None:
        if self._socket is None:
            return
        # The per-message ``encoding`` is fixed to "audio/wav" by the SDK model;
        # the real format is declared once at connect (``input_audio_codec=
        # "pcm_s16le"``), so raw PCM is sent as-is.
        await self._socket.transcribe(  # type: ignore[attr-defined]
            audio=base64.b64encode(chunk.data).decode("ascii"),
            sample_rate=chunk.sample_rate or self._sample_rate,
        )

    async def flush(self) -> None:
        if self._socket is not None:
            await self._socket.flush()  # type: ignore[attr-defined]

    async def stream(self) -> AsyncIterator[StreamingAsrEvent]:
        """Yield transcripts *and* VAD speech signals as they arrive."""
        while self._socket is not None:
            message = await self._socket.recv()  # type: ignore[attr-defined]
            if getattr(message, "type", None) == "events":
                data = getattr(message, "data", None)
                signal = getattr(data, "signal_type", None)
                if signal == "START_SPEECH":
                    yield StreamingAsrEvent(kind="speech_start")
                elif signal == "END_SPEECH":
                    yield StreamingAsrEvent(kind="speech_end")
                continue
            data = getattr(message, "data", None)
            text = (getattr(data, "transcript", None) or "").strip()
            if text:
                yield StreamingAsrEvent(kind="transcript", text=text)

    async def transcripts(self) -> AsyncIterator[str]:
        async for event in self.stream():
            if event.kind == "transcript":
                yield event.text

    async def __aexit__(self, *exc: object) -> None:
        try:
            await self.flush()
        except Exception:  # pragma: no cover - best-effort
            pass
        if self._ctx is not None:
            try:
                await self._ctx.__aexit__(*exc)  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - best-effort
                pass
        if self._client is not None:
            await _aclose_client(self._client)
