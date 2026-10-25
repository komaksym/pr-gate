#!/usr/bin/env python3
"""Install the shared PR visual workflow and report enforcement coverage."""
import argparse
import base64
import json
import subprocess
from pathlib import Path


def gh(*args, payload=None):
    command = ['gh', *args]
    if payload is not None:
        command += ['--input', '-']
    result = subprocess.run(command, input=json.dumps(payload) if payload is not None else None,
                            text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return json.loads(result.stdout) if result.stdout.strip() else None


def caller(pin):
    return f'''name: PR infographic

on:
  pull_request:
    types: [opened, edited, synchronize, reopened, ready_for_review]

permissions: {{}}

jobs:
  visual:
    uses: komaksym/pr-gate/.github/workflows/pr-visual.yml@{pin}
    permissions:
      contents: read
      pull-requests: read
'''


def install(repo, pin, image, apply, arm):
    name = repo['full_name']
    row = {'repo': name, 'default': repo['default_branch'], 'state': 'planned'}
    if repo['archived'] or repo.get('disabled'):
        return dict(row, state='read-only')
    branch = 'ci/require-pr-infographic'
    file = '.github/workflows/required-pr-visual.yml'
    if not apply:
        return row
    base = gh('api', f'repos/{name}/git/ref/heads/{repo["default_branch"]}')['object']['sha']
    try:
        gh('api', f'repos/{name}/git/ref/heads/{branch}')
    except RuntimeError as error:
        if '404' not in str(error):
            raise
        gh('api', '-X', 'POST', f'repos/{name}/git/refs', payload={'ref': f'refs/heads/{branch}', 'sha': base})
    files = {file: caller(pin).encode(), '.codex-pr-infographics/required-pr-visual/infographic.png': image}
    for path, content in files.items():
        previous = None
        try:
            previous = gh('api', f'repos/{name}/contents/{path}?ref={branch}')
        except RuntimeError as error:
            if '404' not in str(error):
                raise
        if previous and base64.b64decode(previous.get('content', '')) == content:
            continue
        payload = {'message': 'ci(pr): require a committed PR infographic', 'branch': branch,
                   'content': base64.b64encode(content).decode()}
        if previous:
            payload['sha'] = previous['sha']
        gh('api', '-X', 'PUT', f'repos/{name}/contents/{path}', payload=payload)
    body = f'''## Summary
- Require the shared infographic check on PRs, including bots and forks.
- Validate current PR text and the committed PNG at the PR head.

## Validation
- Lint: shared workflow passed actionlint and zizmor
- Typecheck: N/A
- Test: shared validator passed five behavior tests
- Build/Package: N/A

## Risks / Notes
- Existing workflows and merge rules are preserved.
- Rule activation requires a successful check at this PR head.
- GitHub plan limitations are reported separately.

## Breaking changes
- PRs need an infographic committed to their head branch.

![Infographic](https://github.com/{name}/blob/{branch}/.codex-pr-infographics/required-pr-visual/infographic.png?raw=true)
'''
    prs = gh('api', f'repos/{name}/pulls?head={name.split("/")[0]}:{branch}&state=open')
    if prs:
        pr = gh('api', '-X', 'PATCH', f'repos/{name}/pulls/{prs[0]["number"]}', payload={'body': body})
    else:
        pr = gh('api', '-X', 'POST', f'repos/{name}/pulls', payload={
            'title': 'ci(pr): require an infographic on every pull request', 'body': body,
            'head': branch, 'base': repo['default_branch']})
    row.update(pr=pr['html_url'], head=pr['head']['sha'], state='adoption-pr-open')
    if arm:
        try:
            current = gh('api', f'repos/{name}/contents/{file}?ref={repo["default_branch"]}')
            if base64.b64decode(current.get('content', '')) != caller(pin).encode():
                return dict(row, state='awaiting-default-branch-workflow')
        except RuntimeError:
            return dict(row, state='awaiting-default-branch-workflow')
        checks = gh('api', f'repos/{name}/commits/{pr["head"]["sha"]}/check-runs?per_page=100')['check_runs']
        visual = [c for c in checks if c['name'].endswith('pr-visual') and c['app']['slug'] == 'github-actions']
        if not visual or visual[0]['conclusion'] != 'success':
            return dict(row, state='awaiting-successful-check')
        context = visual[0]['name']
        try:
            rules = gh('api', f'repos/{name}/rulesets')
            old = next((r for r in rules if r['name'] == 'pr-infographic'), None)
            spec = {'name': 'pr-infographic', 'target': 'branch', 'enforcement': 'active', 'bypass_actors': [],
                    'conditions': {'ref_name': {'include': ['~DEFAULT_BRANCH'], 'exclude': []}},
                    'rules': [{'type': 'required_status_checks', 'parameters': {
                        'strict_required_status_checks_policy': False, 'do_not_enforce_on_create': True,
                        'required_status_checks': [{'context': context, 'integration_id': 15368}]}}]}
            gh('api', '-X', 'PUT' if old else 'POST',
               f'repos/{name}/rulesets' + (f'/{old["id"]}' if old else ''), payload=spec)
            row.update(state='merge-protection-active', context=context)
        except RuntimeError as error:
            row.update(state='ruleset-unavailable', error=str(error))
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pin', required=True)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--repo', action='append')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--arm', action='store_true')
    args = parser.parse_args()
    if len(args.pin) != 40 or any(c not in '0123456789abcdef' for c in args.pin):
        parser.error('--pin must be a full commit SHA')
    image = args.image.read_bytes()
    if not image.startswith(b'\x89PNG\r\n\x1a\n'):
        parser.error('--image must be a PNG')
    if args.repo:
        repos = [gh('api', f'repos/{name}') for name in args.repo]
    else:
        pages = gh('api', '--paginate', '--slurp', 'user/repos?per_page=100')
        repos = [r for page in pages for r in page if r['permissions'].get('admin') or r['permissions'].get('maintain')]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('w') as report:
        for repo in repos:
            try:
                row = install(repo, args.pin, image, args.apply, args.arm)
            except RuntimeError as error:
                row = {'repo': repo['full_name'], 'state': 'failed', 'error': str(error)}
            report.write(json.dumps(row) + '\n')
            report.flush()
            print(json.dumps(row), flush=True)


if __name__ == '__main__':
    main()
