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

Set `VOX_MCP_OAUTH_CLIENTS` as a protected Railway variable on Core API and worker only. For standalone Compose, use a root-owned mode-0600 protected environment file. Preserve other provider entries and the existing `VOX_CREDENTIAL_KEY`. Use hidden input or a secure editor; never put a real secret into shell arguments. The JSON structure is:

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

Confirm `VOX_CREDENTIAL_KEY` is set, backed up, and retained across service recreation. Keep the callback in `VOX_MCP_OAUTH_REDIRECT_URIS`; Vox Web must use the same callback. Changing stored configuration does not prove it is active: redeploy the affected Core services, then verify readiness and configured-provider availability without displaying secret values.

### Railway credential custody

The operator approved transferring the existing encryption key and GitHub client configuration from protected prior VM storage into Railway Core API and worker. That transfer remains pending; do not regenerate the key or infer completion from approval. Use only the approved protected destinations and preserve unrelated provider configuration. Never expose values in logs, issues, source control or command arguments.

VM/GSM GitHub Actions entry points have been retired. Prior VM recovery evidence below is historical and does not establish Railway readiness. Do not reset the database password or run VM release commands as part of the Railway cutover.

## Live acceptance

1. Choose a non-production test repository and obtain explicit approval to install the app for that repository. Avoid selecting all repositories for the test.
2. Publish and promote a reviewed immutable package for `https://api.githubcopilot.com/mcp/x/repos/readonly`. Pin protocol and exact read tool schemas; declare recipients and effects. A read-only endpoint does not independently restrict a stolen token.
3. From Vox Library, install that package, complete the actual browser OAuth flow, and grant one reviewed read to one selected agent. Execute that read and record redacted evidence.
4. Prove a second agent and a different user context cannot use the connection. Verify expiry, refresh rotation, revocation, endpoint/schema drift, and package withdrawal remove readiness or prevent dispatch.
5. Record package digest, Core/Web versions, tested tool inventory, and live evidence in the tracking issue. Protocol reachability and local fixture tests alone do not satisfy this gate.

## Historical VM evidence (2026-09-29)

The App client secret is stored in the reference VM's protected local configuration, and the temporary encrypted GitHub Actions transfer secret has been removed. After the operator reset and saved the database password, a fresh TLS `verify-full` login succeeded before the protected VM configuration was updated. The verified database URL was synchronized into the encrypted production GitHub Actions secret. [Read-only verification run 36574193728](https://github.com/vox-suite/vox-deploy/actions/runs/36574193728) confirmed that the two settings match and authenticate; the credential encryption key and OAuth clients remain configured.

[Release run 36573718858](https://github.com/vox-suite/vox-deploy/actions/runs/36573718858) deployed Core `861b8c75a09221b9984e41e15713fa27be2080d6` and Bridge `5e1449675e0a490d3604606b47efdcdd23d90184` using their previously built images. The VM records those exact commits. Local Core and Bridge readiness, public API health, and two subsequent checks of all five running containers with zero restarts passed. Default publication completed for six reviewed skills in each of three deployments. The local configuration and Bridge host credential files are root-owned mode 0600.

The earlier worker restart loop and fresh-login error `28P01` are resolved by the verified credential recovery above. The release script observes worker status and restart count for 30 seconds before committing a release; an exit or restart triggers recovery. This checks startup stability, not ongoing availability, so later credential changes still require operational monitoring.

The GitHub App private key was generated but its PEM file was not retained by the operator. The test-repository installation, package conformance, and complete live Vox journey above remain unverified. A fresh Chrome reload blocks `app.voxagent.in` with `ERR_BLOCKED_BY_CLIENT`, preventing interactive consent testing in that browser. The candidate package is intentionally unpublished and must not be presented as a ready default integration. The separate Google Secret Manager service account still returns `invalid_grant`; this VM release does not use it.
