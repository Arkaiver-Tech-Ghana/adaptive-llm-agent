"""Day 1 CLI test harness.

This is NOT the P0 Interface Layer (rate limiting, auth, idempotency ship
Day 3). Its per-message flow — Input/Data/Tool/Output Rails, pending
Confirmation Requests, Session history — is delegated entirely to
``ConversationRuntime`` (see ``conversation.py``); this module's only job
is to exercise it end to end, satisfying the PRD's "tested via CLI/web
stub" requirement.
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from adaptive_agent.agent_core import BusinessDisabledError
from adaptive_agent.business_config.loader import BusinessConfigError
from adaptive_agent.conversation import load_conversation_runtime

# The CLI is single-user, so one fixed Session key for the process's whole
# life satisfies ADR 0002's "frontend-type + Customer identity" keying —
# it just needs *a* stable key, not per-Customer differentiation.
SESSION_KEY = "cli:local"


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Adaptive Agent CLI test harness")
    parser.add_argument(
        "--business",
        required=True,
        type=Path,
        help="Path to a Business Config YAML file",
    )
    args = parser.parse_args()

    try:
        runtime = load_conversation_runtime(args.business)
    except (BusinessConfigError, BusinessDisabledError) as exc:
        print(f"Failed to load business: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    display_name = runtime.agent_core.business_config.display_name
    print(f"Loaded {display_name}. Type a message ('quit' to exit).")

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

        reply = runtime.handle_message(SESSION_KEY, user_input)
        print(reply)


if __name__ == "__main__":
    main()
