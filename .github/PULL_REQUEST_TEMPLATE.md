## Summary

One-paragraph description of the change.

## Why

The problem this solves, or the feature it adds.

## Changes

- Bullet list of substantive changes
- File by file when the diff is non-obvious

## Test plan

- [ ] `pytest --cov` passes (>= 79% line coverage).
- [ ] `ruff check .` clean.
- [ ] `ruff format --check .` clean.
- [ ] If this is a skill: passes `skillmd-lint --strict --schema`.
- [ ] If this is a new feature: covered by a test.

## Eval impact

If you measured the skill's lift on the eval harness, paste the
`--save` output or a short summary. New skills that don't move the
baseline are usually not worth merging.

## Screenshots / output

If the change is visible to users (Streamlit UI, CLI flags, etc.),
attach a screenshot or sample output.

## Related issues

Fixes #<n>, relates to #<m>, etc.

## Risk

Anything reviewers should look at carefully. Anything that might
break downstream consumers (saved skills, eval reports, the
browser playground).