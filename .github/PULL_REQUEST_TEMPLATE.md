## Summary

<!-- 1–3 bullet points: what changed and why -->

-
-

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor
- [ ] Documentation
- [ ] Dependency update
- [ ] CI / infrastructure

## Test Plan

<!-- How did you test this? What cases did you cover? -->

-

## Checklist

- [ ] `make lint` passes (ruff + mypy + eslint)
- [ ] `make test` passes with no regressions
- [ ] New API endpoints have at least one integration test
- [ ] New env vars added to `.env.example`
- [ ] DB model changes include an Alembic migration
- [ ] No secrets or `.env` content committed
- [ ] `EMBEDDING_DIMENSION` unchanged (or migration + re-index planned)
- [ ] Security checklist in `SECURITY.md` reviewed for auth/file/LLM changes

## Breaking Changes

<!-- Describe any breaking changes to the API, DB schema, or env vars -->

None / <description>

## Related Issues

Closes #
