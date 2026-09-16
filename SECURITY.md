# Security policy

## Supported versions

| Version | Supported          |
|---------|--------------------|
| 0.2.x   | ✅ active          |
| 0.1.x   | ⚠️ best-effort     |
| < 0.1   | ❌ unsupported     |

## Threat model

LLM Skill Factory is a **single-tenant authoring tool** for `SKILL.md` files.
It is intended to be run by a trusted user (locally, in a Docker container, or
behind your own auth layer in production). Out of the box it does not provide
authentication, authorisation, or rate-limiting for HTTP clients.

In scope:

- Defending against accidental / malicious input that would compromise the
  LLM prompt (size caps, path traversal, reserved slugs).
- Hardening outbound calls to LLM providers against transient network errors
  (retries, timeouts) without amplifying load.
- Defending the host filesystem against path-traversal in preset names and
  skill slugs.

Out of scope:

- Multi-user authentication / authorisation (use a reverse proxy).
- Sandboxing generated `SKILL.md` content — these are plain text; downstream
  consumers are responsible for evaluating any prompt-injection risk in their
  own system.

## Hardening applied in 0.2.0

- `skill_factory.safety` enforces hard size caps on reference text
  (`SF_MAX_REF_TEXT_BYTES`, default 200 KB) and uploads
  (`SF_MAX_UPLOAD_BYTES`, default 5 MB). Override per deployment if needed.
- `skill_factory.safety.RESERVED_SLUGS` blocks Windows device names, `.`,
  `..`, `~`, and the empty string. Combined with the validator's kebab-case
  regex this prevents accidental folder shadowing.
- `LLMClient` validates that `api_key` and `base_url` are non-empty and that
  `timeout` is positive.
- `requests` is pinned at `>=2.32` for the latest proxy-auth and TLS fixes.
- The Streamlit app does not persist API keys to disk; session-only state.

## Reporting a vulnerability

**Please do not file a public GitHub issue for security problems.**

Email `security@example.invalid` (replace with the maintainer's contact) with:

- A short description of the issue.
- Reproduction steps / PoC.
- Impact assessment (what an attacker could achieve).

You should receive an acknowledgement within 72 hours. We aim to ship a fix
or a mitigation within 14 days for confirmed high-severity issues.

## Acknowledgements

We follow responsible-disclosure norms and will credit reporters (with their
permission) in release notes.
