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

## Stacked pull request gate

### Summary

Use GitHub native stacks. GitHub evaluates every layer against the stack trunk, so the existing default-branch `pr-gate` ruleset covers the whole chain. Do not put required status checks on feature branches, because GitHub also enforces them before branch updates.

### Milestones

- [x] Prove that `pr-gate-stacked` rejects a new commit before its `gate` check can run.
- [x] Delete the active `pr-gate-stacked` ruleset from `komaksym/prc`.
- [x] Document native stacks and the bottom-to-top `gh stack link` command.
- [ ] Link existing PRC chains after each chain has a bottom pull request against `main`.
