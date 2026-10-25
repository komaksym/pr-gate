#!/usr/bin/env python3
"""Serve the small GitHub API surface used by the ruleset scripts."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def fail(message):
    print(f"fake gh: {message}", file=sys.stderr)
    raise SystemExit(1)


def paginate(items, page_size, enabled):
    if not enabled:
        return [items[:page_size]]
    return [items[index : index + page_size] for index in range(0, len(items), page_size)] or [[]]


def ruleset_summary(ruleset):
    return {
        key: ruleset[key]
        for key in ("id", "name", "target", "source_type", "source", "enforcement")
        if key in ruleset
    }


def response(endpoint, method, state, paginate_pages, payload):
    path = endpoint.split("?", 1)[0]

    match = re.fullmatch(r"repos/([^/]+/[^/]+)", path)
    if method == "GET" and match:
        repo = match.group(1)
        return [
            {
                "full_name": repo,
                "default_branch": state["default_branch"],
            }
        ]

    match = re.fullmatch(r"repos/([^/]+/[^/]+)/pulls/([0-9]+)", path)
    if method == "GET" and match:
        if state.get("pr_heads"):
            state["pr"]["head"] = state["pr_heads"].pop(0)
        return [
            {
                "base": {"ref": state["pr"]["base"]},
                "head": {"sha": state["pr"]["head"]},
                "state": state["pr"]["state"],
            }
        ]

    if method == "GET" and path == "apps/codecov":
        return [state["app"]]

    match = re.fullmatch(r"repos/([^/]+/[^/]+)/commits/[^/]+/check-runs", path)
    if method == "GET" and match:
        checks = [
            {
                "id": check.get("id", index + 1),
                "name": check["name"],
                "status": check["status"],
                "conclusion": check.get("conclusion"),
                "head_sha": check["head_sha"],
                "app": check.get("app"),
            }
            for index, check in enumerate(state.get("checks", []))
        ]
        return [
            {"check_runs": page}
            for page in paginate(
                checks, state.get("page_size", 100), paginate_pages
            )
        ]

    match = re.fullmatch(r"repos/([^/]+/[^/]+)/rulesets", path)
    if match:
        rulesets = sorted(state.get("rulesets", {}).values(), key=lambda item: item["id"])
        if method == "GET":
            summaries = [ruleset_summary(ruleset) for ruleset in rulesets]
            return paginate(summaries, state.get("page_size", 100), paginate_pages)
        if method == "POST":
            if payload is None:
                fail("POST rulesets requires --input")
            identifier = max((int(item["id"]) for item in rulesets), default=0) + 1
            created = {"id": identifier, **payload}
            created.setdefault("source_type", "Repository")
            created.setdefault("source", match.group(1))
            state.setdefault("rulesets", {})[str(identifier)] = created
            state.setdefault("writes", []).append(
                {"method": method, "endpoint": endpoint, "body": payload}
            )
            return [created]

    match = re.fullmatch(r"repos/([^/]+/[^/]+)/rulesets/([0-9]+)", path)
    if match and method == "GET":
        ruleset = state.get("rulesets", {}).get(match.group(2))
        if ruleset is None:
            fail("ruleset not found")
        return [ruleset]
    if match and method == "PUT":
        if payload is None:
            fail("PUT ruleset requires --input")
        identifier = int(match.group(2))
        if str(identifier) not in state.get("rulesets", {}):
            fail("ruleset not found")
        previous = state["rulesets"][str(identifier)]
        updated = {"id": identifier, **payload}
        updated.setdefault("source_type", previous.get("source_type", "Repository"))
        updated.setdefault("source", previous.get("source", match.group(1)))
        state["rulesets"][str(identifier)] = updated
        state.setdefault("writes", []).append(
            {"method": method, "endpoint": endpoint, "body": payload}
        )
        return [updated]

    fail(f"unsupported request: {method} {endpoint}")


def parse_args(argv):
    method = "GET"
    endpoint = None
    paginate_pages = False
    jq_filter = None
    payload_path = None
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument in ("-X", "--method"):
            index += 1
            if index == len(argv):
                fail(f"{argument} requires a value")
            method = argv[index].upper()
        elif argument == "--paginate":
            paginate_pages = True
        elif argument == "--jq":
            index += 1
            if index == len(argv):
                fail("--jq requires a value")
            jq_filter = argv[index]
        elif argument == "--input":
            index += 1
            if index == len(argv):
                fail("--input requires a value")
            payload_path = Path(argv[index])
        elif argument.startswith("-"):
            fail(f"unsupported option: {argument}")
        elif endpoint is None:
            endpoint = argument
        else:
            fail(f"unexpected argument: {argument}")
        index += 1
    if endpoint is None:
        fail("missing endpoint")
    payload = None
    if payload_path is not None:
        payload = json.loads(payload_path.read_text())
    return method, endpoint, paginate_pages, jq_filter, payload


def main(argv):
    if argv and argv[0] == "api":
        argv = argv[1:]
    state_path = Path(os.environ["FAKE_GH_STATE"])
    state = json.loads(state_path.read_text())
    method, endpoint, paginate_pages, jq_filter, payload = parse_args(argv)
    state.setdefault("calls", []).append({"method": method, "endpoint": endpoint})
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")

    errors = state.get("api_errors", {})
    error = errors.get(f"{method} {endpoint}", errors.get(endpoint))
    if error:
        print(error, file=sys.stderr)
        return 1

    documents = response(endpoint, method, state, paginate_pages, payload)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")

    if jq_filter is None:
        for document in documents:
            print(json.dumps(document, indent=2, sort_keys=True))
        return 0

    for document in documents:
        result = subprocess.run(
            ["jq", "-r", jq_filter],
            input=json.dumps(document),
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            sys.stderr.write(result.stderr)
            return result.returncode
        sys.stdout.write(result.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
