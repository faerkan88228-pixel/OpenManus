# Prometheus OpenManus Runtime

This service runs the actual `app.agent.manus.Manus` implementation from this repository. It is intentionally deployed separately from the OmniNexus host application: both projects use a top-level Python package named `app`, so importing them into one interpreter would create module collisions.

## Start

Use Python 3.12 and install this repository's `requirements.txt`. Provide a real OpenManus `config/config.toml` through the deployment secret/mount mechanism; the example config is not a working model connection.

Set:

- `PROMETHEUS_RUNTIME_TOKEN`: long random server-to-server bearer secret.
- `OPENMANUS_DISABLE_BROWSER_USE=1`: optional, if Browser Use CLI is not installed/configured.
- Any provider-specific environment needed by your deployment. OpenManus reads its model settings from `config/config.toml`.

Start the internal service:

```bash
uvicorn app.prometheus_runtime:app --host 0.0.0.0 --port 8000
```

Expose it only behind a TLS reverse proxy or managed HTTPS ingress on public port 443. Do not expose the internal application port directly.

## API

### Health

`GET /health`

Returns the runtime identity and liveness status. It does not reveal configuration or credentials.

### Execute

`POST /v1/agent/run`

Required header: `X-Prometheus-Runtime-Token`.

Example request:

```json
{
  "goal": "Review the architecture of the connected project",
  "timeout_seconds": 180,
  "skill_contexts": [
    {
      "name": "Repository Analyst",
      "source_url": "https://github.com/example/repo/blob/main/skills/repository/SKILL.md",
      "source_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "content": "Review the repository structure and report evidence."
    }
  ]
}
```

Skill and UI context is source-attributed, size-limited, and passed as supplemental reference material. Set `kind` to `skill` or `ui` for each item. It is not allowed to override the base agent's system policy or tool/security boundaries. The runtime recomputes each Git blob SHA before accepting its content, and places repository material in a user-role reference message rather than elevating it into the base system prompt. The runtime does not install or import overlay code.

The response identifies `runtime: openmanus` and reports the number of skill documents loaded. The runtime enforces a 12-step cap and a request timeout.

## Operational boundaries

- The runtime token and model credentials remain server-side.
- Only direct HTTPS GitHub skill sources on port 443 are accepted.
- Skill source SHA values must be Git blob SHA-1 identifiers.
- Maximum 8 skill/UI documents, 12,000 characters per document, and 32,000 characters total.
- The original OpenManus tools remain the execution layer. Its in-process `python_execute` tool is disabled by default; `OPENMANUS_ENABLE_PYTHON_EXECUTION=1` is an explicit opt-in and must only be used in a dedicated, isolated worker with resource limits and restricted network egress.
- This HTTP adapter is not a substitute for sandbox hardening. Review and configure OpenManus sandbox settings before enabling code execution in a public multi-tenant environment.
