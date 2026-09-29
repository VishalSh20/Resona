"""Application configuration via pydantic-settings.

Environment variables are the source of truth. No secret may be committed;
this module only reads from the process environment (optionally a local ``.env``).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Database
    database_url: str = "postgresql+asyncpg://voiceeval:voiceeval@localhost:5432/voiceeval"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret: str = "change-me-in-production-use-a-real-32-byte-secret"
    jwt_issuer: str = "voiceeval"
    jwt_access_token_expire_minutes: int = 60

    # Object storage
    object_storage_mode: Literal["local", "s3"] = "local"
    local_object_storage_path: str = "./data/object-store"

    # S3. The canonical ``S3_*`` names are accepted alongside the common AWS
    # names (``AWS_REGION``, ``AWS_ACCESS_TOKEN``, ``AWS_ACCESS_SECRET``,
    # ``S3_BUCKET_NAME``) so either spelling in ``.env`` is picked up.
    s3_endpoint_url: str | None = None
    s3_region: str = Field(
        default="us-east-1",
        validation_alias=AliasChoices("S3_REGION", "AWS_REGION"),
    )
    s3_bucket: str = Field(
        default="voiceeval",
        validation_alias=AliasChoices("S3_BUCKET", "S3_BUCKET_NAME"),
    )
    s3_access_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("S3_ACCESS_KEY", "AWS_ACCESS_TOKEN"),
    )
    s3_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("S3_SECRET_KEY", "AWS_ACCESS_SECRET"),
    )

    # Master key used to encrypt provider credentials at rest (a Fernet key,
    # base64, 32 bytes). Must be set before storing integration secrets.
    secret_encryption_key: str | None = None

    # Providers
    openai_api_key: str | None = None
    sarvam_api_key: str | None = None

    # LLM generation providers (used by the evaluator-generation workflows and
    # any future GenAI workflow; the abstraction is provider-agnostic).
    llm_provider: Literal["openai", "anthropic", "openrouter"] = "openrouter"
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-haiku-latest"
    anthropic_base_url: str = "https://api.anthropic.com"
    openrouter_api_key: str | None = None
    openrouter_model: str = "google/gemma-4-31b-it"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Decision model (Jev via OpenRouter Decisions API). The plain-HTTP surface
    # is /api/alpha/decisions; /api/v1/systemone is the TypeSafe SDK path.
    jev_model: str = "typesafe/jev-1.13"
    jev_base_url: str = "https://openrouter.ai/api/alpha/decisions"

    # Voice-Agent Judge (docs/V2-changes/judge-implementation.md). The LLM does
    # extraction/adjudication/verification/audio; Jev makes the bounded decisions.
    judging_rubric_version: str = "2026.10-v1.1"
    judge_llm_model: str | None = None  # defaults to the generation model
    adjudicator_model: str | None = None
    verifier_model: str | None = None
    audio_model: str | None = None
    # Bounded-decision thresholds (§4.3/§5.2/§5.5); [P] calibration starting points.
    jev_escalation_lo: float = 0.2
    jev_escalation_hi: float = 0.8
    jev_confidence_tau: float = 0.6
    injection_tau: float = 0.3
    asr_conf_tau: float = 0.8
    packet_token_budget: int = 6_000
    packet_token_cap: int = 20_000
    jev_max_concurrent_requests: int = 16
    # Stage 0 audio parameters (§2.2/§6.1); [P] calibration starting points.
    vad_frame_ms: int = 10
    vad_hangover_ms: int = 300
    alignment_tolerance_ms: int = 120
    bleed_tau: float = 0.25
    t_yield_ms: int = 1_000
    yield_silence_ms: int = 250
    bargein_censor_ms: int = 3_000
    first_agent_audio_sustain_ms: int = 80
    caller_resume_merge_ms: int = 600
    # Silero VAD (ONNX). When unavailable the energy VAD fallback is used.
    silero_vad_enabled: bool = True
    silero_onnx_path: str | None = None

    # Evaluator-generation policy. Metric removal starts from the full metric set
    # and removes only completely-irrelevant metrics, so there is no mandatory or
    # min/max metric knob. The remaining knobs bound scenario/repair fan-out.
    generation_scenarios_per_profile: int = 3
    generation_max_repair_attempts: int = 1

    # Observability
    otel_exporter_otlp_endpoint: str | None = None

    # Runner dispatch: the base URL a dispatched runner uses to reach the
    # control-plane runner WebSocket.
    runner_backend_url: str = "http://localhost:8000"

    # How an attempt is handed to a runner. "subprocess" spawns an isolated
    # runner process (production v1); "inline" runs the runner inside the worker
    # process (local/dev, no separate runner container); "livekit" dispatches a
    # LiveKit Agents job for the attempt (see caller-migration-to-livekit.md §4).
    runner_dispatch_mode: Literal["subprocess", "inline", "livekit"] = "subprocess"

    # LiveKit (self-hosted). The caller runs as a LiveKit Agents job; the control
    # plane creates the room and issues an explicit named-agent dispatch. The
    # job metadata carries only attempt_id + a short-lived runner token; it is
    # never a config channel (§4.1).
    livekit_url: str | None = None
    livekit_api_key: str | None = None
    livekit_api_secret: str | None = None
    livekit_agent_name: str = "voiceeval-caller"
    livekit_room_empty_timeout_s: int = 600
    livekit_room_max_participants: int = 3
    # Rooms we create on a *target's* LiveKit project (§4.2 external room). The
    # provider deletes the room once it has been empty for this long; we do not
    # reap them locally.
    livekit_target_room_empty_timeout_s: int = 900
    livekit_sip_outbound_trunk_id: str | None = None
    livekit_sip_from_number: str | None = None

    # Per-phase lifecycle timeouts (§4.4). Existing ``conversation_stall_ms`` and
    # ``wall_clock_timeout_ms`` map to the last two phases.
    livekit_dispatch_timeout_ms: int = 15_000
    livekit_register_timeout_ms: int = 15_000
    livekit_dial_timeout_ms: int = 30_000
    livekit_ring_timeout_ms: int = 45_000
    livekit_first_audio_timeout_ms: int = 15_000

    # Admission control (§11): the real bottleneck is usually outside LiveKit.
    livekit_max_concurrent_calls: int = 20
    livekit_max_concurrent_per_target: int = 1
    sarvam_max_concurrent_streams: int = 20
    llm_max_concurrent_requests: int = 16
    # Rooms older than this (max attempt duration + grace) are reaped.
    livekit_room_reap_after_s: int = 360

    # Twilio Elastic SIP trunk for outbound phone calls. ``TWILIO_SIP`` is a
    # Twilio API Key SID (``SK…``) and ``TWILIO_CLIENT_SECRET`` its secret; the
    # account SID + trunk domain + SIP credentials + caller number identify the
    # trunk and caller ID. `livekit_sip_outbound_trunk_id` is the LiveKit-side
    # trunk created from these (see scripts/setup_livekit_sip.py).
    twilio_account_sid: str | None = None
    twilio_api_key_sid: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TWILIO_SIP", "TWILIO_API_KEY_SID"),
    )
    twilio_api_key_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TWILIO_CLIENT_SECRET", "TWILIO_API_KEY_SECRET"),
    )
    twilio_sip_trunk_domain: str | None = None
    twilio_sip_username: str | None = None
    twilio_sip_password: str | None = None
    twilio_from_number: str | None = None

    # Exotel SIP trunking (used by scripts/exotel_setup.py to provision a trunk,
    # map a DID and create digest credentials). India -> api.in.exotel.com,
    # Singapore -> api.exotel.com. Trunk setup is a one-off; the resulting SIP
    # account (address/from_number/username/password) is what the runtime dials.
    exotel_account_sid: str | None = None
    exotel_account_region: str = "Singapore"
    exotel_subdomain: str = "api.exotel.com"
    exotel_api_key: str | None = None
    exotel_api_token: str | None = None
    exotel_trunk_name: str = "voiceeval"
    exotel_sip_username: str | None = None
    exotel_sip_password: str | None = None
    exotel_sip_transport: str = "tls"
    exotel_from_number: str | None = None

    # Port the standalone deterministic fake target server binds in local dev
    # (see ``python -m voiceeval.runtime.fake_target``).
    fake_target_port: int = 8790

    # Runtime defaults (referenced by the manifest; kept as configuration, not
    # hidden constants).
    conversation_stall_ms: int = Field(default=10_000)
    wall_clock_timeout_ms: int = Field(default=180_000)
    max_wall_clock_timeout_ms: int = Field(default=300_000)

    # Retry policy: the maximum number of physical attempts a single logical
    # CallRun may spawn for infrastructure failures before it is marked
    # INFRASTRUCTURE_FAILED. Semantic failures are never retried.
    max_attempts_per_run: int = Field(default=3)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
