"""Mint control-plane JWTs from the command line.

There is deliberately no public signup or identity-management UX. Tokens for the
``/api/v1`` surface are issued out of band:

    uv run python -m voiceeval.auth.cli --sub operator@example.com
    uv run python -m voiceeval.auth.cli --scope runner --attempt att_01J...

The token is printed to stdout. The same signing key and issuer as the API are
used (``JWT_SECRET`` / ``JWT_ISSUER``), so anyone able to run this already has
the deployment secret.
"""

from __future__ import annotations

import argparse
import sys

from voiceeval.auth.jwt import create_runner_token, create_token


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mint a VoiceEval JWT.")
    parser.add_argument("--sub", required=True, help="subject (user id or runner id)")
    parser.add_argument(
        "--scope",
        choices=("user", "runner"),
        default="user",
        help="token scope (default: user)",
    )
    parser.add_argument(
        "--attempt",
        default=None,
        help="attempt id to bind (required for --scope runner)",
    )
    parser.add_argument(
        "--expires-in",
        type=int,
        default=None,
        help="token lifetime in seconds (default: configured access-token lifetime)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.scope == "runner":
        if not args.attempt:
            print("error: --attempt is required for --scope runner", file=sys.stderr)
            return 2
        token = create_runner_token(
            args.sub,
            args.attempt,
            expires_in_seconds=args.expires_in or 300,
        )
    else:
        token, _ = create_token(
            args.sub, "user", expires_in_seconds=args.expires_in
        )
    print(token)
    return 0


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    raise SystemExit(main())
