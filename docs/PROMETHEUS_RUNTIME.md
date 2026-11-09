# Prometheus OpenManus Runtime

This service runs the actual `app.agent.manus.Manus` implementation from this repository. It is intentionally deployed separately from the OmniNexus host application: both projects use a top-level Python package named `app`, so importing them into one interpreter would create module collisions.

## Start

Use Python 3.12 and install this repository's `requirements.txt`. Provide a real OpenManus `config/config.toml` through the deployment secret/mount mechanism; the example config is not a working model connection.

Set:

- `PROMETHEUS_RUNTIME_TOKEN`: long random server-to-server bearer secret.
OpenManus MCP servers remain governed by the base OpenManus configuration; keep them disabled unless the required server commands and permissions are deliberately configured.
- Any provider-specific environment needed by your deployment. OpenManus reads its model settings from `config/config.toml`.

Build the runtime image:

```bash
docker build -f Dockerfile.prometheus-runtime -t prometheus-openmanus-runtime .
```

Run it in an isolated worker. Supply the real config file and token through your deployment secret manager; do not bake them into the image:

```bash
docker run --rm \
  --read-only \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --pids-limit=128 \
  --memory=4g \
  --cpus=2 \
  --tmpfs /tmp:rw,noexec,nosuid,size=256m \
  --tmpfs /srv/openmanus/workspace:rw,nosuid,nodev,size=1g,uid=10001,gid=10001 \
  --tmpfs /srv/openmanus/logs:rw,nosuid,nodev,size=128m,uid=10001,gid=10001 \
  -p 127.0.0.1:8000:8000 \
  -v /secure/config.toml:/srv/openmanus/config/config.toml:ro \
  -e PROMETHEUS_RUNTIME_TOKEN \
  prometheus-openmanus-runtime
```

Expose it only behind a TLS reverse proxy or managed HTTPS ingress on public port 443. Keep the worker private; do not expose port 8000 directly. Apply outbound network restrictions to only the configured model provider and explicitly approved services.

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
