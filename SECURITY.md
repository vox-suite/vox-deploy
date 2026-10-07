# Security Policy

## Supported Versions

The Vox project maintains security updates for the current major release line.

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

The Vox security team takes all security vulnerabilities seriously. We ask that all vulnerabilities be reported responsibly and privately.

### How to Report
Please do **NOT** report security vulnerabilities through public GitHub issues.

Instead, please report potential security vulnerabilities to:
- **Email**: `rahul.id39@gmail.com`
- **PGP Key**: Fingerprint available on official project security advisory page.

### What to Include
When reporting a vulnerability, please provide:
1. Description of the vulnerability and affected components (`vox-core`, `vox-web`, `vox-bridge`, `vox-deploy`, `agents`).
2. Exact steps to reproduce the vulnerability (proof of concept or exploit script).
3. The potential impact of the issue (e.g., identity impersonation, unauthorized action execution, credential leakage).
4. Any proposed remediations if available.

### Disclosure Process
- **Initial Response**: Within 48 hours, an acknowledgment and triage assessment will be provided.
- **Remediation**: If confirmed, a security patch will be developed in a private advisory workspace.
- **Public Disclosure**: A standard 90-day coordinated disclosure policy is followed, or earlier upon mutual agreement once patch verification and backports are published.
- **Credit**: We will publicly credit the reporter in the release notes and advisory unless requested otherwise.

## Security Architecture Principles
The Vox Platform adheres strictly to:
1. **Fail-Closed on Uncertainty**: When authentication, connection, grant, or policy cannot be verified, execution is denied.
2. **Secret Isolation**: Secrets are never placed in client-readable configurations, logs, traces, exports, or AI model prompts.
3. **Non-Action Authority**: Reminders, notifications, and preferences confer zero authority to execute consequential actions.
4. **Exact Action Approval**: Proposals require exact-match confirmation and are single-use; details cannot be altered post-approval.
