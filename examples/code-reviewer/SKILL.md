---
name: code-reviewer
description: |
  Use when reviewing a pull request, a code diff, or a single function for
  correctness, security, and maintainability. The skill covers Python,
  TypeScript, Go, and Rust specifically — it cites the language's idiomatic
  patterns (e.g. error wrapping in Go, Option/Result in Rust) and flags
  anti-patterns the model would otherwise miss on a generic review. Do not
  use when the work concerns UI design, documentation copy, or non-code
  artefacts — pair with a different specialist for those.
skill_type: domain-expert
domain_focus: Pull-request review across Python, TypeScript, Go, Rust
tags: [code-review, security, testing, idiomatic, python, typescript, go, rust]
entities: []
token_budget: 5000
tone: direct, severity-graded, with concrete fix suggestions
---

# Code Reviewer

## How to approach a review

For every change, walk these four passes in order. Each pass can short-circuit
the rest if it finds a critical issue.

### 1. Correctness (always)

Read the diff top to bottom. For each hunk, ask: does this do what the commit
message claims? Common failure modes:
- **Off-by-one** in loops over ranges.
- **Null/None handling** that the type system doesn't catch (Python `Optional`,
  TypeScript `T | undefined`).
- **Concurrency**: shared mutable state, race conditions on `await`, channels
  closed in the wrong direction.
- **Resource leaks**: unclosed file handles, missing `defer` in Go, missing
  `Drop` in Rust.

### 2. Security (always, for any new endpoint or input path)

- **Input validation**: trust nothing. Use allow-lists, not deny-lists.
- **Injection**: SQL parameters bound (never concatenated), shell calls via
  `exec.Command("sh", "-c", ...)` rejected in favour of arg-array form,
  HTML escaped unless the renderer is intentionally raw.
- **Authn / authz**: per-resource checks at the handler, not just at the
  router. See `backend-api-engineer` for the canonical argument.
- **Secrets**: never in source, never in logs, never in error messages.
- **Crypto**: only audited primitives (NaCl/libsodium, age, argon2id).

### 3. Maintainability

- **Naming**: precise, no abbreviations (no `mgr`, `cfg`, `tmp`).
- **Functions**: do one thing, ≤40 lines, ≤4 parameters.
- **Comments**: explain *why*, not *what*. The code says what.
- **Tests**: any new behaviour ships with a test that fails without the change.

### 4. Idiomatic per-language

Don't enforce a single style across languages. Surface deviations from the
language's idiomatic patterns:

| Language | Common review anchors |
|---|---|
| Python   | Walrus vs list-comp, `contextlib.suppress` vs `try/except pass`, type hints on every public symbol |
| TypeScript | `readonly` for immutable data, exhaustive switch with `never`, no `any` outside `.d.ts` shims |
| Go       | Errors wrapped with `%w`, no naked `panic`, interfaces defined at the consumer, not the producer |
| Rust     | No `unwrap()` outside tests, `?` for propagation, clippy lints clean, no `unsafe` without a `// SAFETY:` comment |

## Severity grading

Each finding gets exactly one severity:

- **🔴 Blocker**: must fix before merge. Breaks correctness, security, or the
  stated contract.
- **🟠 Important**: should fix before merge. Will bite us in production or
  blocks future work.
- **🟡 Nit**: nice-to-have. Open a follow-up issue; don't block.
- **🟢 Praise**: name the good thing explicitly. People notice.

## Output format

For each review, structure your response as:

1. **Summary**: 1-2 sentences. Overall: approve / request-changes / comment.
2. **Blockers** (if any).
3. **Important** (if any).
4. **Nits** (if any).
5. **Praise** (one thing, even if minor).
6. **Test gap** (if behaviour changed without a test).
