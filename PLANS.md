# Global PR infographic enforcement

Summary: one validator in pr-gate serves all repositories where the operator has maintenance access. Repository callers pin its commit. Existing merge rules remain intact.

1. Capture accessible repositories and current enforcement gaps.
2. Test the validator against missing, forged, stale, and valid image references.
3. Publish one reusable workflow that reads current PR data without executing contributor code.
4. Provide an idempotent fleet installer and coverage report. Open adoption PRs against each default branch.
5. Require the observed check only after the workflow reaches the default branch and posts successfully. Record unsupported plans and permissions explicitly.
6. Verify the current coverage from GitHub. Never label an open adoption PR as enforced.
