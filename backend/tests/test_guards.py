"""Immutability guard tests."""

from __future__ import annotations

import pytest

from voiceeval.core.errors import ImmutableResourceError
from voiceeval.db.guards import (
    ensure_benchmark_version_mutable,
    ensure_manifest_immutable,
    ensure_media_artifact_mutable,
    ensure_runtime_event_append_only,
)
from voiceeval.db.models import domain, runtime


def test_frozen_benchmark_version_is_immutable():
    version = domain.BenchmarkVersion(status="frozen")
    with pytest.raises(ImmutableResourceError):
        ensure_benchmark_version_mutable(version)


def test_draft_benchmark_version_is_mutable():
    version = domain.BenchmarkVersion(status="draft")
    ensure_benchmark_version_mutable(version)  # should not raise


def test_manifest_is_always_immutable():
    with pytest.raises(ImmutableResourceError):
        ensure_manifest_immutable()


def test_runtime_event_append_only():
    with pytest.raises(ImmutableResourceError):
        ensure_runtime_event_append_only()


def test_original_media_with_hash_is_immutable():
    artifact = runtime.MediaArtifact(representation="original", sha256="abc")
    with pytest.raises(ImmutableResourceError):
        ensure_media_artifact_mutable(artifact)


def test_analysis_media_is_mutable():
    artifact = runtime.MediaArtifact(representation="analysis")
    ensure_media_artifact_mutable(artifact)  # should not raise
