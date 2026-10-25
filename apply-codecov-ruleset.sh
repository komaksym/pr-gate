#!/usr/bin/env bash
# Create or update the opt-in Codecov ruleset after a genuine patch check passes.
# Usage: apply-codecov-ruleset.sh OWNER/REPO PR_NUMBER
set -euo pipefail

readonly usage="usage: apply-codecov-ruleset.sh OWNER/REPO PR_NUMBER"
readonly managed_name="pr-gate-codecov"
readonly check_name="codecov/patch"

usage_error() {
  printf 'error: %s\n%s\n' "$1" "$usage" >&2
  exit 1
}

die() {
  printf 'error: %s\n' "$1" >&2
  exit 1
}

read_api() {
  local endpoint="$1"
  shift
  local output
  if ! output="$(gh api "$endpoint" "$@")"; then
    die "GitHub API request failed: $endpoint"
  fi
  printf '%s' "$output"
}

write_api() {
  local description="$1"
  shift
  local output
  if ! output="$(gh api "$@")"; then
    die "GitHub API write failed: $description"
  fi
  printf '%s' "$output"
}

ruleset_decision() {
  local requires_source="$1"
  jq -r \
    --arg name "$managed_name" \
    --arg check "$check_name" \
    --argjson integration_id "$app_id" \
    --argjson requires_source "$requires_source" '
      def intended_rule:
        ((.rules // []) | length == 1)
        and .rules[0].type == "required_status_checks"
        and (
          (.rules[0].parameters | keys)
          == ["do_not_enforce_on_create", "required_status_checks", "strict_required_status_checks_policy"]
        )
        and .rules[0].parameters.strict_required_status_checks_policy == false
        and .rules[0].parameters.do_not_enforce_on_create == false
        and ((.rules[0].parameters.required_status_checks // []) | length == 1)
        and .rules[0].parameters.required_status_checks[0].context == $check
        and (
          ((.rules[0].parameters.required_status_checks[0] | keys) - ["context", "integration_id"])
          | length == 0
        );

      if .name == $name
        and .target == "branch"
        and (
          if $requires_source
          then (.source_type // "") == "Repository"
          else true
          end
        )
        and (.conditions | keys) == ["ref_name"]
        and ((.conditions.ref_name | keys) == ["exclude", "include"])
        and .conditions.ref_name.include == ["~DEFAULT_BRANCH"]
        and .conditions.ref_name.exclude == []
        and ((.bypass_actors // []) == [])
        and intended_rule
      then
        if .enforcement == "active"
          and .rules[0].parameters.required_status_checks[0].integration_id == $integration_id
        then "exact"
        else "update"
        end
      else "conflict"
      end
    '
}

if (( $# != 2 )); then
  usage_error "expected OWNER/REPO and PR_NUMBER"
fi

repo="$1"
pr_number="$2"
if [[ ! "$repo" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]*/[A-Za-z0-9_.-]+$ ]]; then
  usage_error "invalid OWNER/REPO: $repo"
fi
if [[ ! "$pr_number" =~ ^[1-9][0-9]*$ ]]; then
  usage_error "invalid PR_NUMBER: $pr_number"
fi

script_dir="$(cd "$(dirname "$0")" && pwd)"
spec="$script_dir/codecov-ruleset.json"
payload_file="$(mktemp "${TMPDIR:-/tmp}/codecov-ruleset.XXXXXX")"
trap 'rm -f "$payload_file"' EXIT

if ! jq -e --arg name "$managed_name" --arg check "$check_name" '
  .name == $name
  and .target == "branch"
  and .enforcement == "active"
  and .conditions.ref_name.include == ["~DEFAULT_BRANCH"]
  and .conditions.ref_name.exclude == []
  and .bypass_actors == []
  and (.rules | length == 1)
  and .rules[0].type == "required_status_checks"
  and .rules[0].parameters.strict_required_status_checks_policy == false
  and .rules[0].parameters.do_not_enforce_on_create == false
  and .rules[0].parameters.required_status_checks == [{"context": $check}]
' "$spec" >/dev/null; then
  die "invalid ruleset template: $spec"
fi

repo_json="$(read_api "repos/$repo")"
default_branch="$(jq -er '.default_branch | select(type == "string" and length > 0)' <<< "$repo_json")"

pr_json="$(read_api "repos/$repo/pulls/$pr_number")"
base_ref="$(jq -er '.base.ref' <<< "$pr_json")"
head_sha="$(jq -er '.head.sha' <<< "$pr_json")"
if [[ ! "$head_sha" =~ ^[0-9a-f]{40}$ ]]; then
  die "PR head is not a commit SHA"
fi
if [[ "$base_ref" != "$default_branch" ]]; then
  die "PR base $base_ref is not the default branch $default_branch"
fi

app_json="$(read_api "apps/codecov")"
app_id="$(jq -er '.id | select(type == "number" and . > 0 and . == floor)' <<< "$app_json")"
app_slug="$(jq -er '.slug' <<< "$app_json")"
if [[ "$app_slug" != "codecov" ]]; then
  die "apps/codecov did not return the canonical app slug"
fi

check_pages="$(read_api \
  "repos/$repo/commits/$head_sha/check-runs?per_page=100&filter=latest" \
  --paginate)"
checks="$(jq -sc '[.[] | (.check_runs // [])[]]' <<< "$check_pages")"
matching_checks="$(jq -c --arg name "$check_name" \
  '[.[] | select(.name == $name)]' <<< "$checks")"

if [[ "$(jq 'length' <<< "$matching_checks")" -eq 0 ]]; then
  die "no $check_name check was found on the PR head"
fi
if [[ "$(jq --arg check "$check_name" \
  --argjson integration_id "$app_id" '
    [.[]
      | select(.name == $check)
      | select(
          (.app.slug // "") != "codecov"
          or (.app.id // 0) != $integration_id
        )
    ] | length
  ' <<< "$matching_checks")" -ne 0 ]]; then
  die "$check_name is not from the canonical Codecov GitHub App"
fi
if [[ "$(jq --arg check "$check_name" --arg head "$head_sha" '
  [.[]
    | select(.name == $check)
    | select(.head_sha != $head)
  ] | length
' <<< "$matching_checks")" -ne 0 ]]; then
  die "$check_name is not on the PR's current head"
fi
if [[ "$(jq --arg check "$check_name" '
  [.[]
    | select(.name == $check)
    | select(.status != "completed" or .conclusion != "success")
  ] | length
' <<< "$matching_checks")" -ne 0 ]]; then
  die "$check_name must be completed successfully"
fi

ruleset_pages="$(read_api "repos/$repo/rulesets?per_page=100" --paginate)"
rulesets="$(jq -sc '[.[] | .[]]' <<< "$ruleset_pages")"
managed_ids="$(jq -c --arg name "$managed_name" \
  '[.[] | select(.name == $name) | .id]' <<< "$rulesets")"
managed_count="$(jq 'length' <<< "$managed_ids")"
if [[ "$managed_count" -gt 1 ]]; then
  die "duplicate managed rulesets named $managed_name"
fi

existing_id=""
existing_json=""
existing_decision=""
if [[ "$managed_count" -eq 1 ]]; then
  existing_id="$(jq -er '.[0] | select(type == "number" and . > 0 and . == floor)' \
    <<< "$managed_ids")"
  existing_json="$(read_api "repos/$repo/rulesets/$existing_id")"
  if ! jq -e \
    --argjson id "$existing_id" '
      .id == $id
    ' <<< "$existing_json" >/dev/null; then
    die "conflicting managed ruleset named $managed_name"
  fi
  existing_decision="$(ruleset_decision true <<< "$existing_json")"
  if [[ "$existing_decision" == "conflict" ]]; then
    die "conflicting managed ruleset named $managed_name"
  fi
fi

jq \
  --argjson integration_id "$app_id" \
  '.rules[0].parameters.required_status_checks =
    [{"context": "codecov/patch", "integration_id": $integration_id}]' \
  "$spec" > "$payload_file"
if [[ "$(ruleset_decision false < "$payload_file")" != "exact" ]]; then
  die "invalid Codecov ruleset payload"
fi

if [[ "$existing_decision" == "exact" ]]; then
  printf '%s is already exact\n' "$managed_name"
  jq -c --arg check "$check_name" '
    {
      id,
      name,
      enforcement,
      required: [.rules[]?
        | select(.type == "required_status_checks")
        | .parameters.required_status_checks[]
        | select(.context == $check)]
    }
  ' <<< "$existing_json"
  exit 0
fi

recheck_pr="$(read_api "repos/$repo/pulls/$pr_number")"
if ! jq -e --arg base "$default_branch" --arg head "$head_sha" '
  .base.ref == $base and .head.sha == $head
' <<< "$recheck_pr" >/dev/null; then
  die "PR base or head changed after the Codecov check; no write was made"
fi

action="updated"
if [[ -n "$existing_id" ]]; then
  write_api "$managed_name ruleset $existing_id" \
    -X PUT "repos/$repo/rulesets/$existing_id" \
    --input "$payload_file" >/dev/null
else
  existing_id="$(write_api "$managed_name ruleset" \
    -X POST "repos/$repo/rulesets" \
    --input "$payload_file" \
    --jq '.id')"
  action="created"
fi
if [[ ! "$existing_id" =~ ^[1-9][0-9]*$ ]]; then
  die "GitHub returned an invalid ruleset id"
fi

verified_json="$(read_api "repos/$repo/rulesets/$existing_id")"
if [[ "$(ruleset_decision true <<< "$verified_json")" != "exact" ]]; then
  die "live $managed_name ruleset does not match the requested configuration"
fi

printf '%s %s\n' "$managed_name" "$action"
jq -c --arg check "$check_name" '
  {
    id,
    name,
    enforcement,
    required: [.rules[]?
      | select(.type == "required_status_checks")
      | .parameters.required_status_checks[]
      | select(.context == $check)]
  }
' <<< "$verified_json"
