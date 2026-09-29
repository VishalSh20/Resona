"""Immutability guards.

The design contract forbids mutation of frozen benchmark versions, execution
manifests, raw runtime events and original media artifacts. These guards raise
:class:`ImmutableResourceError` before any such mutation reaches the database;
they are the application-level backstop to the database-level constraints
applied where practical.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from voiceeval.core.errors import ImmutableResourceError

if TYPE_CHECKING:
    from voiceeval.db.models import domain, runtime


def ensure_benchmark_version_mutable(version: "domain.BenchmarkVersion") -> None:
    """Reject mutation of frozen (or retired) benchmark versions."""
    if version.status in {"frozen", "retired"}:
        raise ImmutableResourceError(
            f"benchmark version '{version.id}' is {version.status} and immutable"
        )


def ensure_manifest_immutable() -> None:
    """Execution manifests are immutable by construction."""
    raise ImmutableResourceError("execution manifests are immutable")


def ensure_runtime_event_append_only() -> None:
    """Raw runtime events are append-only; never updated or deleted."""
    raise ImmutableResourceError("runtime events are append-only")


def ensure_media_artifact_mutable(artifact: "runtime.MediaArtifact") -> None:
    """Original artifacts' hash/object pointer cannot change once set.

    Analysis/clip representations may be derived, but the original recording is
    immutable evidence.
    """
    if artifact.representation == "original" and (
        artifact.sha256 is not None or artifact.object_uri is not None
    ):
        raise ImmutableResourceError(
            f"original media artifact '{artifact.id}' is immutable"
        )
