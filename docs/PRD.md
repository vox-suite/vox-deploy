# Vox Platform Product Requirements Document

**Status:** Product requirements baseline
**Version:** 1.0
**Date:** 2026-09-19
**Source of truth:** This PRD operationalizes the accepted product model in `docs/current-product-direction.md` and the vocabulary in `CONTEXT.md`. If this document conflicts with an accepted ADR, the ADR and current product direction take precedence until the conflict is explicitly resolved.

## 1. Executive summary

Vox is a global, modular, self-hostable platform for building and operating everyday AI assistants that safely use reusable external-service integrations. Vox's own user-facing application is one host app; independent applications must be able to use the same platform capabilities through the same public boundary.

The platform separates six concerns that must not collapse into one another:

1. A user identity identifies a person within a deployment and host-app context.
2. An agent interprets intent and plans work.
3. An integration declares reusable service capabilities.
4. A connection links a user to a particular external account.
5. A grant permits a selected agent to use selected capabilities through a connection.
6. An approval authorizes one exact consequential action or disclosed group of actions.

The first release proves these boundaries end to end. It does not attempt to claim universal direct execution across Amazon, Expedia, Zomato, Uber, or every regional service. Direct execution is enabled only where production access and operational behavior are verified. Otherwise, Vox provides an honest handoff without claiming completion.

## 2. Problem statement

Users currently interact with separate applications for communication, calendars, shopping, food, travel, rides, reminders, and personal organization. An assistant can reduce this fragmentation, but a useful assistant must be able to act across services without receiving blanket access, exposing credentials, confusing recommendations with completed transactions, or coupling every service to a particular agent or interface.

Application developers also need an assistant platform they can embed without adopting Vox's user interface, login provider, model provider, or hosted infrastructure. Existing agent implementations often couple prompts, tool definitions, credentials, execution, and UI into one application. That makes integrations difficult to reuse and makes consequential actions unsafe to generalize.

Vox solves both problems by providing a stable platform boundary for identity, capabilities, connections, grants, approvals, durable task execution, outcome tracking, reminders, auditing, and extension conformance.

## 3. Product vision

Any authorized host app can give its users access to configurable assistants that discover and use independently addable capabilities. Users remain in control of which accounts and capabilities each agent may use and approve consequential actions with exact material details. The same runnable platform can be self-hosted and extended without depending on proprietary Vox services.

## 4. Product principles

### 4.1 Stable core, replaceable edges

The core owns identity boundaries, connections, grants, approvals, tasks, runs, action state, policy enforcement, audit evidence, and conformance behavior. Agents, models, identity providers, service integrations, notification channels, observability sinks, and host applications are replaceable.

### 4.2 Installation is not authority

Installing an agent or integration grants no account access. Declared requirements are untrusted requests. Users and deployment policy determine actual authority.

### 4.3 Planning is not enforcement

Agents may propose actions, but the platform independently checks user context, connection state, capability grants, deployment policy, approval validity, and provider prerequisites before execution.

### 4.4 Honest outcomes

The platform distinguishes confirmed success, confirmed failure, pending, cancelled, expired, and unknown outcomes. A handoff, payment authorization, timeout, or agent statement is not proof that an order, booking, ride, message, or other external result exists.

### 4.5 Explicit consequential action

Reads may proceed within configured grants and policy. External changes require approval when policy classifies them as consequential. Approval is exact, time-bound, price-bound when relevant, single-use, and non-replayable.

### 4.6 Global without false universality

The platform is locale-aware and region-neutral. Integrations declare regional availability. Global scope does not imply that every service or action works in every country.

### 4.7 Open and self-hostable

The runnable core, integration protocol and adapters, reference host, conformance sandbox, and bundled foundational integrations belong in the open-source scope. A deployment must not require proprietary Vox-hosted services.

### 4.8 Data minimization

Agents and remote tools receive only context needed for the current task or invocation. Credentials remain outside agent context. Audit and observability records do not become covert copies of conversations or provider payloads.

## 5. Goals

### 5.1 First-release goals

- Prove that multiple host apps can use the same platform boundary.
- Prove that multiple independently configured agents can use reusable integrations without owning connections.
- Provide a reusable connection and authorization journey independent of Vox's UI.
- Enforce grants and approvals outside agent behavior.
- Execute at least one connected read and one consequential connected write.
- Prove transactional semantics through a deterministic conformance sandbox.
- Support at least one user-added remote integration.
- Support one-time and simple recurring reminders.
- Provide durable tasks and runs that survive host-app disconnection.
- Provide structured, privacy-conscious audit evidence and replaceable observability.
- Demonstrate that a model provider, integration, and host app can each be replaced without changing core domain concepts.
- Preserve historical action evidence when an integration is removed.

### 5.2 Longer-term goals enabled by the foundation

- Add regional and global service integrations, including travel, commerce, food, rides, communication, productivity, and developer tools.
- Add richer automation rules as an explicit authority concept.
- Support agent-to-agent delegation with scoped context and authority.
- Support explicit cross-host-app connection sharing.
- Support additional extension execution models, including safely isolated local code if justified.
- Support richer team and organizational administration.

## 6. Non-goals for the first release

- Universal direct execution for every named consumer service.
- Automatic web or app interaction that bypasses provider terms or verified access.
- Uploaded untrusted code executing inside the platform.
- Automatic agent-to-agent delegation.
- Autonomous tasks initiated by external events.
- Scheduled purchases, bookings, messages, or other consequential transactions.
- Raw card or bank-detail collection or storage.
- Automatic credential migration between deployments.
- Automatic connection sharing across host apps.
- Identity linking based only on matching email addresses.
- An all-or-nothing transaction spanning multiple external services.
- A marketplace ranking or commercial settlement system.
- A second polished consumer application.
- A commitment to a particular language, database, cloud, framework, model, identity provider, protocol, or deployment topology in this PRD.

## 7. Users and actors

### 7.1 End user

A person using Vox or another host app to ask an agent for help, connect external accounts, manage grants, approve actions, maintain saved preferences, configure reminders, and inspect task outcomes.

### 7.2 Host-app developer

A developer embedding the platform in another application. The developer supplies a user experience and trusted user identity, initiates connection flows, renders proposals, submits authenticated decisions, and displays authoritative task state.

### 7.3 Agent author

A creator defining an agent's purpose, behavioral instructions, and requested capability categories. The author does not receive user credentials or automatic access.

### 7.4 Integration operator

The party operating a remote integration or maintaining a service adapter. The operator declares capabilities, effects, access requirements, data recipients, regions, and behavioral guarantees.

### 7.5 Deployment operator

The party running a Vox deployment. The operator configures identity adapters, model providers, enabled integrations, consequential-capability policy, operational quotas, retention, reminder delivery, and observability sinks.

### 7.6 Host organization administrator

An optional administrator within a host app's organization. The administrator may define application quotas or spending policies but cannot convert policy into user approval.

### 7.7 External service

A provider such as a calendar, email, commerce, travel, food, ride, payment, or communication service. It remains authoritative for its account access and external outcomes.

## 8. Jobs to be done

### 8.1 End-user jobs

- When I ask for help, I want the agent to use only the accounts and capabilities I authorized.
- When an action affects the outside world, I want to see and approve the material details before it occurs.
- When a service cannot be executed directly, I want a truthful handoff rather than a false success claim.
- When an operation fails or becomes uncertain, I want to know exactly what is confirmed and what is unresolved.
- When I connect or disconnect an account, I want to understand which agents and capabilities are affected.
- When I install an agent or integration, I want to understand its operator, requested access, external data recipients, effects, and regional availability.
- When I set a reminder, I want its timezone, recurrence, delivery channel, and delivery status to be explicit.
- When I use more than one app powered by Vox, I want my data isolated unless I explicitly choose to share it.

### 8.2 Host-app developer jobs

- I want to embed agents and capabilities without recreating connection, approval, and execution safety machinery.
- I want to provide my own identity and interface without requiring my users to create separate Vox accounts.
- I want durable task status even if my client disconnects.
- I want authenticated change notifications while retaining authoritative status retrieval.
- I want to replace model, identity, notification, and observability providers without redefining core product concepts.

### 8.3 Integration-author jobs

- I want to register a remote capability using a stable, protocol-neutral contract.
- I want to state provider-specific guarantees without pretending every provider behaves identically.
- I want a conformance environment that proves success, failure, timeout, cancellation, refund, and unknown-outcome behavior.

### 8.4 Deployment-operator jobs

- I want to enable or disable integrations and consequential capabilities without changing platform code.
- I want to configure identity sources, models, quotas, retention, observability, and delivery channels.
- I want audit evidence for security and operational diagnosis without exposing credentials or hidden model reasoning.

## 9. Domain model

The canonical definitions live in `CONTEXT.md`. The product relationships are:

- A **deployment** hosts one or more host apps.
- A **host app** supplies presentation and authenticated identity.
- A **user context** isolates a host app's user, optionally inside a host organization, on one deployment.
- An **agent** belongs to or is available within a user context and requests capability categories.
- An **integration** exposes one or more tools or capabilities independently of agents and user accounts.
- A **connection** links a user context to one external account.
- A **service authorization** describes what the external service permits.
- An **agent access grant** selects the connection and capabilities an agent may use within service authorization and platform policy.
- A **task** represents a requested outcome.
- A **run** represents one attempt to pursue the task.
- An **action proposal** describes exact intended external effects.
- A **user approval** authorizes one valid proposal or disclosed group of exact proposals.
- An **action attempt** records one execution attempt and its outcome.
- A **handoff** transfers continuation to an external service without claiming completion.
- A **saved preference** stores user-managed information for later tasks but grants no action authority.
- A **reminder** schedules a notification but grants no authority for another action.

## 10. End-to-end experience

### 10.1 Standalone Vox onboarding

1. The user chooses an allowed identity method.
2. The selected identity adapter authenticates the user.
3. The platform establishes a Vox host-app user context.
4. The user sees available agents and capabilities without being asked to connect every possible service.
5. When a chosen capability requires an account, the user enters the reusable connection flow.

### 10.2 Embedded host-app onboarding

1. The host app authenticates its user.
2. The host app establishes its trusted identity relationship with the platform.
3. The platform maps the identity into an isolated host-app user context.
4. The host app retrieves agents and capabilities available under deployment and organization policy.
5. The user initiates connection only when needed.

### 10.3 Connecting an account

1. The host app initiates a connection flow for a selected integration.
2. The platform displays or supplies presentation data for the integration operator, requested service access, capabilities, data recipients, regions, and credential-custody model.
3. The user authorizes through the external service or explicitly consents to an external operator's authorization flow.
4. The platform binds the result to the correct deployment, host app, organization if present, and host user.
5. The platform reports the actual account identity, authorization state, available capabilities, and limitations.
6. The flow may offer explicit grants for a selected agent. Connection and grant remain distinct even if presented in one journey.
7. No other agent or host app inherits access.

### 10.4 Starting and running a task

1. The user or host app selects an agent and provides an outcome request.
2. The platform creates a durable task and run.
3. The agent receives relevant task context, allowed preferences, and currently discoverable capabilities.
4. The agent plans and requests tool use.
5. The platform checks user context, integration state, connection state, grant, policy, regional availability, and operational quota.
6. Non-consequential reads execute if allowed.
7. Missing information or account ambiguity pauses the run for clarification.
8. Consequential actions become exact proposals rather than immediate execution.

### 10.5 Approving and executing an action

1. The platform supplies the host app with an exact proposal.
2. The host app renders account, provider, recipients, location, timing, item details, total and currency, cancellation terms, data recipients, and expiry as applicable.
3. The user approves or rejects through an authenticated interaction.
4. The platform binds the decision to the exact proposal and verifies it has not expired or materially changed.
5. Spending policy, grant, connection, provider prerequisites, and current relevant conditions are rechecked.
6. Provider payment authentication occurs separately when required.
7. The platform makes one authorized execution attempt.
8. The platform records confirmed success, confirmed failure, cancellation, pending, or unknown outcome.
9. An unknown outcome is reconciled before any retry.
10. The agent explains authoritative state without representing its own narrative as evidence.

### 10.6 Handoff

1. The platform determines direct execution is unavailable or intentionally unsupported.
2. The host app clearly labels the transition as a handoff.
3. Material prepared information may be transferred only as disclosed and permitted.
4. The external service becomes responsible for continuation.
5. Vox does not report completion without an authoritative confirmation path.

### 10.7 Revocation

1. The user may disable one agent's grant while preserving the connection for other agents.
2. The user may disconnect the account for the entire user context.
3. Disconnect blocks new platform use, removes platform-held credentials, and attempts service-side revocation where supported.
4. Remaining external-operator access is disclosed.
5. Revocation does not undo completed actions and may not cancel in-flight provider work.

### 10.8 Reminder

1. The user requests a one-time or simple recurring reminder.
2. The platform resolves an explicit timezone, recurrence, and host-app delivery channel.
3. The user confirms ambiguous timing.
4. The platform records scheduled state.
5. At trigger time, the delivery adapter attempts notification.
6. The reminder becomes delivered-to-channel, failed, or delivery-unknown.
7. Failure may retry only within the disclosed window.
8. Missed reminders are surfaced and not silently delivered much later.

## 11. Functional requirements

Priorities use **P0** for required first-release behavior, **P1** for important follow-up behavior compatible with the first-release model, and **P2** for future expansion.

### 11.1 Deployment and host applications

- **FR-DEP-001 (P0):** The platform shall run independently of proprietary Vox-hosted services.
- **FR-DEP-002 (P0):** Vox shall consume the same public platform boundary available to other host apps.
- **FR-DEP-003 (P0):** The platform shall register multiple host apps within one deployment.
- **FR-DEP-004 (P0):** The platform shall isolate data and authority by deployment, host app, optional host organization, and host user.
- **FR-DEP-005 (P0):** A minimal reference host shall demonstrate external identity, account connection, task initiation, proposal approval, client reconnection, and status retrieval.
- **FR-DEP-006 (P0):** A host app shall be unable to assert arbitrary user identity or approval without platform-verifiable authentication.
- **FR-DEP-007 (P1):** Host apps shall be able to declare application-specific quotas and spending policies.
- **FR-DEP-008 (P2):** The platform may support in-process embedding without changing core domain semantics.

### 11.2 Identity

- **FR-ID-001 (P0):** Identity-provider implementations shall be replaceable adapters.
- **FR-ID-002 (P0):** Standalone Vox shall support at least one federated identity path and one passwordless recovery-capable path.
- **FR-ID-003 (P0):** Host apps shall be able to provide authenticated user identity through an established trust relationship.
- **FR-ID-004 (P0):** A provider identity shall map into a platform user context rather than become the canonical domain identity.
- **FR-ID-005 (P0):** Matching email addresses shall not automatically link users across host apps.
- **FR-ID-006 (P1):** Linking login identities shall require proof of control of both identities.
- **FR-ID-007 (P1):** Identity linking shall not automatically merge host-app contexts, connections, grants, preferences, or histories.

### 11.3 Agents and model providers

- **FR-AGT-001 (P0):** The platform shall support multiple independently configured agents.
- **FR-AGT-002 (P0):** A general-purpose agent shall be available as the default first-release experience.
- **FR-AGT-003 (P0):** Users or host apps shall select the agent for a task.
- **FR-AGT-004 (P0):** An agent definition shall express purpose, behavior, and requested capability categories independently of model provider.
- **FR-AGT-005 (P0):** Agent installation shall grant no account or capability access.
- **FR-AGT-006 (P0):** Agent-requested capabilities shall be treated as untrusted requirements.
- **FR-AGT-007 (P0):** Agents shall never receive raw service credentials or payment credentials.
- **FR-AGT-008 (P0):** Changing an allowed model configuration shall not alter grants, approval rules, or platform enforcement.
- **FR-AGT-009 (P1):** Deployment or host-app policy shall constrain selectable model configurations.
- **FR-AGT-010 (P2):** Agent-to-agent delegation may be added only with explicit context and authority propagation rules.

### 11.4 Integration registration and discovery

- **FR-INT-001 (P0):** The platform shall model integrations independently of agents and connections.
- **FR-INT-002 (P0):** An integration shall expose one or more independently describable capabilities.
- **FR-INT-003 (P0):** Integration registration shall declare operator, capability purpose, inputs, outputs, external effects, account access, data recipients, supported regions, approval needs, and failure or uncertainty outcomes.
- **FR-INT-004 (P0):** Integration declarations shall be treated as untrusted claims subject to validation.
- **FR-INT-005 (P0):** The platform integration model shall remain protocol-neutral.
- **FR-INT-006 (P0):** MCP shall be supported as an adapter without receiving inherent trust or authority.
- **FR-INT-007 (P0):** Direct APIs, SDK-backed adapters, and compatible remote protocols shall be representable without redefining core authorization concepts.
- **FR-INT-008 (P0):** Integrations shall declare optional guarantees, including reconciliation, cancellation, refunds, streaming status, and idempotent execution where supported.
- **FR-INT-009 (P0):** Agents and workflows shall rely only on guarantees explicitly declared and validated for the selected integration version.
- **FR-INT-010 (P0):** Discovery shall include only capabilities enabled by deployment policy and usable under the current user context.
- **FR-INT-011 (P0):** Removing an integration shall preserve historical task and action evidence.
- **FR-INT-012 (P1):** The platform shall support separately distributed proprietary integrations under the same authority boundary as open integrations.

### 11.5 Extension lifecycle and conformance

- **FR-EXT-001 (P0):** Version one shall support user-added remote integrations.
- **FR-EXT-002 (P0):** Version one shall not execute uploaded untrusted integration code inside the platform.
- **FR-EXT-003 (P0):** Installing an extension shall grant no connection, capability, context, or action authority.
- **FR-EXT-004 (P0):** Consequential capabilities shall remain disabled until conformance succeeds and the deployment operator enables them.
- **FR-EXT-005 (P0):** Conformance shall not replace user grants or action approval.
- **FR-EXT-006 (P0):** Integration updates shall never silently expand existing grants.
- **FR-EXT-007 (P0):** New capabilities shall require explicit enablement.
- **FR-EXT-008 (P0):** Material changes to permissions, data recipients, operator, or effects shall require renewed consent before affected use.
- **FR-EXT-009 (P0):** A deterministic transactional sandbox shall simulate success, rejection, price change, provider authentication, timeout, duplicate attempts, cancellation, refund, and unknown outcome.
- **FR-EXT-010 (P0):** The sandbox shall be clearly identified as test infrastructure and never as production consumer coverage.

### 11.6 Connections and service authorization

- **FR-CON-001 (P0):** A connection shall belong to one user context and identify one external account.
- **FR-CON-002 (P0):** A connection shall not belong to an agent.
- **FR-CON-003 (P0):** Connections shall not automatically cross host-app boundaries.
- **FR-CON-004 (P0):** The platform shall provide a reusable connection-authorization journey that host apps can initiate and present.
- **FR-CON-005 (P0):** Authorization results shall bind to the correct deployment, host app, organization if present, and user.
- **FR-CON-006 (P0):** The platform shall report actual connected account identity, current authorization state, capability availability, and known limitations.
- **FR-CON-007 (P0):** The platform shall distinguish platform-held credential custody from external-operator authorization.
- **FR-CON-008 (P0):** Credentials shall not be forwarded to a remote operator without explicit disclosure and consent.
- **FR-CON-009 (P0):** Expired or revoked service authorization shall pause affected work.
- **FR-CON-010 (P0):** The platform shall never silently switch connections or expand permissions after access failure.
- **FR-CON-011 (P0):** Reconnection shall recheck authorization and relevant task facts.
- **FR-CON-012 (P0):** Disconnect shall block future platform use, remove platform-held credentials, and attempt service-side revocation where supported.
- **FR-CON-013 (P0):** Disconnect shall disclose known external-operator access that may remain.

### 11.7 Agent access grants

- **FR-GRT-001 (P0):** A grant shall bind one agent, selected capabilities, and a selected connection within one user context.
- **FR-GRT-002 (P0):** New agents shall inherit no grants.
- **FR-GRT-003 (P0):** Connecting an account shall not automatically grant every capability.
- **FR-GRT-004 (P0):** Connection and grant may be presented in one journey but shall remain distinct authorization records.
- **FR-GRT-005 (P0):** Users shall be able to disable an agent's grant without disconnecting the account.
- **FR-GRT-006 (P0):** Disabling one grant shall preserve unrelated grants where policy permits.
- **FR-GRT-007 (P0):** Grants shall never exceed service authorization or deployment policy.
- **FR-GRT-008 (P0):** A grant shall not authorize a specific consequential action.

### 11.8 Tasks and runs

- **FR-TSK-001 (P0):** Tasks and runs shall be durable platform resources independent of a live client connection.
- **FR-TSK-002 (P0):** Host apps shall retrieve authoritative current task and run status after reconnecting.
- **FR-TSK-003 (P0):** Client disconnection shall not be interpreted as execution failure.
- **FR-TSK-004 (P0):** Client disconnection shall not trigger blind retries.
- **FR-TSK-005 (P0):** Runs shall support waiting for clarification, approval, provider authentication, reconnection, and outcome reconciliation.
- **FR-TSK-006 (P0):** Cancellation shall stop future work where possible without claiming guaranteed cancellation of an in-flight provider action.
- **FR-TSK-007 (P0):** Undo shall be represented as a separate capability and action rather than an implied effect of task cancellation.
- **FR-TSK-008 (P0):** Multi-service tasks shall track outcomes per action rather than claim atomicity.
- **FR-TSK-009 (P0):** Partial success shall be reported explicitly.
- **FR-TSK-010 (P0):** The platform shall not automatically undo a successful action or switch providers after another action fails.
- **FR-TSK-011 (P0):** Dependent work shall pause when prerequisite outcomes are failed or unknown.

### 11.9 Tool invocation and context minimization

- **FR-TOL-001 (P0):** The platform shall mediate tool execution independently of agent instructions.
- **FR-TOL-002 (P0):** Each invocation shall include only context required for that capability invocation.
- **FR-TOL-003 (P0):** Remote tools shall not automatically receive the entire conversation, unrelated preferences, or unrelated connection data.
- **FR-TOL-004 (P0):** Sensitive data recipients shall be disclosed before applicable use.
- **FR-TOL-005 (P0):** External content shall be treated as task data and shall not expand authority.
- **FR-TOL-006 (P0):** Tool execution shall be blocked when connection, grant, policy, region, conformance, or approval requirements are not satisfied.
- **FR-TOL-007 (P0):** Capability unavailability shall produce an honest explanation and optional handoff rather than fabricated execution.

### 11.10 Proposals and user approvals

- **FR-APR-001 (P0):** Consequential actions shall require a platform-issued proposal before execution.
- **FR-APR-002 (P0):** A proposal shall disclose material details applicable to the action, including selected account, provider, recipients, location, timing, content, item, price, currency, fees, cancellation terms, data recipients, and expiry.
- **FR-APR-003 (P0):** Host apps shall be able to render proposals and return authenticated user decisions.
- **FR-APR-004 (P0):** Approval shall bind to the exact proposal and authenticated user context.
- **FR-APR-005 (P0):** Changed material details shall invalidate prior approval.
- **FR-APR-006 (P0):** Expired proposals shall require refresh and fresh approval.
- **FR-APR-007 (P0):** Approval shall be single-use and consumed by one execution attempt.
- **FR-APR-008 (P0):** Approval shall not be replayed after an unknown outcome.
- **FR-APR-009 (P0):** One approval may cover a disclosed group of exact actions while preserving separate authority and outcome tracking for each.
- **FR-APR-010 (P0):** Unresolved future actions shall not be included under blanket plan approval.
- **FR-APR-011 (P0):** Agent claims and arbitrary host-app flags shall not count as user approval.
- **FR-APR-012 (P0):** Revocation, deletion, or rejection shall not be represented as undo of completed external actions.

### 11.11 Price, payment, and spending policy

- **FR-PAY-001 (P0):** Priced-action proposals shall disclose exact current total and currency by default.
- **FR-PAY-002 (P0):** Any price increase shall require fresh approval unless the user explicitly set a maximum for that action.
- **FR-PAY-003 (P0):** The platform shall never infer price tolerance.
- **FR-PAY-004 (P0):** Taxes, fees, and provider charges shall be disclosed when available and shall not be misrepresented by an incomplete subtotal.
- **FR-PAY-005 (P0):** Version one shall not collect or store raw card or bank details.
- **FR-PAY-006 (P0):** Agents shall never receive payment credentials.
- **FR-PAY-007 (P0):** Provider-held payment methods may be shown only through safe user-recognizable identifiers.
- **FR-PAY-008 (P0):** Provider-required payment authentication shall remain distinct from platform action approval.
- **FR-PAY-009 (P0):** Payment authorization alone shall not be reported as a completed external outcome.
- **FR-PAY-010 (P0):** Spending policies shall constrain execution independently of user approval.
- **FR-PAY-011 (P0):** Spending policy shall never authorize a transaction.
- **FR-PAY-012 (P0):** Operational model and infrastructure quotas shall remain separate from external transaction limits.
- **FR-PAY-013 (P0):** Quota exhaustion shall pause work without silent switching to another paid provider, account, or connection.

### 11.12 Execution outcomes and reconciliation

- **FR-EXE-001 (P0):** The platform shall record an action outcome as pending, confirmed success, confirmed failure, cancelled, expired, or unknown.
- **FR-EXE-002 (P0):** A timeout or lost client connection shall not be treated as confirmed failure.
- **FR-EXE-003 (P0):** An unknown outcome shall trigger supported reconciliation before retry.
- **FR-EXE-004 (P0):** If reconciliation is unsupported or inconclusive, the run shall pause and explain uncertainty.
- **FR-EXE-005 (P0):** The platform shall not blindly retry consequential actions.
- **FR-EXE-006 (P0):** Provider idempotency guarantees shall be used only when explicitly supported.
- **FR-EXE-007 (P0):** Success shall require authoritative confirmation of the requested external result.
- **FR-EXE-008 (P0):** Payment, handoff, or request acceptance shall not substitute for result confirmation.

### 11.13 Handoffs

- **FR-HND-001 (P0):** The platform shall support explicit handoff when direct execution is unavailable.
- **FR-HND-002 (P0):** The host app shall clearly label a handoff before transferring the user.
- **FR-HND-003 (P0):** A handoff shall disclose what information will be transferred.
- **FR-HND-004 (P0):** The platform shall not mark the requested action complete solely because a handoff opened successfully.
- **FR-HND-005 (P1):** The platform may reconcile post-handoff outcomes only through an authoritative provider mechanism.

### 11.14 Saved preferences

- **FR-PRF-001 (P0):** Saved preferences shall be user-managed and separate from agent definitions and conversation history.
- **FR-PRF-002 (P0):** Saved preferences shall remain within one user context.
- **FR-PRF-003 (P0):** The platform shall ask before saving sensitive information or replacing an existing preference.
- **FR-PRF-004 (P0):** Conversation content shall not silently become permanent memory.
- **FR-PRF-005 (P0):** Agents shall receive only relevant, permitted preferences.
- **FR-PRF-006 (P0):** Preferences shall grant no capability, account, payment, or action authority.
- **FR-PRF-007 (P0):** Locale preferences shall include language, locale, timezone, units, and display currency.
- **FR-PRF-008 (P0):** Display preferences shall never silently replace authoritative provider currency or timezone.

### 11.15 Reminders

- **FR-REM-001 (P0):** The platform shall support one-time reminders.
- **FR-REM-002 (P0):** The platform shall support simple interval and calendar recurrence.
- **FR-REM-003 (P0):** Each reminder shall have an explicit timezone and delivery channel.
- **FR-REM-004 (P0):** Every host app supporting reminders shall provide at least one declared delivery channel.
- **FR-REM-005 (P0):** Reminder status shall distinguish scheduled, delivered-to-channel, failed, and delivery-unknown.
- **FR-REM-006 (P0):** Delivered-to-channel shall not be represented as proof the human saw the reminder.
- **FR-REM-007 (P0):** Retry behavior and retry window shall be disclosed.
- **FR-REM-008 (P0):** Missed reminders shall be surfaced rather than silently delivered substantially later.
- **FR-REM-009 (P0):** A reminder shall not authorize a purchase, booking, message, or other external action.

### 11.16 External events and notifications

- **FR-EVT-001 (P0):** External events may update an existing task or external-action status.
- **FR-EVT-002 (P0):** External events shall not create new autonomous tasks in version one.
- **FR-EVT-003 (P0):** External events shall not create or expand authority.
- **FR-EVT-004 (P0):** The platform may notify users or prepare options in response to an event.
- **FR-EVT-005 (P0):** Consequential follow-up actions shall still require grants, policy checks, and exact approval.
- **FR-EVT-006 (P0):** Host apps shall be able to retrieve authoritative task state.
- **FR-EVT-007 (P0):** Host apps shall be able to receive authenticated change notifications.
- **FR-EVT-008 (P0):** Change notifications shall be treated as hints and may be delayed or duplicated.
- **FR-EVT-009 (P0):** Notification consumers shall fetch authoritative state before presenting consequential status.

### 11.17 Global and regional behavior

- **FR-GLB-001 (P0):** Capabilities shall declare supported regions and current availability.
- **FR-GLB-002 (P0):** The platform shall not silently substitute a different country, currency, provider, or account.
- **FR-GLB-003 (P0):** Consequential proposals shall display authoritative provider currency and applicable timezone.
- **FR-GLB-004 (P0):** Unsupported direct execution shall produce a truthful limitation and optional handoff.
- **FR-GLB-005 (P1):** Integrations may provide regional capability variants without redefining the platform integration model.

### 11.18 Audit and observability

- **FR-AUD-001 (P0):** Audit evidence shall record task and action IDs, actor, selected agent and model configuration, integration and capability versions, connection reference, grant and approval references, timestamps, material proposal details, attempts, and outcomes.
- **FR-AUD-002 (P0):** Audit evidence shall exclude raw credentials and payment credentials.
- **FR-AUD-003 (P0):** Audit evidence shall not require private model reasoning.
- **FR-AUD-004 (P0):** Complete provider payloads shall not be retained as audit evidence by default.
- **FR-AUD-005 (P0):** Privileged administrative access shall be recorded.
- **FR-AUD-006 (P0):** Observability sinks shall be replaceable and deployment-controlled.
- **FR-AUD-007 (P0):** Sensitive data shall be redacted before observability export.
- **FR-AUD-008 (P0):** External observability sinks shall be disclosed.
- **FR-AUD-009 (P0):** User-context boundaries shall be preserved in logs, metrics, traces, and administrative tools.

### 11.19 Retention and deletion

- **FR-DAT-001 (P0):** The platform shall retain user-visible task history and a minimal action record by default.
- **FR-DAT-002 (P0):** Temporary execution context shall be removed after completion according to declared retention policy.
- **FR-DAT-003 (P0):** Saved preferences shall be managed separately from task history.
- **FR-DAT-004 (P0):** Deployments shall declare retention and backup behavior.
- **FR-DAT-005 (P0):** Users shall be able to request deletion of platform-controlled task history.
- **FR-DAT-006 (P0):** Deletion shall disclose external-service records, remote-operator copies, mandatory audit retention, and backup timing beyond immediate platform control.
- **FR-DAT-007 (P0):** Local deletion shall not be represented as universal deletion or undo.
- **FR-DAT-008 (P0):** Ordinary administration shall not expose conversations or credentials as a product feature.
- **FR-DAT-009 (P0):** The product shall disclose that infrastructure operators may possess technical access to systems they control.

### 11.20 Portability

- **FR-PRT-001 (P0):** Agent definitions shall be exportable in a documented portable representation.
- **FR-PRT-002 (P0):** Integration registrations and non-secret configuration shall be exportable.
- **FR-PRT-003 (P0):** Non-secret grants and saved preferences shall be exportable.
- **FR-PRT-004 (P0):** Task and audit history shall be separately exportable because of its sensitivity.
- **FR-PRT-005 (P0):** Exports shall never contain raw credentials, active approvals, or reusable action authority.
- **FR-PRT-006 (P0):** Imported connections shall require renewed authorization on the destination deployment.

### 11.21 Open-source distribution

- **FR-OSS-001 (P0):** The open-source scope shall include a runnable platform core.
- **FR-OSS-002 (P0):** The open-source scope shall include the integration protocol and foundational adapters.
- **FR-OSS-003 (P0):** The open-source scope shall include the reference host and conformance sandbox.
- **FR-OSS-004 (P0):** Bundled foundational integrations shall be open where provider terms permit.
- **FR-OSS-005 (P0):** Self-hosting shall not require proprietary Vox services.
- **FR-OSS-006 (P0):** Provider credentials and partnerships shall not be presented as conferred by self-hosting.
- **FR-OSS-007 (P0):** Proprietary integrations shall receive no elevated privilege.
- **FR-OSS-008 (P1):** License selection and distribution policy shall be completed with legal review before public release.

## 12. Non-functional requirements

### 12.1 Security

- **NFR-SEC-001:** Deny execution by default when identity, connection, grant, policy, approval, or provider state cannot be verified.
- **NFR-SEC-002:** Secrets shall be encrypted in transit and at rest wherever the deployment retains them.
- **NFR-SEC-003:** Secrets shall never be included in agent prompts, model context, browser-readable configuration, logs, traces, exports, or audit records.
- **NFR-SEC-004:** Host-app identity and approval assertions shall be authenticated and protected from replay.
- **NFR-SEC-005:** Proposal approval shall be tamper-evident and bound to user context, proposal contents, expiry, and execution attempt.
- **NFR-SEC-006:** Remote integration traffic shall authenticate the integration endpoint and protect request integrity.
- **NFR-SEC-007:** User-context isolation shall be enforced on every data and execution path rather than only in UI navigation.
- **NFR-SEC-008:** Administrative capabilities shall be separately authorized and audited.
- **NFR-SEC-009:** Consequential-capability enablement shall fail closed when conformance or operator policy is missing.

### 12.2 Reliability

- **NFR-REL-001:** Durable task state shall survive process restart and client disconnection.
- **NFR-REL-002:** Action execution shall tolerate duplicated internal delivery without duplicating an external action when the provider supports safe deduplication.
- **NFR-REL-003:** Unsupported deduplication or reconciliation shall be surfaced as a capability limitation.
- **NFR-REL-004:** Platform recovery shall preserve pending approvals, action attempts, and unknown outcomes without replaying authority.
- **NFR-REL-005:** Status notifications may be at-least-once, while authoritative state remains queryable.
- **NFR-REL-006:** Reminder scheduling and delivery shall preserve timezone intent across restarts and daylight-saving changes.

### 12.3 Privacy

- **NFR-PRI-001:** Data minimization shall be applied per tool invocation.
- **NFR-PRI-002:** Sensitive data recipients and remote operators shall be disclosed before transfer.
- **NFR-PRI-003:** Retention defaults shall favor the minimum data needed for user history, action evidence, and operational recovery.
- **NFR-PRI-004:** Private model reasoning shall not be stored or exposed as a product feature.
- **NFR-PRI-005:** Users shall have clear controls for preferences, task-history deletion, grants, and connections.

### 12.4 Extensibility

- **NFR-EXT-001:** Adding an integration shall not require changes to core identity, connection, grant, approval, task, run, or audit concepts.
- **NFR-EXT-002:** Adding a host app shall not require changes to provider-specific integrations.
- **NFR-EXT-003:** Replacing a model provider shall not change authorization behavior.
- **NFR-EXT-004:** Protocol adapters shall map to stable platform semantics rather than leak protocol-specific authority into the core model.
- **NFR-EXT-005:** Historical records shall remain interpretable after integration upgrade or removal.

### 12.5 Operability

- **NFR-OPS-001:** Deployments shall expose health and readiness appropriate to platform, worker, connection, and adapter dependencies.
- **NFR-OPS-002:** Operators shall diagnose failed, pending, and unknown outcomes without viewing raw credentials or complete private content.
- **NFR-OPS-003:** Configuration errors shall fail explicitly rather than silently disabling enforcement.
- **NFR-OPS-004:** Integration and capability versions shall be visible in execution and audit records.
- **NFR-OPS-005:** Operational limits and degraded provider states shall be visible to host apps and agents in non-sensitive form.

### 12.6 Accessibility and localization

- **NFR-ACC-001:** Vox-owned approval, connection, reminder, and task-status interfaces shall meet WCAG 2.2 AA.
- **NFR-ACC-002:** Consequential action details shall not rely on color alone.
- **NFR-ACC-003:** Currency, date, time, timezone, address, and unit presentation shall support localization without altering authoritative values.
- **NFR-ACC-004:** Approval interfaces shall remain understandable with assistive technology and keyboard-only navigation.

### 12.7 Performance targets

Targets below apply to platform-controlled processing and exclude external provider latency.

- **NFR-PER-001:** Cached capability discovery should complete at p95 within 500 ms under the supported reference load.
- **NFR-PER-002:** Authoritative task-status retrieval should complete at p95 within 500 ms under the supported reference load.
- **NFR-PER-003:** Platform policy evaluation before tool execution should complete at p95 within 200 ms.
- **NFR-PER-004:** Host-app change notification creation should occur within 5 seconds of committed platform state change at p95.
- **NFR-PER-005:** Performance targets shall be measured with published reference hardware and load assumptions before release claims are made.

## 13. First-release scope

### 13.1 Required capability proof

1. **Built-in reminders:** One-time and simple recurring reminders through at least one Vox channel and one replaceable reference-host channel.
2. **Connected read:** A production-capable integration that reads selected user-authorized information with minimized context.
3. **Consequential write:** A production-capable integration that creates an external change only after exact approval.
4. **Transactional sandbox:** A deterministic provider exercising price, payment authentication, success, rejection, timeout, duplicate prevention, cancellation, refund, and unknown outcome.
5. **Remote extension:** A user-added remote integration registered without modifying platform core.
6. **Second host app:** A minimal reference client using external identity and the public platform boundary.

### 13.2 Candidate branded integrations

Amazon, Expedia, Zomato, and Uber are integration targets, not unconditional release commitments. Each target must pass feasibility review covering:

- Official production access route
- Permitted use case and applicable provider terms
- Consumer versus merchant or partner account model
- Supported countries and currencies
- Authentication and credential custody
- Search, quote, cart, execution, status, cancellation, refund, and reconciliation behavior
- Payment responsibilities
- Rate limits and commercial costs
- Data retention and deletion requirements
- Conformance and operational support

The release plan may ship discovery or handoff before direct execution. Product copy must describe the actual supported level.

### 13.3 Existing repository baseline

The current repositories provide a starting implementation, not a final allocation of the accepted product model:

- **vox-core:** Existing Rust core with conversations, agents, events, schedules, summaries, user context, jobs, and actions. It currently assumes PostgreSQL, Redis projections, and existing provider credentials. The PRD does not automatically ratify those choices for every new platform requirement.
- **vox-bridge:** Existing Twilio and WhatsApp ingress plus speech pipeline bridge. It must remain a replaceable channel adapter rather than own prompts, tools, grants, or action authority.
- **vox-web:** Existing Next.js public site and superuser interface. It is not yet the complete end-user Vox host app described by this PRD.
- **vox-deploy:** Existing production release authority for Core and Bridge. It may evolve to deploy the platform but must not make the open core dependent on one hosting topology.
- **agents:** Existing agent work remains logically independent of connection custody and platform authorization.

Repository boundaries may change only after architecture design demonstrates how the accepted domain responsibilities remain deep, testable, and independently replaceable.

## 14. User experience requirements

### 14.1 Required user surfaces in Vox

- Sign in and recovery
- Agent selection and agent details
- Conversation and task initiation
- Capability discovery
- Connection initiation and connection status
- Grant review and modification
- Exact action proposal and approval
- Payment-authentication continuation when required
- Task and per-action status
- Unknown-outcome explanation and recovery choices
- Reminder creation and status
- Saved-preference review and deletion
- Connection disable and disconnect controls
- Task-history deletion and retention explanation
- Installed agent and integration review

### 14.2 UX content rules

- Use “Connect account” for service authorization and “Enable for agent” for agent grants.
- Use “Approve” only for a concrete proposal, not generic account access.
- Use “Continue in [service]” for handoff; do not use “Booked,” “Ordered,” “Purchased,” “Sent,” or “Requested” until confirmed.
- Present confirmed, failed, pending, cancelled, expired, and unknown states distinctly.
- Show provider, account, region, currency, timezone, recipient, location, amount, fees, expiry, and cancellation terms when material.
- Explain whether credentials remain with the platform, the provider, or an external integration operator.
- Explain when a remote operator receives task data.
- Separate disable-agent-access from disconnect-account.
- Distinguish delivered-to-channel from seen for reminders.
- Never expose private model reasoning as an explanation feature.

## 15. Policy model

Execution requires the intersection of all applicable authority and policy layers:

1. The deployment enables the integration and capability.
2. The integration version has required conformance status.
3. The host app and optional organization permit the capability.
4. The external service authorization remains valid.
5. The connection belongs to the current user context.
6. The selected agent has a grant for the connection and capability.
7. Operational quota permits processing.
8. Spending policy permits the proposed transaction.
9. The proposal remains current and valid.
10. The authenticated user supplied required approval.
11. Provider payment authentication or other provider confirmation succeeds when required.

Failure at any layer blocks execution. No layer alone grants sufficient authority.

## 16. State and outcome model

### 16.1 Task states

- Requested
- Active
- Waiting for clarification
- Waiting for connection
- Waiting for approval
- Waiting for provider authentication
- Waiting for provider outcome
- Partially completed
- Completed
- Failed
- Cancelled

### 16.2 Proposal states

- Draft
- Ready for approval
- Approved
- Rejected
- Expired
- Invalidated by change
- Consumed

### 16.3 Action-attempt outcomes

- Pending
- Confirmed success
- Confirmed failure
- Cancelled before execution
- Cancellation requested
- Unknown

The exact persistence representation is an architecture concern. These semantic distinctions are product requirements.

## 17. Success metrics

### 17.1 Platform proof metrics

- A second host app completes identity, connection, task, approval, and status flows without using private Vox interfaces.
- A new conforming remote integration is added without changes to core identity, grant, approval, task, run, or audit logic.
- A model-provider replacement passes the same authorization and action-safety acceptance suite.
- Integration removal preserves readable historical action evidence.
- The transactional sandbox passes every required scenario deterministically.

### 17.2 User trust metrics

- Zero confirmed consequential actions executed without a valid grant and required approval in acceptance and security testing.
- Zero raw credentials observed in model context, client-readable payloads, logs, traces, exports, or audit records.
- One hundred percent of unknown provider outcomes appear as unknown rather than success or failure.
- One hundred percent of handoffs are labelled before transfer and are not counted as completed transactions.
- One hundred percent of price increases beyond approved bounds require fresh approval.

### 17.3 Experience metrics

- At least 90% of usability-test participants can correctly distinguish connection, agent access, and action approval after onboarding.
- At least 90% can identify whether an action was completed, handed off, pending, or unknown from task status.
- At least 90% can disable one agent's access without disconnecting the service account.
- At least 90% can determine a reminder's timezone and delivery channel before saving it.

### 17.4 Reliability metrics

- No duplicate external effect in the conformance suite under duplicate internal delivery, client reconnect, or process restart.
- All durable task states recover after reference deployment restart.
- Authenticated change notification duplication or delay does not produce incorrect authoritative status in reference clients.

Production service-level objectives require architecture and capacity planning and are not asserted by this PRD.

## 18. Acceptance scenarios

### AS-001: Connection does not grant agent access

Given a user connects a calendar account, when a new agent is installed, then that agent cannot read or write the calendar until the user grants selected capabilities.

### AS-002: Read and write remain distinct

Given an agent may check availability, when it attempts to create an event without a write grant and valid approval, then the platform blocks the action independent of the agent's reasoning.

### AS-003: Exact approval

Given a user approves a ride for a disclosed route, provider, price, currency, and expiry, when the price increases, then the proposal is invalidated and requires fresh approval.

### AS-004: Approval expiry

Given a proposal expires before execution, when the platform receives an execution request, then it refuses execution and obtains a refreshed proposal before seeking approval again.

### AS-005: Unknown outcome

Given a provider times out after receiving a booking request, when the outcome cannot be reconciled, then the task pauses with an unknown outcome and the platform does not replay the approval.

### AS-006: Partial multi-service success

Given a hotel booking succeeds and a ride request fails, then both outcomes are shown separately, the hotel is not automatically cancelled, and recovery requires a user decision.

### AS-007: Client disconnect

Given a host app disconnects while a provider action is pending, when it reconnects, then it retrieves the same durable run and no duplicate action has been triggered because of disconnection.

### AS-008: Remote context minimization

Given a ride tool needs pickup and destination, when invoked from a conversation containing email and travel details, then the remote operator receives only permitted ride inputs and disclosed account context.

### AS-009: Integration update

Given an integration update adds a payment capability or changes its data recipient, when deployed, then existing grants do not expand and affected use requires deployment enablement and renewed user consent.

### AS-010: Host-app isolation

Given the same email address appears in two host apps, when an account is connected in the first app, then the second app cannot see or use the connection without a future explicit sharing flow.

### AS-011: Revocation distinction

Given two agents use one connection, when the user disables access for one agent, then the second agent retains its valid grant; when the user disconnects the account, both agents lose future access.

### AS-012: External operator credential custody

Given a remote integration requires operator-held authorization, when the user connects, then the interface discloses the operator and independent access; Vox does not claim all operator actions are controlled by platform approvals.

### AS-013: Handoff honesty

Given direct Amazon purchase execution is unavailable, when the user chooses an item, then Vox offers a labelled Amazon handoff and does not claim purchase completion.

### AS-014: Reminder delivery

Given a reminder is scheduled in a declared timezone, when delivery succeeds to the configured channel, then status says delivered-to-channel rather than seen; when delivery fails beyond the retry window, the reminder is shown as missed or failed.

### AS-015: Model replacement

Given the deployment changes model provider, when the same action is proposed, then connection, grant, policy, approval, and audit enforcement remain unchanged.

### AS-016: Integration removal

Given completed tasks used an integration version that is later removed, when users inspect history, then material proposals, attempts, and outcomes remain interpretable without calling the removed integration.

### AS-017: Export and migration

Given a user exports portable configuration to another deployment, when imported, then agents, non-secret configuration, and preferences may be restored, while connections require reauthorization and no active approval migrates.

### AS-018: Provider event

Given a flight cancellation event updates an existing task, when the agent prepares alternatives, then no replacement booking occurs until an applicable grant and exact user approval exist.

### AS-019: Spending policy

Given a user approves a transaction above an organization limit, when execution is requested, then the platform blocks it; the approval does not override policy.

### AS-020: Payment authentication

Given an approved booking requires provider payment authentication, when payment succeeds but booking confirmation fails or remains unknown, then Vox does not claim a confirmed booking.

## 19. Release gates

The first release is not complete until all gates pass.

### 19.1 Product gate

- Vox host app completes the required end-to-end journeys.
- Reference host completes its required proof journey.
- Connection, grant, approval, and disconnect concepts are distinguishable in usability testing.
- Direct execution and handoff language is truthful.

### 19.2 Extension gate

- A remote integration can be registered without platform-core modification.
- Declarations and consent render correctly.
- Conformance blocks consequential enablement on failure.
- Integration upgrade does not expand grants.
- Integration removal preserves history.

### 19.3 Security gate

- Cross-user, cross-organization, and cross-host-app isolation tests pass.
- Replay, expired approval, changed proposal, and forged host decision tests pass.
- Credential scanning finds no raw secrets in prohibited surfaces.
- Administrative access controls and audit tests pass.
- Context minimization tests pass for remote invocation.

### 19.4 Reliability gate

- Process restart and client reconnect tests preserve durable task state.
- Transactional sandbox passes every required outcome scenario.
- Duplicate notification and execution-delivery tests do not corrupt authoritative state.
- Unknown outcome handling prevents blind retries.

### 19.5 Open-source gate

- A clean environment can run the core, reference host, sandbox, and foundational integrations without proprietary Vox services.
- Setup documentation distinguishes required operator configuration from bundled functionality.
- No bundled configuration contains provider secrets.
- License and third-party notices pass legal review.

### 19.6 Provider gate

Each branded production integration independently passes:

- Verified official access and permitted use
- Region and account-model validation
- Credential-custody review
- Privacy and data-recipient review
- Consequential-action conformance
- Cancellation, refund, and reconciliation documentation
- Operational ownership and support readiness
- Accurate user-facing capability claims

Failure blocks only that integration's affected capability, not the entire platform release, unless it is the only implementation satisfying a required capability proof.

## 20. Delivery phases

These phases define product increments, not technology or repository structure.

### Phase 0: Contract and feasibility

- Reconcile current implementation with accepted concepts.
- Verify official access paths for candidate production integrations.
- Define provider-neutral contracts for identity, host apps, integrations, connections, grants, proposals, actions, outcomes, notifications, and audit evidence.
- Define conformance cases and reference fixtures.
- Choose first connected read and consequential write providers.
- Complete threat modeling, privacy review, and license review.

**Exit criterion:** Contracts can express every P0 requirement and acceptance scenario without privileging a specific model, identity provider, host app, or integration protocol.

### Phase 1: Platform trust spine

- Implement or adapt user-context isolation.
- Implement host-app trust and identity adapters.
- Implement connection lifecycle and credential custody.
- Implement capability registry and grants.
- Implement durable tasks, runs, proposals, approvals, attempts, and outcomes.
- Implement policy and quota evaluation.
- Implement minimal audit evidence and redacted observability.

**Exit criterion:** A synthetic host and synthetic integration complete read and approved-write flows with security tests passing.

### Phase 2: Conformance and extension system

- Implement remote integration registration.
- Implement protocol adapters, including MCP as one adapter.
- Implement conformance sandbox and operator enablement.
- Implement update-consent behavior and historical version preservation.
- Publish integration-author documentation.

**Exit criterion:** An independently created remote integration passes conformance and operates without core changes.

### Phase 3: Host experiences

- Build the primary Vox end-user journey.
- Build the minimal reference host.
- Implement reusable connection presentation data.
- Implement proposal and approval experiences.
- Implement status, unknown-outcome, handoff, preference, revocation, and deletion experiences.

**Exit criterion:** Vox and the reference host pass the same public-boundary acceptance suite.

### Phase 4: Foundational capabilities

- Implement reminders and replaceable delivery adapters.
- Ship one connected read integration.
- Ship one connected consequential write integration.
- Complete transactional sandbox proof.
- Add one user-added remote integration example.

**Exit criterion:** Every first-release capability proof and release gate passes.

### Phase 5: Branded integration expansion

- Add direct execution where provider access is verified.
- Add discovery or handoff where direct execution is unavailable.
- Complete provider-specific operational readiness.
- Maintain per-region and per-capability truthfulness.

**Exit criterion:** Each integration independently passes the provider gate and accurately advertises its supported level.

## 21. Dependencies

- Verified identity mechanism for standalone Vox and host-app trust.
- A secrets-custody approach suitable for self-hosting.
- At least one provider supporting connected read access.
- At least one provider supporting a consequential write and authoritative outcome retrieval.
- A notification channel for Vox and a replaceable channel contract for host apps.
- Model-provider access for the default agent, without coupling enforcement to that model.
- Legal review for license, provider terms, privacy disclosures, and payment boundaries.
- Security review for isolation, credential custody, proposal approval, remote integrations, and administrative access.
- Operational ownership for production integrations and incident response.

## 22. Risks and mitigations

### 22.1 Provider access is unavailable

**Risk:** Named consumer services may offer only partner, merchant, personal-testing, or handoff access.
**Mitigation:** Verify access before commitment, model capability levels honestly, ship handoff where appropriate, and prove transactional behavior with the sandbox.

### 22.2 Config-driven design becomes an unsafe generic executor

**Risk:** A declarative tool description is mistaken for trusted behavior.
**Mitigation:** Treat declarations as claims, require conformance and deployment enablement, minimize context, and preserve platform-side enforcement.

### 22.3 Abstraction becomes too broad before proof

**Risk:** Supporting every theoretical provider delays end-to-end value.
**Mitigation:** Use the first-release proof set and add abstraction only when a second concrete implementation demonstrates the need.

### 22.4 Remote integration leaks data or abuses credentials

**Risk:** A third-party operator receives more authority than users understand.
**Mitigation:** Prefer platform-held credentials, disclose operator custody and recipients, require explicit consent, enforce least-context invocation, and limit claims when enforcement is impossible.

### 22.5 Agents manipulate approvals

**Risk:** Model output obscures or alters action details.
**Mitigation:** Platform-issued proposals, authenticated host rendering, content binding, expiry, single-use approval, and independent policy checks.

### 22.6 Duplicate consequential action

**Risk:** Retries, disconnects, or timeouts cause duplicate orders or bookings.
**Mitigation:** Attempt identity, provider idempotency where supported, reconciliation, non-replayable approval, and unknown-outcome pause.

### 22.7 Self-hosting creates misleading security expectations

**Risk:** Users assume deployment operators cannot access data.
**Mitigation:** Disclose operator trust, avoid product-level conversation browsing, audit privileged access, and minimize stored sensitive data.

### 22.8 Existing repositories constrain the target model

**Risk:** Current voice, database, provider, and deployment assumptions become accidental permanent architecture.
**Mitigation:** Treat current code as baseline evidence, conduct architecture design against this PRD, and preserve behavior through migration tests rather than preserving every implementation choice.

### 22.9 Global claims exceed regional reality

**Risk:** Users receive incorrect currencies, providers, or service expectations.
**Mitigation:** Explicit locale preferences, authoritative provider values, declared regions, no silent substitution, and per-capability availability.

### 22.10 Audit or observability becomes surveillance

**Risk:** Troubleshooting copies full conversations, provider payloads, or reasoning.
**Mitigation:** Structured evidence, redaction before export, disclosed sinks, retention controls, and prohibited data classes.

## 23. Decisions intentionally deferred to architecture and implementation design

- Programming languages and frameworks
- Database and persistence topology
- Queue, event, scheduling, and worker implementation
- API transport and schema
- Host-app trust protocol
- Proposal-verification mechanism
- Secret encryption and key-management implementation
- OAuth and non-OAuth adapter interfaces
- MCP adapter details
- Model-provider interface
- Reminder scheduler and delivery implementation
- Observability standards and exporters
- Repository responsibility changes
- Deployment topology and supported reference environments
- Exact retention periods and backup windows
- Exact performance load assumptions
- Exact open-source license

Deferral does not weaken the semantic requirements in this PRD.

## 24. Pre-implementation research backlog

### 24.1 Provider feasibility

- Verify Expedia production partner routes, supported booking capabilities, payment responsibility, and regions.
- Verify Zomato third-party production eligibility beyond personal-use testing and its consumer authorization model.
- Verify Amazon product discovery, referral, cart, purchase handoff, and any approved consumer transaction routes.
- Verify Uber developer access for estimates, deep links, account linking, ride requests, status, cancellation, and regional availability.
- Select the first production read and write providers based on official access rather than brand preference.

### 24.2 Identity and authorization

- Evaluate replaceable federated and passwordless identity paths.
- Define host-app identity proof and key lifecycle.
- Define proposal binding, approval proof, replay protection, and expiry.
- Define connection authorization variants and external-operator custody disclosure.

### 24.3 Security and privacy

- Threat-model agents, remote integrations, prompt injection, host-app impersonation, approval forgery, credential theft, cross-context access, and administrative abuse.
- Define secret custody and rotation expectations for self-hosted deployments.
- Define audit retention, user deletion, legal holds, backups, and observability redaction.
- Classify sensitive preference and task data.

### 24.4 Open-source and operations

- Select a license with legal review.
- Define release artifacts and source-versus-secret boundaries.
- Define reference deployment support expectations.
- Define vulnerability disclosure, security updates, and integration revocation processes.

## 25. Traceability to accepted decisions

- Platform-enforced authority: ADR 0002
- Open extensions with controlled authority and handoff: ADR 0003
- Self-hostable platform and host-app identity: ADR 0004
- Host-app-isolated connections: ADR 0005
- Credential custody and host-app approvals: ADR 0006
- First release proves platform seams: ADR 0007
- Open runnable core and equal extension boundaries: ADR 0008
- Accepted global modular product model: ADR 0009

ADR 0001 and the scheduling-specific portions of the historical MVP material document an earlier narrow baseline. Their safety principles remain relevant where carried into the accepted current product direction; their scheduling-only scope is superseded.

## 26. PRD completion criteria

This PRD is ready to enter architecture design when:

- Product owner confirms the document represents the accepted global modular product.
- Each P0 requirement has an owner or target phase.
- Provider feasibility research identifies candidates for the connected read and consequential write proofs.
- Security, privacy, and legal reviewers accept the research backlog and release gates.
- Architecture work agrees to preserve the domain boundaries rather than prematurely mapping them one-to-one onto services or repositories.

The PRD is implemented only when all P0 functional requirements, applicable non-functional requirements, acceptance scenarios, first-release proof items, and release gates pass with evidence.
