# Case 8 submission implementation plan

Goal: reproducible PostgreSQL deployment and a reviewable submission package.
Architecture: retain Compose, pgvector, Celery and the current UI. Keep cloud configuration separate from local defaults. Never clean the user's database for tests; use a separate Compose project.

- [x] Preserve narrative Markdown as one runbook; regression tests for headings and explicit If/Then rules.
- [x] Verify database URL defaults and explicit overrides; retain local PostgreSQL fix.
- [x] Improve Windows launcher: engine check, readiness wait and actionable failures.
- [x] Show API/model readiness separately from monitoring on Sources.
- [x] Add unseen author-created regression scenarios, reviewer JSON and five-minute guide. Describe benchmark limits.
- [x] Replace machine-specific README entry; document full cloud dependencies.
- [x] Verify video duration/content; repair outdated recording authentication.
- [x] Run backend/browser/smoke tests in isolated data, validate clean checkout, capture results.
- [x] Commit and push; prepare tagged release/image publishing workflow.
- [ ] Complete Amvera deployment only after access is available and full end-to-end checks pass.

User authorized implementation and publication of the audit fixes. Cloud browser access currently denied by saved origin permission; do not circumvent.

Cloud blocker: two origin-gate denials despite user-visible Always allow. No workaround attempted. Additional finding: remove fabricated monitoring fallback (test first, then implementation).
