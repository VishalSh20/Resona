"""Backend realtime control plane.

Two distinct WebSocket channels, both deliberately outside the audio path:
  * the runner control/telemetry channel (``/internal/v1``), and
  * the live plan observation channel (``/api/v1``).

Raw runtime events are ingested append-only; derived objects (turns, tool calls,
state transitions) are materialized and therefore rebuildable.
"""
