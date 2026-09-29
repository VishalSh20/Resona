"""Domain repositories (SQLAlchemy 2 async).

Each repository owns a coherent slice of the domain and exposes operations
rather than generic CRUD. Importing this package re-exports the concrete
repository classes for use by services and route handlers.
"""

from voiceeval.db.repositories.attempts import CallAttemptRepository
from voiceeval.db.repositories.benchmarks import BenchmarkRepository
from voiceeval.db.repositories.events import RuntimeEventRepository
from voiceeval.db.repositories.integrations import IntegrationRepository
from voiceeval.db.repositories.judges import JudgeRepository
from voiceeval.db.repositories.judging import (
    JudgeFindingRepository,
    JudgeLedgerRepository,
    MetricProbeRepository,
)
from voiceeval.db.repositories.manifests import ManifestRepository
from voiceeval.db.repositories.materialization import MaterializationRepository
from voiceeval.db.repositories.media import MediaArtifactRepository
from voiceeval.db.repositories.metrics import MetricRepository
from voiceeval.db.repositories.results import ResultRepository
from voiceeval.db.repositories.runs import CallRunRepository
from voiceeval.db.repositories.targets import TargetRepository
from voiceeval.db.repositories.users import UserRepository
from voiceeval.db.repositories.simulations import SimulationRepository
from voiceeval.db.repositories.run_instances import RunRepository
from voiceeval.db.repositories.run_evaluators import RunEvaluatorRepository

__all__ = [
    "CallAttemptRepository",
    "CallRunRepository",
    "BenchmarkRepository",
    "IntegrationRepository",
    "JudgeFindingRepository",
    "JudgeLedgerRepository",
    "JudgeRepository",
    "ManifestRepository",
    "MaterializationRepository",
    "MediaArtifactRepository",
    "MetricProbeRepository",
    "MetricRepository",
    "ResultRepository",
    "RuntimeEventRepository",
    "RunEvaluatorRepository",
    "RunRepository",
    "SimulationRepository",
    "TargetRepository",
    "UserRepository",
]
