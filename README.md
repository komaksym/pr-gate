# pr-gate

One required check, `gate`, for every repository.

## PR infographic policy for every maintained repository

The shared `pr-visual.yml` workflow validates current PR descriptions and PNG bytes at the PR head. It never checks out contributor code. Body edits trigger the caller, and re-runs fetch the latest description. Bots and forks use the same policy. An image URL alone is insufficient. The file must exist on the head branch or commit and contain a PNG signature.

Run the fleet installer with a full published pr-gate commit and a generated infographic:

```sh
python3 adopt-pr-visual.py --pin COMMIT_SHA --image infographic.png --report /tmp/pr-visual-coverage.jsonl
python3 adopt-pr-visual.py --pin COMMIT_SHA --image infographic.png --report /tmp/pr-visual-coverage.jsonl --apply
```

With no `--repo`, it enumerates all repositories where the authenticated account has admin or maintain access, including forks and private repositories. Archived repositories are reported as read-only. `--repo OWNER/REPO` limits the operation. Existing files and branches are checked before writing, making repeat runs safe.

Every adoption PR includes a caller pinned to the shared commit and an infographic. Merge adoption PRs through normal review. Then run again with `--apply --arm`. Arming requires the caller on the default branch and a successful GitHub Actions visual check. The installer adds a separate `pr-infographic` ruleset, preserving existing checks. Unsupported plans and access failures remain explicit coverage gaps. No repository changes visibility or billing.

GitHub has no personal-account setting that installs this workflow on future repositories automatically. Run the same installer during repository creation and periodically to detect new maintained repositories. An open adoption PR is pending coverage, never enforced coverage.

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
    types: [opened, synchronize, reopened]
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

Skip `edited`. A description edit would rerun every job and cancel the run in progress. The `title` job reads the live title, so after you fix a title, re-run that job.

For a repository without npm, pass `run: ''` to skip the `test` job, and add your own test job to `needs`:

```yaml
  checks:
    uses: komaksym/pr-gate/.github/workflows/checks.yml@<commit sha> # v1
    with:
      run: ''
    permissions:
      contents: read
      pull-requests: read

  test:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@<commit sha> # v4
        with:
          persist-credentials: false
      - run: <your test command>

  gate:
    if: always()
    needs: [checks, test]
    # same steps as above
```

Then run `./apply-ruleset.sh OWNER/REPO`. It creates or updates the `pr-gate` ruleset on the default branch:

- require `gate` from GitHub Actions
- branches need not be up to date
- squash merges only
- review threads must be resolved

The script lists other active rulesets. Disable any that still require old checks.

### Enforce checks on stacked pull requests

Use a GitHub stack. GitHub evaluates required reviews, status checks, CODEOWNERS, and Actions for every stack layer against the stack trunk. When the trunk is the default branch, the `pr-gate` ruleset on that branch requires `gate` for every layer. For a stack rooted at another branch, apply an equivalent ruleset to that trunk.

Create a stack with `gh stack`, or link existing pull requests with `gh stack link`. Pass the pull requests from bottom to top.

    gh stack link 41 42

GitHub shows how to create and link stacks in [Stacked pull requests](https://docs.github.com/en/pull-requests/reference/stacked-pull-requests).

Do not add `required_status_checks` to a ruleset that targets feature branches. GitHub checks that rule before every branch update. A new commit would need `gate` before the push that starts CI, so developers could not update the branch.

### Require Codecov patch coverage

Use this option when the repository uploads coverage and must block a PR that misses its patch target.

Install the Codecov GitHub App. Push the PR so Codecov reports `codecov/patch` on the current head. Then run:

    ./apply-codecov-ruleset.sh OWNER/REPO PR_NUMBER

The PR must target the default branch. The script reads the repository default branch, PR base, and PR head. It reads the canonical Codecov app ID from `gh api apps/codecov`. It accepts only a completed successful `codecov/patch` run from that app on the PR head. It checks the PR head again immediately before a write. If the PR base or head changes, the script writes nothing.

The script creates or updates one dedicated active ruleset, `pr-gate-codecov`. The ruleset requires `codecov/patch` from the canonical Codecov app on the default branch. It has no bypass actors. The script leaves `pr-gate` and all other rulesets unchanged. An exact existing ruleset causes no write. Running `./apply-ruleset.sh OWNER/REPO` later keeps the Codecov ruleset. The script has no delete path. To stop requiring `codecov/patch`, explicitly delete the `pr-gate-codecov` ruleset in GitHub.

## Rules that keep the gate honest

- `gate` uses `if: always()`. Without it, a failed job skips `gate`, and GitHub treats a skipped check as passing.
- Never path-filter `pr.yml`. A skipped workflow leaves `gate` pending, and the merge blocks.
- Skip slow work with a job-level `if:`. A job skipped that way reports success.
- Never make a review bot's check required. See [REVIEW.md](REVIEW.md).

## Limits

- Rulesets apply to private repositories only on GitHub Pro, Team, or Enterprise Cloud.
- Merge queue needs a public repository owned by an organization. Add a `merge_group` trigger to `pr.yml` if you enable it.
