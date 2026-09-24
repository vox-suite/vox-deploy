# Vox conceptual model

Status: Historical scheduling-focused model. Its identity, connection, grant, approval, and execution boundaries inform the current direction, but its scheduling-only launch scope has been superseded. See current-product-direction.md. No implementation technologies or contracts have been selected.

Scope under reconsideration: the user requires a global, modular everyday-assistant product, not an India-first or scheduling-only product. Requested service coverage includes Expedia, Zomato, Amazon, Uber, and everyday capabilities such as reminders; these are examples, not a closed integration list. User-added extensions are desired. The scheduling-only MVP below is the previous baseline, not the current launch scope. Actual execution coverage, unavailable-capability behavior, reminder behavior, and extension authority remain to be settled. Global product scope does not establish that every external service or action is available in every region.

## Product promise

An individual selects an email thread and asks an assistant to prepare a meeting. The assistant reads that context, checks the selected calendar, resolves ambiguity with the user, and proposes an invitation. The platform creates the invitation only after approval of its exact details and checks of current authority and relevant conditions. The calendar invitation is the notification; no duplicate email is sent.

This proves reusable integrations and user connections, not multi-agent collaboration. One configured assistant is sufficient initially.

## Concepts and boundaries

| Concept | What it is and why it exists | Ownership or control | Responsible for | Not responsible for |
| --- | --- | --- | --- | --- |
| Agent | Configured assistant with a purpose; interprets the request and plans work | Platform provides the initial assistant; user controls its access grants | Cross-service planning, choosing enabled tools, clarification, explaining results | Holding credentials, granting itself authority, authoritative execution records |
| Integration | Reusable capabilities for an external service; separates service behavior from agents and accounts | Platform supplies MVP integrations | Service-specific rules and capability descriptions | Owning user accounts, cross-service planning, overriding platform policy |
| Tool / action | A tool is an available capability; an action is a specific requested use of it | Platform supplies tools through integrations; the user authorizes consequential uses | A bounded service operation with described inputs, result, effects, and failure outcomes | Owning a task or an agent; interpreting account access as blanket approval |
| Connection | User-owned link to a particular service account; separates account identity from capability definitions | User | Identifying the account and its access lifecycle | Owning integrations or being tied exclusively to one agent |
| Credential | Protected evidence of service access; makes authenticated use possible | Platform protects it on the user's behalf; external service governs validity | Establishing access to the selected account | Being agent context or approval for a particular change |
| Service authorization | Permissions allowed by the external service | User grants access subject to service rules | Bounding what the connection can do at the service | Replacing narrower product limits or action approval |
| Agent access grant | Allowance to use selected capabilities through a connection | User controls; platform enforces | Limiting the agent's usable connections and tools | Expanding service authorization or approving all future writes |
| Task | User-requested outcome; groups work around intent | User requests; platform tracks | Defining the desired outcome and unresolved choices | Being a single tool invocation or standing authority |
| Run | An attempt to carry out a task, including pauses | Platform tracks | Execution status, attempted actions, confirmed results, unresolved outcomes | Treating an agent's narrative as proof of external success |
| User approval | Permission for one exact proposed external change | User gives; platform enforces | Binding permission to disclosed account and material action details | Approving changed details, a second event, or unknown future actions |
| Agent-to-agent interaction | Delegation or collaboration between distinct assistants | Deferred beyond MVP | No MVP responsibility | Being required merely because the eventual product supports many agents |
| Orchestration | Coordination of task progress and execution safeguards, not necessarily a separate component or agent | Platform owns execution coordination; agent owns planning | Pauses, authority checks, status, cancellation, and controlled execution | Becoming a second planning agent or dictating deployment architecture |

## Interaction model

1. The user connects accounts, understands service permissions, enables capabilities for the assistant, and selects defaults or task overrides.
2. The user selects a thread through a recent-thread picker and starts a task. Only selected content enters assistant context.
3. The assistant plans using enabled capabilities and their current availability. The platform checks authority before each execution; external content cannot create authority.
4. Reads proceed within granted access. Unresolved recipients, timing, or account selection cause clarification rather than guessing.
5. The assistant proposes exact invitation details. The user approves; the platform rechecks authority and relevant conditions before executing.
6. The platform records the confirmed result or unresolved outcome. The assistant explains the status in the conversation.

The integration is a reusable capability boundary, not necessarily an extra runtime hop. The connection supplies account identity and authorized access; it is not embedded in the agent or tool definition.

## Minimal integration abstraction

A service exposes a set of usable capabilities, independently of connected accounts. Each capability describes purpose, required inputs, expected result, required access, external effects, and possible failures or uncertain outcomes. A connection supplies an account and its current access state. Agent grants and platform policy determine whether a capability may be used and whether approval is required.

This is protocol-neutral. MCP, APIs, SDKs, and other mechanisms are implementation candidates rather than the product abstraction. Arbitrary endpoint installation, custom integrations, and dynamic installation are deferred. Capability versioning and compatibility rules remain pre-implementation work, not an assumed schema.

## Failure and trust rules

- Expired access pauses affected work. Reconnection never silently broadens permissions or switches accounts; relevant facts and authority are rechecked.
- Materially changed conditions invalidate the basis for proceeding. Ask for a revised decision instead of proceeding on stale approval.
- A timeout is not proof of failure. Check for the event before retrying; if its existence cannot be established, pause with an unknown outcome.
- Cancellation stops future work where possible, not necessarily an in-flight action. Completed changes are not automatically undone. Undo is a separate approved action outside current MVP capabilities.
- Credentials never enter agent context. Email content is untrusted task data, not a source of instructions that can expand authority.
- Selected-thread context is a product restriction, not a promise of thread-only permissions at the external service.

## Minimal experience and retained data

Use one conversation, a compact task-status view, a thread picker, and an exact approval preview. Show selected accounts, attempted actions, confirmed outcomes, and unresolved status. Do not add an operations dashboard or expose private model reasoning.

Selected content remains only as needed for active or paused work and is removed from task context on completion or cancellation. Keep a minimal action record rather than full email bodies; users may delete task history. Exact retention periods, historical context removal, and provider-side storage requirements must be settled before launch. No claim is made that external service records are deleted when local task history is deleted.

## MVP proof and deliberate exclusions

Demonstrate a correct approved invitation from a selected thread; reuse the same integrations with different connections without changing the agent; block disabled capabilities and unapproved writes independently of agent behavior; handle expiry, changed availability, uncertain outcomes, and cancellation honestly without duplicate invitations.

Exclude multi-agent collaboration, autonomous negotiation, background triggers, schedules, inbox-wide agent search, email sending, event deletion, purchases, payments, shared account ownership, custom integrations, and unnecessary management dashboards.

The tradeoff is deliberate: narrower workflows and explicit approval introduce friction but make authority and outcomes understandable. A wider marketplace, background autonomy, or several agents could add flexibility, but none is needed to prove this MVP's product requirements.

## Deferred decisions, not hidden assumptions

Specific email/calendar services, feasible service permissions, credential handling details, retention periods, capability compatibility, integration mechanisms, languages, frameworks, models, persistence, infrastructure, and deployment remain undecided. They require a later feasibility and implementation-design phase after confirmation of this conceptual model.
