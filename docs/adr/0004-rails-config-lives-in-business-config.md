# Rail behavior is configured inside the Business Config, not a separate file

Every Business needs different Input/Output Rail boundaries (KampusCrave's
off-topic line isn't the hotel's) and different Tool Rail confirmation
rules (which Tools are write-scoped varies per Business's Tool set) — this
can't be one global NeMo config shared across Businesses. The alternative
was a second per-Business file (`rails.yaml`, mirroring how `context/` is
a directory, not inline content) referenced from `business.yaml`. We're
adding `rails` as a new top-level key in `business.yaml` instead, alongside
`llm`, `business_logic`, `tools`, etc. — rails config is structured
parameters (thresholds, scope boundaries, which Tools require
Confirmation), the same shape as those existing keys, not prose content
like `context/`'s files. This keeps "one file describes one Business"
intact rather than splintering Business identity across files as soon as
guardrails entered the picture.
