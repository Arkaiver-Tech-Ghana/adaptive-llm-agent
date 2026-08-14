"""The Rail axis — NeMo Guardrails' four checkpoints wrapping the Agent Core.

See CLAUDE.md's "Rails" section and CONTEXT.md's glossary for what each of
Input/Data/Tool/Output Rail is responsible for. This package only ships the
Input/Output Rail boundary (``RailChecker``, backed by NeMo) — the Tool Rail
and Data Rail are pure in-process decision functions with no external
dependency to swap, so they don't need a Protocol here (see
``feature/tool-rail-and-session``).
"""
