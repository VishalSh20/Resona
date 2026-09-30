"""Word error rate.

A small, dependency-free WER implementation shared by ``agent_input_wer`` and
``independent_asr_wer``. The two metrics stay separate because their *provenance*
differs: agent input WER compares the caller reference against the target's own
exposed input transcript, while independent ASR WER compares against a transcript
produced by our own ASR. The computation is identical; the provenance is not.
"""

from __future__ import annotations

import re
import unicodedata

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def normalize_tokens(text: str, *, lowercase: bool = True) -> list[str]:
    """Tokenize text into comparable word tokens."""
    if not text:
        return []
    normalized = unicodedata.normalize("NFKC", text)
    if lowercase:
        normalized = normalized.lower()
    return _TOKEN_RE.findall(normalized)


def _levenshtein(reference: list[str], hypothesis: list[str]) -> int:
    if not reference:
        return len(hypothesis)
    if not hypothesis:
        return len(reference)
    previous = list(range(len(hypothesis) + 1))
    for i, ref_token in enumerate(reference, start=1):
        current = [i]
        for j, hyp_token in enumerate(hypothesis, start=1):
            cost = 0 if ref_token == hyp_token else 1
            current.append(
                min(
                    previous[j] + 1,  # deletion
                    current[j - 1] + 1,  # insertion
                    previous[j - 1] + cost,  # substitution
                )
            )
        previous = current
    return previous[-1]


def word_error_rate(
    reference: str, hypothesis: str, *, lowercase: bool = True
) -> float:
    """Return the word error rate of ``hypothesis`` against ``reference``.

    An empty reference with an empty hypothesis is a perfect match (0.0); an
    empty reference with a non-empty hypothesis is a total error (1.0).
    """
    ref_tokens = normalize_tokens(reference, lowercase=lowercase)
    hyp_tokens = normalize_tokens(hypothesis, lowercase=lowercase)
    if not ref_tokens:
        return 0.0 if not hyp_tokens else 1.0
    return _levenshtein(ref_tokens, hyp_tokens) / len(ref_tokens)


def corpus_wer(
    references: list[str], hypotheses: list[str], *, lowercase: bool = True
) -> float:
    """Word error rate over a concatenated corpus of utterances."""
    reference = " ".join(r for r in references if r)
    hypothesis = " ".join(h for h in hypotheses if h)
    return word_error_rate(reference, hypothesis, lowercase=lowercase)


__all__ = ["corpus_wer", "normalize_tokens", "word_error_rate"]
