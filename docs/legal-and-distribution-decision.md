# Legal and Distribution Readiness Decision Record (E03 / vox-deploy#2)

**Status**: Approved & Closed  
**Date**: 2026-09-24  
**Accountable Owner**: Vox Platform Architecture & Legal Review  
**Governing Issue**: [`vox-suite/vox-deploy#2`](https://github.com/vox-suite/vox-deploy/issues/2) (**E03**)  
**Unlocks**: [`vox-suite/vox-deploy#3`](https://github.com/vox-suite/vox-deploy/issues/3) (**E52**)

---

## 1. Context and Objective

In accordance with PRD Section 11.21 (**Open-Source Distribution**, FR-OSS-001 through FR-OSS-008) and Architecture Decision Record **ADR 0008** (*Open runnable core with equal extension boundaries*), Platform V1 requires an accountable legal and product decision establishing:
1. The chosen open-source license and third-party notices.
2. The strict boundary between open self-hostable components and separately distributed provider integrations.
3. Verification that published artifacts contain zero provider or deployment secrets.
4. Documented security vulnerability disclosure and supported release policies.
5. Clarification that self-hosting confers no commercial partnerships or provider credentials.

---

## 2. Decision and Scope Boundaries

### 2.1 License Selection: Apache License 2.0
The entire runnable self-hostable reference stack (`vox-core`, `vox-web`, `vox-bridge`, `vox-deploy`, and `agents`) is published under the **Apache License, Version 2.0** (`LICENSE`).

**Rationale**:
- Grants permissive commercial and non-commercial use, modification, and redistribution.
- Provides explicit patent grant and retaliation protections (Section 3).
- Explicitly reserves trademark and brand rights (Section 6), ensuring external forks cannot misrepresent themselves as the official Vox service.
- Compatible with all foundational dependencies across Rust, Node.js/TypeScript, and Python ecosystems.

### 2.2 Boundary Between Open and Separately Distributed Components
- **In-Scope Open Components**:
  - `vox-core`: Platform coordination, state machine, durable task engine, identity context resolution, proposal generation, policy enforcement, audit trails, and privacy/retention engines.
  - `vox-web`: Modern consumer web host and portal, standalone authentication (OAuth + email OTP), and privacy controls.
  - `vox-bridge`: Voice (Twilio/LiveKit) and messaging (WhatsApp/SMS) channel ingress gateway.
  - `vox-deploy`: Docker Compose orchestrator, Caddy reverse proxy, automated backup/restore scripts, and deployment verification tools.
  - `agents`: Model-neutral portable agent package delegating authority to Core.
  - `conformance-sandbox`: Hermetic, deterministic sandbox for testing provider integrations and fault scenarios without live external accounts.
- **Out-of-Scope / Separately Governed Elements**:
  - **Provider Credentials**: Self-hosting confers no API keys, accounts, or carrier numbers for third-party services (Twilio, Amazon, Google Maps, Exa, AssemblyAI, Sarvam, Uber, Expedia). Operators must supply their own legitimate API credentials.
  - **Commercial Partnerships**: Self-hosting does not grant any special status, quota, or bypass of external provider terms of service.
  - **Proprietary Integrations**: Any separately distributed remote extensions run strictly behind public platform boundaries, subject to user consent, capability grants, and policy checks. They receive zero elevated privileges (FR-OSS-007).

---

## 3. Dependency License Audit

An automated dependency scan was conducted across all participating repository package manifests:

| Repository | Ecosystem / Manifest | Primary Licenses | Permitted / Compatible |
| :--- | :--- | :--- | :---: |
| `vox-core` | Rust (`Cargo.toml`) | MIT, Apache-2.0, BSD-3-Clause | :white_check_mark: YES |
| `vox-web` | Node.js (`package.json`) | MIT, Apache-2.0, ISC | :white_check_mark: YES |
| `vox-bridge` | Rust (`Cargo.toml`) | MIT, Apache-2.0, BSD-3-Clause | :white_check_mark: YES |
| `agents` | Python (`pyproject.toml`) | MIT, Apache-2.0, BSD-3-Clause | :white_check_mark: YES |
| `vox-deploy` | Shell / Compose / Caddy | Apache-2.0, PostgreSQL, BSD-3 | :white_check_mark: YES |

**Findings**:
- Zero viral copyleft (GPL / AGPL) dependencies exist in the distributable libraries or service binaries.
- All transitive dependencies allow static linking and container packaging under Apache-2.0 terms.
- Attribution notices for all third-party projects are compiled in the root [`NOTICE`](../NOTICE) file.

---

## 4. Secret Isolation & Zero-Credential Assurance

In accordance with PRD NFR-SEC-002 and NFR-SEC-003:
- Automated pattern matching checks (live API keys, GitHub tokens, private keys) pass across all tracked repository files.
- Runtime secrets are loaded exclusively via environment variables (`.env.self-hosted`) or external secret managers (Google Secret Manager / Vault).
- `.env.self-hosted.example` contains only redacted placeholders.
- Git repositories ignore all `.env*` files with real credentials.

---

## 5. Security and Maintenance Expectations

1. **Security Reporting**: Detailed in [`SECURITY.md`](../SECURITY.md). Coordinated disclosure email is `security@voxagent.in` with a 48-hour SLA for initial acknowledgment.
2. **Supported Releases**: Security patches are maintained for the active `1.0.x` release stream.
3. **Disclosure Window**: Standard 90-day embargo period prior to public CVE publication, or earlier upon mutual coordinator agreement.

---

## 6. Acceptance Checklist

- [x] Apache-2.0 license file added to reference deployment repository (`LICENSE`).
- [x] Attribution and third-party notices compiled in `NOTICE`.
- [x] Security vulnerability disclosure policy published in `SECURITY.md`.
- [x] Dependency license scan completed with zero non-compliant licenses.
- [x] Prohibited secret audit passed (zero hardcoded credentials).
- [x] Boundary between open-source reference stack and provider accounts documented.

**Conclusion**: All acceptance criteria for **E03** ([`vox-deploy#2`](https://github.com/vox-suite/vox-deploy/issues/2)) are completely satisfied. The issue is unblocked for closure and unlocks **E52**.
