# Adaptive Business Chat Agent

Domain model for a single agent core that serves multiple unrelated
fictional businesses (WhatsApp food ordering, hotel booking) off one
codebase, with all per-business behavior selected through config.

## Language

### Tenancy & configuration

**Business**:
A tenant of the platform — a fictional company (KampusCrave, the hotel)
with its own tools, data, and behavior, defined entirely by its Business
Config.
_Avoid_: Client, tenant, account.

**Business Config**:
The selections that define one Business's instance — frontend adapter,
LLM, tools, storage/schema, business logic, auth type, context files,
on/off switch. Onboarding a Business means adding a Business Config,
never touching Agent Core code.
_Avoid_: Client config, tenant config.

**Agent Core**:
The LLM plus a loaded Business Config — handles both informative (RAG)
and action-taking (tool-calling) requests. Identical code for every
Business; behavior differs only by which Business Config is loaded.
_Avoid_: Bot, assistant, agent (bare).

**Business Admin UI**:
A future (P2, not built for v1) interface for a business owner to edit
their own Business Config without a developer. For v1 the Business
Config is a hand-edited file.
_Avoid_: Client-facing frontend, config UI.

### Guardrails

**Rail**:
One of NeMo Guardrails' four checkpoints wrapping the Agent Core —
nothing reaches or leaves the Agent Core unchecked.

**Input Rail**:
Checks an incoming message for injection/off-topic content before the
Agent Core sees it.

**Data Rail**:
Governs what data the Agent Core may retrieve during a request. This
project's name for NeMo's retrieval rail.
_Avoid_: Retrieval rail.

**Tool Rail**:
Governs which Tools the Agent Core may call and gates any write/
irreversible Tool call behind a Confirmation. This project's name for
NeMo's execution rail.
_Avoid_: Execution rail.

**Output Rail**:
Validates the Agent Core's response before it reaches the Customer.

**Confirmation**:
An explicit yes/no from the Customer, required by the Tool Rail before a
write-scoped Tool executes. Accepted as a WhatsApp quick-reply button or
plain-text yes/no — the Tool Rail checks the reply against the expected
shape, it doesn't distinguish which form was used.

### Frontend & sessions

**Frontend Adapter**:
An implementation of the Interface Layer's request/response contract for
one channel (WhatsApp for v1). Adding a channel means adding an adapter,
not touching the Agent Core.
_Avoid_: Channel, integration.

**Interface Layer**:
The single request-processing layer between a Frontend Adapter and the
Agent Core: enforces the request/response contract, per-Customer rate
limiting, auth validation, and dedupe of retried inbound messages.
_Avoid_: Middleware.

**Customer**:
The end user chatting with a Business through a Frontend Adapter.
_Avoid_: User, end user, client.

**Session**:
Conversation history and pending Confirmations for one Customer on one
Business, scoped to a single Frontend Adapter. A Customer's WhatsApp
Session and web Session for the same Business never share context.

### Actions

**Tool**:
An MCP-compatible callable action available to the Agent Core (e.g.
reserve a table). Read Tools need no Confirmation; write/irreversible
Tools require one via the Tool Rail.
_Avoid_: Function, action.
