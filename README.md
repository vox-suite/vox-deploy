# Vox Deploy

The active backend runs in [Railway project vox](https://railway.com/project/00945ffa-7a84-4615-87e1-f37022b106ce): Core API, Core worker, Bridge, Redis and Caddy. Vox Web runs on Vercel; PostgreSQL remains external.

## Railway releases

Core API and worker deploy from `vox-suite/vox-core`; Bridge deploys from `vox-suite/vox-bridge`. Railway owns the runtime deployment. This repository provides release verification, documentation and supported self-hosting; it no longer provides VM or Google Secret Manager GitHub Actions workflows.

See [deployment topology, current evidence and remaining gates](docs/railway-deployment.md). Require successful component CI and service readiness before accepting a release. Preserve the exact source revisions and sanitized verification evidence. Database migrations are not undone by a Railway rollback: verify compatibility before reverting a binary.

## Connector configuration

For self-hosting, place connection variables in the optional Core-only `.env.connections` file using `.env.connections.example`; for production Compose use the protected Core override. Keep `VOX_CREDENTIAL_KEY`, `GOOGLE_CLIENT_ID`, and `GOOGLE_CLIENT_SECRET` restricted to Core API and worker. Preserve the existing encryption key and other provider entries during migration. Replacing or losing the key makes existing connected-account tokens unreadable. Back it up with the database in protected operator custody.

See [GitHub MCP setup](docs/github-mcp-setup.md) for the registered App, callback, credential configuration and live acceptance gates. Deployment or account linking alone does not certify an integration.

## Self-hosting

See [self-hosting](docs/self-hosting.md) for the supported Compose distribution. The remaining protected-file helpers support standalone operation and recovery. They are not Railway release commands. Keep prior protected credentials and backups until cutover is verified; workflow retirement does not delete or rotate them.

## Local verification

```sh
bash tests/run.sh
```

The only GitHub workflow in this repository validates pull requests and `main`. Hosted releases are managed in Railway.

## Library defaults

`vox-core-defaults` publishes six curated declarative skills by immutable content digest after migrations. Publication does not install or enable them for agents. Operator registration also seeds defaults for a new deployment. Core's `Cargo.lock` pins Connections and Shared revisions. Service apps remain unpublished until provider configuration and live acceptance evidence exist.

Connected Apps use a configured `VOX_CORE_API_URL` Google callback and the Core worker. No standalone Connections daemon or consumer web app is deployed. Vox-web hosts the public website. Real account linking and sync on desktop and Android are mandatory release gates.
