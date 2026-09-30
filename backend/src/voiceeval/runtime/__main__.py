"""Allow ``python -m voiceeval.runtime`` to launch the runner process."""

from voiceeval.runtime.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
