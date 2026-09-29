# GitHub MCP release setup

Tracking: https://github.com/vox-suite/vox-deploy/issues/19.

## Registered app

The `vox-suite` organization owns [Vox Connections](https://github.com/apps/vox-connections), registered on 2026-09-29. Its App ID is `5116898`; its public client ID is `Iv23liz7tKHVAjCoBD2W`.

- Callback: `https://app.voxagent.in/apps/oauth/callback`, without wildcards.
- Repository permissions: Contents, Issues, Pull requests and mandatory Metadata, all read-only.
- Expiring user tokens enabled; device flow and webhook delivery disabled.
- Any account can install; each account must authorize installation and select repositories. Registration itself grants no repository access.

## Credentials and Core configuration

An organization administrator generates the OAuth client secret and the private key in [App settings](https://github.com/organizations/vox-suite/settings/apps/vox-connections). GitHub requires a private key before installation. Keep that key in protected operator custody; the current Core user OAuth flow uses the client secret and does not consume the private key. Never paste either credential into an issue, PR, chat, or log.

Set `VOX_MCP_OAUTH_CLIENTS` in the server's root-owned mode-0600 `/etc/vox.local.env`, or as a Google Secret Manager secret consumed by the existing `sync-secrets-from-gsm` workflow. Preserve other provider entries and the existing `VOX_CREDENTIAL_KEY`. Use hidden input or a secure editor; never put a real secret into shell arguments. The JSON structure is:

```json
{
  "api.githubcopilot.com": {
    "issuer": "https://github.com/login/oauth",
    "client_id": "Iv23liz7tKHVAjCoBD2W",
    "client_secret": "REPLACE_IN_SECRET_STORE_ONLY",
    "token_endpoint_auth_method": "client_secret_post",
    "scopes": [],
    "send_resource": true
  }
}
```

Do not install the example placeholder. The Core revision must pin Connections' explicit token authentication support. GitHub's documented token exchange sends client credentials in the form; [GitHub App user tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app) use app permissions rather than OAuth scopes. Do not add `repo` scopes. Vox sends PKCE and the challenged MCP resource; test provider acceptance before release.

Confirm `VOX_CREDENTIAL_KEY` is set, backed up, and retained across service recreation. Keep the callback in `VOX_MCP_OAUTH_REDIRECT_URIS`; Vox Web must use the same callback. Syncing a secret file does not change an existing container's environment: recreate the Core service through the normal deployment procedure, then verify health and configured-provider availability without displaying secret values.

### Transfer through the deployment service account

When the operator's interactive Google account lacks project access, the manual `configure-github-oauth` workflow can use the existing deployment service account. Supply the already-generated App client secret as the encrypted repository secret `VOX_GITHUB_OAUTH_CLIENT_SECRET` in `vox-suite/vox-deploy`, then dispatch the workflow. It validates the input, preserves other provider entries, and writes a new `VOX_MCP_OAUTH_CLIENTS` version through standard input. A missing secret is created only after an explicit not-found response; access failures and unreadable or malformed existing configuration stop the operation. An identical configuration adds no version.

After a successful transfer, remove the temporary encrypted GitHub secret, run `sync-secrets-from-gsm`, and deploy/recreate Core. On failure retain the transfer secret until the failure is resolved. This workflow configures the reference deployment's registered App; it grants no new IAM roles or repository access and does not publish a connector package.

### Direct VM configuration

Google Secret Manager is optional. For the reference VM, dispatch `configure-github-oauth-vm` with `apply=false` to inspect configuration presence and database authentication. With approval to store the App secret on that VM, dispatch with `apply=true`. The workflow uses the existing encrypted GitHub transfer secret and SSH deployment credential, verifies the pinned reference VM host key, and passes the App secret only through encrypted SSH stdin. It atomically updates root-owned mode-0600 `/etc/vox.local.env`, preserves the encryption key and effective provider configuration, and refuses malformed, duplicate, or insecure configuration. It does not rotate credentials or restart services. Remove the temporary GitHub transfer secret after successful storage, and activate through the tested release procedure. This protected local file survives GSM synchronization.

Inspection also tests the encrypted production `DATABASE_URL`, when supplied, against the same database target with a fresh client and `SELECT 1`. It reports only whether it matches the VM and whether authentication succeeds; it does not update the database setting. The client verifies TLS and hostname. For Supabase it loads the vendor CA identified by Supabase's official Studio configuration into a temporary, client-scoped certificate file and removes it after the probe; it does not modify system trust or disable certificate verification. A successful existing API health response alone is insufficient evidence that a newly started worker can authenticate.

### Recover a reset database password

After the administrator completes the Supabase password reset, transfer the approved new password through SSH stdin to `sudo -n python3 -B configure-vm-database.py --apply`, with the helper scripts staged in a private temporary directory. Never enter it as a command argument or paste it into a log. This reference-only helper preserves the database host, user, port, database name and query settings, percent-encodes password characters, and verifies a fresh TLS-authenticated `SELECT 1` before changing `/etc/vox.local.env`. The same protected atomic update and file lock used for OAuth preserve unrelated settings, including `VOX_CREDENTIAL_KEY`. Failed authentication, insecure files, duplicate entries, or concurrent changes stop the update.

With approval for that destination, synchronize the resulting `DATABASE_URL` into the encrypted `production` GitHub Actions secret via stdin, without printing it. Keep the local override: it survives GSM sync while the Google service account is unavailable. Recreate Core through the release procedure and verify both API readiness and sustained worker operation; storing a password alone does not activate it in existing containers.

## Live acceptance

1. Choose a non-production test repository and obtain explicit approval to install the app for that repository. Avoid selecting all repositories for the test.
2. Publish and promote a reviewed immutable package for `https://api.githubcopilot.com/mcp/x/repos/readonly`. Pin protocol and exact read tool schemas; declare recipients and effects. A read-only endpoint does not independently restrict a stolen token.
3. From Vox Library, install that package, complete the actual browser OAuth flow, and grant one reviewed read to one selected agent. Execute that read and record redacted evidence.
4. Prove a second agent and a different user context cannot use the connection. Verify expiry, refresh rotation, revocation, endpoint/schema drift, and package withdrawal remove readiness or prevent dispatch.
5. Record package digest, Core/Web versions, tested tool inventory, and live evidence in the tracking issue. Protocol reachability and local fixture tests alone do not satisfy this gate.

## Reference deployment status (2026-09-29)

The App client secret is stored in the reference VM's protected local configuration, and the temporary encrypted GitHub Actions transfer secret has been removed. The database password reset was verified with a fresh TLS `verify-full` connection. [Release run 36538449960](https://github.com/vox-suite/vox-deploy/actions/runs/36538449960) deployed Core `4bd3a9fcf8181fc8a5f9f83114363f2118c1f7bb` and Bridge `5e1449675e0a490d3604606b47efdcdd23d90184`; Core and Bridge readiness, public API health, and a later zero-restart check across all five containers passed. The Bridge host credential is root-owned mode 0600 in `/etc/vox.bridge.env`.

A subsequent September 29 check found the worker restarting with database error `28P01`; a fresh connection using the protected VM setting and Supabase's CA also rejected the password. The earlier successful release is historical evidence, not current database readiness. Deployment remains blocked until the configured password authenticates again. Apple Passwords was locked during that check. No password or stored credential was changed. The release script now observes worker status and restart count for 30 seconds before committing a release; an exit or restart triggers recovery. This checks startup stability, not ongoing availability, so later credential changes still require operational monitoring.

The GitHub App private key was generated but its PEM file was not retained by the operator. The test-repository installation, package conformance, and complete live Vox journey above remain unverified. The candidate package is intentionally unpublished and must not be presented as a ready default integration. The separate Google Secret Manager service account still returns `invalid_grant`; this VM release does not use it.
