# Case 8 submission implementation plan

Goal: reproducible PostgreSQL deployment and a reviewable submission package.
Architecture: retain Compose, pgvector, Celery and the current UI. Keep cloud configuration separate from local defaults. Never clean the user's database for tests; use a separate Compose project.

- [ ] Preserve narrative Markdown as one runbook; regression tests for headings and explicit If/Then rules.
- [ ] Verify database URL defaults and explicit overrides; retain local PostgreSQL fix.
- [ ] Improve Windows launcher: engine check, readiness wait and actionable failures.
- [ ] Show API/model readiness separately from monitoring on Sources.
- [ ] Add unseen author-created regression scenarios, reviewer JSON and five-minute guide. Describe benchmark limits.
- [ ] Replace machine-specific README entry; document full cloud dependencies.
- [ ] Verify video duration/content; repair outdated recording authentication.
- [ ] Run backend/browser/smoke tests in isolated data, validate clean checkout, capture results.
- [ ] Commit and push; prepare tagged release/image publishing workflow.
- [ ] Complete Amvera deployment only after access is available and full end-to-end checks pass.

User authorized implementation and publication of the audit fixes. Cloud browser access currently denied by saved origin permission; do not circumvent.
