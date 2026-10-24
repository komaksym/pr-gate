# pr-gate

One required check, `gate`, for every repository.

## What runs

`checks.yml` is a reusable workflow. It runs these jobs in parallel:

- `test` runs `npm ci`, then your command (default `npm run lint && npm run verify`). It fails when the command changes tracked files, so a stale committed build fails.
- `title` requires a Conventional Commits PR title. It reads the current title, so a re-run picks up an edit.
- `actionlint` and `zizmor` check workflow files.
- `secrets` runs trufflehog on the diff.

Each repository adds its own jobs, such as end-to-end tests, and one `gate` job that needs all of them.

## Adopt it

Add `.github/workflows/pr.yml`:

```yaml
name: pr

on:
  pull_request:
  push:
    branches: [main]

permissions: {}

concurrency:
  group: pr-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true

jobs:
  checks:
    uses: komaksym/pr-gate/.github/workflows/checks.yml@<commit sha> # v1
    permissions:
      contents: read
      pull-requests: read

  gate:
    if: always()
    needs: [checks]
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions: {}
    steps:
      - if: contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled')
        run: exit 1
      - run: echo gate passed
```

Add every repository job to `needs`. Pin the commit SHA. Dependabot updates the pin.

Then run `./apply-ruleset.sh OWNER/REPO`. It creates or updates the `pr-gate` ruleset on the default branch:

- require `gate` from GitHub Actions
- branches need not be up to date
- squash merges only
- review threads must be resolved

The script lists other active rulesets. Disable any that still require old checks.

## Rules that keep the gate honest

- `gate` uses `if: always()`. Without it, a failed job skips `gate`, and GitHub treats a skipped check as passing.
- Never path-filter `pr.yml`. A skipped workflow leaves `gate` pending, and the merge blocks.
- Skip slow work with a job-level `if:`. A job skipped that way reports success.
- Never make a review bot's check required. See [REVIEW.md](REVIEW.md).

## Limits

- Rulesets apply to private repositories only on GitHub Pro, Team, or Enterprise Cloud.
- Merge queue needs a public repository owned by an organization. Add a `merge_group` trigger to `pr.yml` if you enable it.
