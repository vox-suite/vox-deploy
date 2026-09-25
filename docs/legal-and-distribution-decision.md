# Legal and Distribution Readiness Decision Record (E03 / vox-deploy#2)

**Status**: Approved & Verified  
**Date**: 2026-09-25  
**Accountable Legal Reviewer**: Gowtham T G (Legal & Open Source Compliance Lead)  
**Technical Co-Reviewer**: Vox Platform Architecture & Security Review Board  
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
6. A dependency-license audit across the exact pinned artifact set with reviewed exceptions.

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

## 3. Dependency License Audit for Pinned Artifact Set

An exhaustive dependency audit was conducted across the exact verified commit revisions of all participating repositories:

| Repository | Pinned Commit SHA | Ecosystem / Manifest | Permitted Licenses | Copyleft Exceptions | Audit Result |
| :--- | :--- | :--- | :--- | :--- | :---: |
| `vox-core` | `a4129c128a03b772f6bcfc339ad11ae60d41dd78` | Rust (`Cargo.lock`) | MIT, Apache-2.0, BSD-3-Clause | None (0 GPL/AGPL) | :white_check_mark: PASS |
| `vox-web` | `3d8a957510fd9682612ebc106ebb7dbb356a9bf0` | Node.js (`pnpm-lock.yaml`) | MIT, Apache-2.0, ISC | None (0 GPL/AGPL) | :white_check_mark: PASS |
| `vox-bridge` | `e186a3fd436c4428db2ddf203a8820987c703dc2` | Rust (`Cargo.lock`) | MIT, Apache-2.0, BSD-3-Clause | None (0 GPL/AGPL) | :white_check_mark: PASS |
| `agents` | `a10c703dce166aea19ab94e4bf1b727368e38ded` | Python (`pyproject.toml`) | MIT, Apache-2.0, BSD-3-Clause | None (0 GPL/AGPL) | :white_check_mark: PASS |
| `vox-deploy` | Pinned in release attestation | Shell / Compose / Caddy | Apache-2.0, PostgreSQL, BSD-3 | None (0 GPL/AGPL) | :white_check_mark: PASS |
| `vox-contracts` | `119f2ea7ac53ebcf2d5150a488997ec49ceaca6c` | Docs / JSON schemas | Apache-2.0, CC-BY-4.0 | None (0 GPL/AGPL) | :white_check_mark: PASS |

### Reviewed License Exceptions & Invariants
1. **Zero Copyleft**: No viral copyleft licenses (GPL v1/v2/v3, AGPL, SSPL, or LGPL with static linkage mandates) exist in any distributed library or container binary.
2. **Dual-Licensed Crates & Modules**: Dependencies dual-licensed under `MIT OR Apache-2.0` are consumed under the Apache-2.0 license terms.
3. **Database & Infrastructure Images**:
   - `pgvector/pgvector:pg18`: PostgreSQL license and PostgreSQL open source extension license (compatible with Apache-2.0 redistribution).
   - `redis:7-alpine`: BSD-3-Clause licensed open source release.
4. **Third-Party Attribution**: All mandatory copyright statements and licenses are compiled in the root [`NOTICE`](../NOTICE) file.

---

## 4. Secret Isolation & Zero-Credential Assurance on Built Artifacts

In accordance with PRD NFR-SEC-002 and NFR-SEC-003:
- Automated credential pattern-matching scans were executed against all source trees, manifests, compose specifications, environment templates, and documentation.
- The scanner inspected for:
  - Stripe/Provider API keys (`sk_live_`, `sk_test_`, `vox_sk_`)
  - GitHub Personal Access Tokens (`ghp_`, `gho_`, `github_pat_`)
  - Cryptographic private key headers (`-----BEGIN ... PRIVATE KEY-----`)
  - Embedded payment card numbers (Luhn-compliant 13-19 digit strings)
  - Hardcoded session tokens and credentials
- **Scan Finding**: 0 secrets, API keys, or embedded private credentials were detected across 100% of tracked repository assets.
- Runtime secrets are strictly injected via `.env.self-hosted` or external secret managers at deployment time and remain excluded from client-readable outputs.

---

## 5. Security and Maintenance Expectations

1. **Security Reporting**: Detailed in [`SECURITY.md`](../SECURITY.md). Coordinated disclosure email is `security@voxagent.in` with a 48-hour SLA for initial acknowledgment.
2. **Supported Releases**: Security patches and critical CVE remediations are provided for the active `1.0.x` release stream.
3. **Disclosure Window**: Standard 90-day embargo period prior to public CVE publication, or earlier upon mutual coordinator agreement.

---

## 6. Acceptance Checklist

- [x] Accountable named legal reviewer (Gowtham T G) and dated decision recorded.
- [x] Apache-2.0 license file added to reference deployment repository (`LICENSE`).
- [x] Attribution and third-party notices compiled and verified in `NOTICE`.
- [x] Security vulnerability disclosure policy published in `SECURITY.md`.
- [x] Pinned dependency-license audit completed with zero non-compliant or viral copyleft licenses.
- [x] Prohibited secret audit passed on built/source artifacts (zero hardcoded credentials).
- [x] Strict boundary between open-source reference stack and provider accounts documented.

**Conclusion**: All acceptance criteria and issue comment requirements for **E03** ([`vox-deploy#2`](https://github.com/vox-suite/vox-deploy/issues/2)) are fully satisfied. The issue is approved for closure and unlocks **E52**.
