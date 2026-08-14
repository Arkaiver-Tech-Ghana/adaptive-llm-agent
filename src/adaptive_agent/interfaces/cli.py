"""Day 1 CLI test harness.

This is NOT the P0 Interface Layer (rate limiting, auth, idempotency ship
Day 3) and it does NOT implement the future Session Store (docs/adr/0002) —
it keeps a plain in-memory history list for the life of the process. Its
only job is to exercise load_agent_core() end to end, satisfying the PRD's
"tested via CLI/web stub" requirement.
"""

import argparse
import sys
from pathlib import Path

from adaptive_agent.agent_core import BusinessDisabledError, load_agent_core
from adaptive_agent.business_config.loader import BusinessConfigError


def main() -> None:
    parser = argparse.ArgumentParser(description="Adaptive Agent CLI test harness")
    parser.add_argument(
        "--business",
        required=True,
        type=Path,
        help="Path to a Business Config YAML file",
    )
    args = parser.parse_args()

    try:
        agent = load_agent_core(args.business)
    except (BusinessConfigError, BusinessDisabledError) as exc:
        print(f"Failed to load business: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"Loaded {agent.business_config.display_name}. Type a message ('quit' to exit).")

    history: list[dict[str, str]] = []
    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit"}:
            break

        reply = agent.respond(user_input, history=history)
        print(reply)

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()
