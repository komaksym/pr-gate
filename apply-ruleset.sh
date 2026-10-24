#!/usr/bin/env bash
# Create or update the pr-gate ruleset on one repository. Safe to re-run.
# Usage: apply-ruleset.sh OWNER/REPO
set -euo pipefail

repo="${1:?usage: apply-ruleset.sh OWNER/REPO}"
spec="$(cd "$(dirname "$0")" && pwd)/ruleset.json"
name="$(jq -r .name "$spec")"

id="$(gh api "repos/$repo/rulesets" --paginate --jq ".[] | select(.name == \"$name\") | .id")"
if [ -n "$id" ]; then
  gh api -X PUT "repos/$repo/rulesets/$id" --input "$spec" > /dev/null
else
  id="$(gh api -X POST "repos/$repo/rulesets" --input "$spec" --jq .id)"
fi

gh api "repos/$repo/rulesets/$id" --jq '{id, name, enforcement, required: [.rules[] | select(.type == "required_status_checks") | .parameters.required_status_checks[].context]}'

others="$(gh api "repos/$repo/rulesets" --paginate --jq ".[] | select(.name != \"$name\" and .enforcement == \"active\") | \"\\(.id) \\(.name)\"")"
if [ -n "$others" ]; then
  echo "These active rulesets still apply and may require old checks:" >&2
  echo "$others" >&2
fi
