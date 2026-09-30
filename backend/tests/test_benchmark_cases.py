"""Benchmark-case materialization from a version manifest."""

from __future__ import annotations

from voiceeval.services.benchmarks import parse_manifest_cases

_DEFINITION = {
    "scenario": "blocked card",
    "expected_output_prompt": "judge it",
    "metrics": ["task_completion"],
    "languages": {"major": "hi", "minor": "en"},
    "personality": ["IMPATIENT"],
}


def test_parse_manifest_cases_reads_explicit_case_definition():
    cases = parse_manifest_cases(
        {
            "cases": [
                {"case_key": "a", "case_definition": _DEFINITION},
                {"caseDefinition": _DEFINITION, "caseKey": "b", "sequence_no": 5},
            ]
        }
    )
    assert cases == [
        {"case_key": "a", "case_definition": _DEFINITION, "sequence_no": 1},
        {"case_key": "b", "case_definition": _DEFINITION, "sequence_no": 5},
    ]


def test_parse_manifest_cases_accepts_inline_fields():
    cases = parse_manifest_cases(
        {
            "cases": [
                {
                    "scenario": "s",
                    "expectedOutputPrompt": "j",
                    "metrics": ["task_completion"],
                }
            ]
        }
    )
    assert cases == [
        {
            "case_key": "case_1",
            "case_definition": {
                "scenario": "s",
                "expected_output_prompt": "j",
                "metrics": ["task_completion"],
            },
            "sequence_no": 1,
        }
    ]


def test_parse_manifest_cases_skips_entries_without_definition():
    assert parse_manifest_cases({"cases": [{"case_key": "a"}, "not-an-object"]}) == []


def test_parse_manifest_cases_is_safe_on_missing_input():
    assert parse_manifest_cases(None) == []
    assert parse_manifest_cases({}) == []
    assert parse_manifest_cases({"cases": "nope"}) == []
