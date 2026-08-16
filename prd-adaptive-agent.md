# PRD — Adaptive Business Chat Agent (WhatsApp, v1)

> **2026-08-16 addendum**: this PRD is a historical snapshot of the
> original 3-day-sprint scope, left as-is rather than edited in place.
> The P2 "Business Admin UI" bullet below has since shipped (self-serve
> signup, generic owner-defined tables, no staff/RBAC) — see ADR 0007,
> ADR 0008, and CONTEXT.md's `Business Admin UI`/`Custom Table` glossary
> entries for the current state.

## Problem Statement
Making production-grade agent architecture (guardrails, multi-tenant config, action-safety) legible to a reviewer in a few minutes of video and repo skimming. Without this, the project reads as "followed a tutorial" instead of "understands the system."

## Goals
1. One agent core, wrapped by NeMo on all sides, handles both informative (RAG) and action-taking (tool-calling + confirmation) requests — every surrounding piece (frontend, tools, storage, business logic, context) is a swappable module behind its own interface, not hardcoded.
2. The same core serves two distinct fictional businesses by swapping only a config file — proven live on camera, not just claimed. This allows easy versioning for the user, from v1 to v2 when they want to change what their agent can do, without needing a developer.
3. The guardrail stack visibly catches at least one adversarial input (prompt injection) on screen.
4. Full build — architecture, two configs, working demo, recorded video — ships inside the 3-day sprint.
5. A technical reviewer can map spoken concepts (rails, config swap, confirmation gate) to specific code within 5 minutes of skimming the repo.

## Non-Goals

- **Additional frontends** (Discord, Slack ) — future work. The interface layer is designed to support them, but none are built now.
- **Full NeMo rail depth** (all 5 rail types, retrieval-rail tuning) — only input, output, and execution (tool-call) rails ship, since those correlate most with real incidents.
- **Real third-party integrations** (live payments, live bookings) — tools hit mock/sandbox endpoints. Integration risk isn't what's being demonstrated.
- **Multiple live storage or frontend implementations** — each gets one clean interface and one real implementation for v1. Modularity is proven by the interface contract and by the axes that do get swapped (tools, business logic, context), not by standing up a second database or a second channel just to make the point.

## User Stories

**Technical reviewer (the real audience)**
- As a reviewer watching the demo, I want to see the same core answer for two different businesses with no code change, so I can verify "generic" instead of taking it on faith.
- As a reviewer, I want to see a prompt-injection attempt get caught on camera, so I trust the guardrail claims.
- As a reviewer, I want to see an action-taking request pause for confirmation before executing, so I know agent safety was considered, not assumed.
- As a reviewer skimming the repo, I want the business-config schema clearly documented, so I can judge design quality without running the code.

**Simulated end user (WhatsApp)**
- As a customer messaging Business A, I want answers grounded in that business's own data, so I don't get generic or wrong answers.
- As a customer, I want to complete an action (e.g. reserve a table) inside the chat, so I don't leave WhatsApp.
- As a customer, I want a confirmation step before anything irreversible happens, so I don't trigger an action by accident.


#### Choices

1. Database: RLS, users probably shouldn't see other people's data, except for maybe general functions that fetch specific aggregate data
2. Lock chat to frontend-type + user identity system by default , so context from whatsapp doesn't bleed into web context. might change when I expand.
3. Database: the more clients, the more schemas i'll have to build, meaning i might have to create multiple databases, meaning I should have a database-id + schema identity system


#### Components 
- Storage ( user-and-device-data---accessed by middleware, client agent specific user data schema, client config)
- LLM router 
- NeMo Guardrails layer
- Cost evaluation per client (model choice , traffic etc)
- middleware (for whatsapp and web, rate limiting per user-id,session cache management,...)
- business config management
- Agent = LLM + business config
- client facing frontend
- user facing frontends ( whatsapp , web)
- agent tools management system
- two live business configs


- Documenting parts (video, written , post)

## Requirements

### P0 — Must-have
- **Interface layer / middleware**: rate limiting per user, basic account/auth validation, a request/response contract any frontend adapter can implement, and idempotency/dedupe on inbound messages so a retried webhook delivery can't double-execute a tool call.
  - *AC*: Given >N messages/min from one user, When the threshold is exceeded, Then further messages are rate-limited with a clear response.
  - *AC*: Given the same inbound message delivered twice (e.g. a WhatsApp webhook retry) with the same message id, When the second delivery arrives, Then it is recognized as a duplicate and dropped/short-circuited before reaching the agent — no tool call, including a write/irreversible one, executes twice for one logical message.
- **NeMo wraps the agent entirely** — input rail (injection/off-topic detection before the agent sees the message), retrieval rail (governs data access — Ramsey's "data rails"), execution rail (governs tool calls, gates any write/irreversible tool behind explicit confirmation — Ramsey's "tool rails"), and output rail (response validation before it reaches the user). One wrapper, four checkpoints, nothing reaches or leaves the agent unchecked.
  - *AC*: Given a known injection-pattern message, When it passes through NeMo, Then it is rejected or rewritten before reaching the agent.
  - *AC*: Given the agent selects a write-scoped tool, When it's about to call it, Then the user must confirm first; declining halts the action.
  - *AC*: Given an out-of-scope agent response, When the output rail runs, Then it is blocked or reformatted.
- **Modular config layer**: the client selects, per instance, which frontend adapter, which LLM, which tools, which data storage/structure, which business logic, auth type, turn agent on/off, and which context files to load — each axis sits behind a defined interface, Lego-style. Tools are MCP-compatible.
  - *AC*: A new business onboards by selecting/adding modules, with zero core agent code changes.
  - *Scope note*: every axis gets a clean interface for v1. Only tools, business logic, and context files are actually swapped between two working implementations to prove it. Storage and frontend get one real implementation each — modularity there is proven by the interface, not by a second working backend.
- **Two working configs** (fictional businesses) proving the swap.
- **WhatsApp adapter** via Cloud API test number.
  - *AC*: Given a WhatsApp message to the test number, When received, Then it flows interface → NeMo → agent → tools → back out within target latency (define a number, e.g. <8s).
- **Session/state store**: conversation history + pending confirmations, persisted per user per business.
- **Recorded demo video** covering: informative flow, action flow with confirmation, one caught injection attempt, live config swap.

### P1 — Nice-to-have
- Structured logging/tracing so the video can show a trace, not just narrate one.
- The middleware, literally one, but virtually multiple per user.
- On-screen latency numbers — proves awareness of the production cost tradeoff, not just theory.
- A second, distinct tool type demoed (lookup + booking), to show tool diversity beyond one action.

### P2 — Future considerations (design for, don't build)
- Additional frontend adapters (Discord, Slack, website).
- Deeper NeMo rails (retrieval, dialog).
- Official Meta Business API + template approval for real deployment.
- Business Admin UI — lets a business owner edit their own Business Config
  without a developer or hand-edited file. For v1, config is a file edited
  by hand.

## Success Metrics

**Leading**
- Demo video completed and published within the 3-day window.
- All 4 must-show moments present in the video (checklist, target 4/4).
- A reviewer can map concepts to code within 5 minutes (self- or peer-tested).

**Lagging**
- Project gets referenced positively in at least one application or interview.
- Any measurable bump in portfolio-site traffic or recruiter contact tied to the post.

## Open Questions
- Which two fictional businesses to model? — KampusCrave food purchasing, hotel booking and enquiries 
- Scripted or genuinely adversarial injection example for the demo? — yes, adversarial
- Confirmation UX on WhatsApp: quick-reply buttons vs. plain-text yes/no? — both, system can't tell the difference, just has expected input and a check to see if it looks like the expected.
- Target latency budget for the demo? — *Ramsey, informed by build; rail-check overhead is small, most latency comes from the core LLM calls*

## Timeline
Hard constraint: 3-day sprint, rest day after — your usual pattern.

- **Day 1**: Business config schema + agent core, tested via CLI/web stub (no WhatsApp yet). Validates the "generic core" claim structurally before the channel is even in play.
- **Day 2**: NeMo input/output rails + tool-call confirmation gate + second business config (the swap proof).
- **Day 3**: WhatsApp adapter (Cloud API test number) + interface layer (rate limit/auth) + record the video.


Note: This project is to demonstrate my  professionalism  , so I shall use github project and actions for validation and deployment , write proper tests, make proper branches, produce professional grade articles and videos, and publish everything publicly.