# Adaptive Business Chat Agent

One agent core wrapped by NeMo Guardrails, serving two unrelated fictional
businesses (KampusCrave food ordering, hotel booking/enquiries) off the same
codebase by swapping only a config. Built to prove production-grade agent
architecture to a technical reviewer in a 3-day sprint — see
`prd-adaptive-agent.md` for the full spec: goals, acceptance criteria, P0/P1/P2
requirements, timeline, and success metrics. Read it before planning any
feature-sized change.

Domain vocabulary (Business, Agent Core, Rail, Session, etc.) is defined in
`CONTEXT.md` — use those terms, not ad hoc synonyms. Architectural decisions
that are hard to reverse live in `docs/adr/`; check there before revisiting
RLS, session isolation, or the storage-keying scheme.

## The invariant

Every axis around the core — frontend adapter, LLM, tools, storage, business
logic, auth, context files — sits behind its own interface. **Onboarding a new
business must never touch core agent code**, only add/select modules. Before
writing anything that special-cases a business inside the core, stop: that
logic belongs in a config module, not in the core.

Only two axes need a second live implementation to prove the swap: tools and
business logic/context. Storage and the frontend (WhatsApp) each get exactly
one real implementation for v1 — their modularity is proven by the interface
contract alone, not by standing up a second backend. Don't build a second
storage or frontend implementation; it's explicitly out of scope.

## Rails

NeMo wraps the agent at four checkpoints, nothing reaches or leaves unchecked:
**input** rail (injection/off-topic, before the agent sees the message),
**data rail** (retrieval/data-access governance), **tool rail** (execution —
gates any write/irreversible tool call behind explicit user confirmation),
**output rail** (response validation before it reaches the user). "Data rail"
and "tool rail" are this project's names for the retrieval and execution
rails — use them, not the generic NeMo terms, when discussing this codebase.

Only these four rail types ship. Deeper rail types (dialog, retrieval-rail
tuning) are P2 — design the interface to allow them later, don't build them
now.

## Non-goals (don't build these)

- Additional frontends beyond WhatsApp (Discord, Slack, web) — interface
  layer must support them later, none get built now.
- Real third-party integrations (live payments, live bookings) — tools hit
  mock/sandbox endpoints only. Integration risk isn't what's being
  demonstrated.
- A second storage backend or frontend just to "prove" modularity — the
  interface contract is the proof.

## Resolved decisions (don't re-litigate)

- The two businesses are fixed: **KampusCrave** (food ordering) and a
  **hotel** (booking/enquiries).
- The demo injection attempt is genuinely adversarial, not scripted.
- Confirmation UX accepts both WhatsApp quick-reply buttons and plain-text
  yes/no — the rail checks input against the expected shape, it doesn't try
  to distinguish the two.
- Latency budget isn't fixed; rail-check overhead is expected to be small
  relative to core LLM call latency — don't over-optimize rail plumbing at
  the expense of shipping.

## Process bar

This repo is a public professionalism showcase, not a throwaway demo:
proper branches + PRs, GitHub Actions for CI/deploy validation, real tests,
public repo and articles/video. Treat scrappy shortcuts (direct pushes to
main, skipped tests, no CI) as defects even under the 3-day deadline — the
process is part of what's being demonstrated, not overhead around it.

## Data model notes

- RLS by default: a Customer's data is invisible to other Customers except
  via explicitly-aggregate queries. See `docs/adr/0001-*`.
- Session is scoped to `frontend-type + Customer identity` — a WhatsApp
  Session's context must never bleed into a web Session's, even for the
  same Customer. See `docs/adr/0002-*`.
- Storage is keyed by `database-id + schema identity`, anticipating one
  schema (or database) per Business as the Business count grows. See
  `docs/adr/0003-*`.
