"""Aggregate validator results into a ValidationReport outcome."""

from __future__ import annotations

from dataclasses import dataclass, field

from voiceeval.services.validation.validators import Check, run_validators

VALIDATOR_VERSION = "1.0.0"


@dataclass
class ValidationOutcome:
    checks: list[Check] = field(default_factory=list)
    blocking_error_count: int = 0
    warning_count: int = 0
    validator_version: str = VALIDATOR_VERSION

    @property
    def passed(self) -> bool:
        return self.blocking_error_count == 0

    @property
    def status(self) -> str:
        return "passed" if self.passed else "failed"

    def as_report(self) -> dict:
        return {
            "validator_version": self.validator_version,
            "status": self.status,
            "blocking_error_count": self.blocking_error_count,
            "warning_count": self.warning_count,
            "checks": [check.as_dict() for check in self.checks],
        }


def run_validation(content: dict) -> ValidationOutcome:
    checks = run_validators(content)
    blocking = sum(
        1 for check in checks if check.severity == "error" and not check.passed
    )
    warnings = sum(1 for check in checks if not check.passed and check.severity == "warning")
    return ValidationOutcome(
        checks=checks,
        blocking_error_count=blocking,
        warning_count=warnings,
    )
