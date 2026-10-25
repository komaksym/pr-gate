# Add optional Codecov enforcement

## Summary

Support a required `codecov/patch` check for repositories that upload coverage. Preserve the default gate-only ruleset for repositories without coverage. Refuse activation until a genuine Codecov status is visible.

## Milestones

- [x] Test the real apply command with an isolated fake GitHub API before implementation.
- [x] Implement guarded opt-in enforcement and document its prerequisites.
- [x] Verify default and opt-in behavior. The parent owns the PR.
- [ ] Apply the proven policy to music-saver and prc after each emits a real Codecov status. The parent owns live changes.

## Throughput checkpoint

- Blocking first steps. Read the existing apply command and active rulesets.
- Independent workstreams. This checkout owns shared ruleset support. PRC coverage uses its own checkout.
- Shared mutable state. Only the parent writes live repository rulesets.
- Smallest safe decomposition. Keep the default ruleset unchanged and add one explicit Codecov option.
