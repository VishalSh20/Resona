"""Evaluator content validation.

Independent validators check schema, scenario, motive, state, success
conditions, behaviour, language, criteria and capabilities. Their results are
aggregated into a ``ValidationReport``; an evaluator is executable only when no
error-severity check fails.
"""

from voiceeval.services.validation.report import ValidationOutcome, run_validation

__all__ = ["ValidationOutcome", "run_validation"]
