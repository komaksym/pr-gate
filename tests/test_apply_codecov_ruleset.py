import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODECOV_SCRIPT = ROOT / "apply-codecov-ruleset.sh"
PLAIN_SCRIPT = ROOT / "apply-ruleset.sh"
FAKE_GH = ROOT / "tests" / "fake_gh.py"
HEAD = "a" * 40
CHANGED_HEAD = "b" * 40


def check(codecov=True, status="completed", conclusion="success", head=HEAD):
    if codecov:
        app = {"slug": "codecov", "id": 254}
        name = "codecov/patch"
    else:
        app = {"slug": "github-actions", "id": 15368}
        name = "gate"
    return {
        "id": 1,
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "head_sha": head,
        "app": app,
    }


def ruleset(identifier, name, context, integration_id):
    return {
        "id": identifier,
        "name": name,
        "target": "branch",
        "source_type": "Repository",
        "source": "owner/repo",
        "enforcement": "active",
        "conditions": {
            "ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}
        },
        "bypass_actors": [],
        "rules": [
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": False,
                    "do_not_enforce_on_create": False,
                    "required_status_checks": [
                        {"context": context, "integration_id": integration_id}
                    ],
                },
            }
        ],
    }


def base_state():
    return {
        "default_branch": "main",
        "pr": {"base": "main", "head": HEAD, "state": "open"},
        "pr_heads": [],
        "app": {"id": 254, "slug": "codecov"},
        "checks": [check()],
        "rulesets": {
            "1": ruleset(1, "pr-gate", "gate", 15368),
            "9": ruleset(9, "release-branches", "release", 15368),
        },
        "page_size": 100,
        "api_errors": {},
        "calls": [],
        "writes": [],
    }


class CodecovRulesetTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = Path(tempfile.mkdtemp(prefix="codecov-ruleset-test-"))
        bin_dir = self.tempdir / "bin"
        bin_dir.mkdir()
        wrapper = bin_dir / "gh"
        wrapper.write_text('#!/bin/sh\nexec python3 "$FAKE_GH_IMPL" "$@"\n')
        wrapper.chmod(0o755)
        self.state_path = self.tempdir / "gh-state.json"
        self.state = base_state()
        self.last = None

    def tearDown(self):
        artifact_dir = os.environ.get("CODECOV_RULESET_TEST_ARTIFACTS")
        if artifact_dir and self.last is not None:
            destination = Path(artifact_dir)
            destination.mkdir(parents=True, exist_ok=True)
            artifact = {
                "test": self._testMethodName,
                "returncode": self.last.returncode,
                "stdout": self.last.stdout,
                "stderr": self.last.stderr,
                "state": self.state,
            }
            (destination / f"{self._testMethodName}.json").write_text(
                json.dumps(artifact, indent=2, sort_keys=True) + "\n"
            )
        shutil.rmtree(self.tempdir)

    def write_state(self):
        self.state_path.write_text(json.dumps(self.state, indent=2, sort_keys=True) + "\n")

    def run_script(self, *args, script=CODECOV_SCRIPT):
        self.write_state()
        env = os.environ.copy()
        env["PATH"] = f"{self.tempdir / 'bin'}{os.pathsep}{env['PATH']}"
        env["FAKE_GH_STATE"] = str(self.state_path)
        env["FAKE_GH_IMPL"] = str(FAKE_GH)
        self.last = subprocess.run(
            [str(script), *map(str, args)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.state = json.loads(self.state_path.read_text())
        return self.last

    def assert_rejected_without_writes(self, message):
        self.assertNotEqual(self.last.returncode, 0)
        self.assertIn(message, self.last.stderr.lower())
        self.assertEqual(self.state["writes"], [])

    def codecov_rulesets(self):
        return [
            item
            for item in self.state["rulesets"].values()
            if item["name"] == "pr-gate-codecov"
        ]

    def test_rejects_invalid_arguments_before_api(self):
        for arguments in (
            (),
            ("owner/repo",),
            ("owner/repo", "0"),
            ("owner/repo", "-1"),
            ("owner/repo", "pr"),
            ("owner", "7"),
            ("owner/repo/extra", "7"),
            ("-owner/repo", "7"),
        ):
            with self.subTest(arguments=arguments):
                self.state = base_state()
                self.run_script(*arguments)
                self.assert_rejected_without_writes("usage")
                self.assertEqual(self.state["calls"], [])

    def test_rejects_missing_codecov_check_without_write(self):
        self.state["checks"] = [check(codecov=False)]
        self.run_script("owner/repo", "7")
        self.assert_rejected_without_writes("codecov/patch")

    def test_rejects_spoofed_codecov_checks_without_write(self):
        for app in (
            {"slug": "codecov-evil", "id": 254},
            {"slug": "codecov", "id": 999},
        ):
            with self.subTest(app=app):
                self.state = base_state()
                self.state["checks"][0]["app"] = app
                self.run_script("owner/repo", "7")
                self.assert_rejected_without_writes("canonical")

    def test_rejects_failed_check_without_write(self):
        self.state["checks"][0] = check(conclusion="failure")
        self.run_script("owner/repo", "7")
        self.assert_rejected_without_writes("successful")

    def test_successful_retry_supersedes_an_older_failure(self):
        older = check(conclusion="failure")
        newer = {**check(), "id": 2}
        self.state["checks"] = [newer, older]
        self.run_script("owner/repo", "7")
        self.assertEqual(self.last.returncode, 0, self.last.stderr)
        self.assertEqual(len(self.state["writes"]), 1)

    def test_failed_retry_cannot_use_an_older_success(self):
        older = check()
        newer = {**check(conclusion="failure"), "id": 2}
        self.state["checks"] = [newer, older]
        self.run_script("owner/repo", "7")
        self.assert_rejected_without_writes("successful")

    def test_rejects_incomplete_check_without_write(self):
        self.state["checks"][0] = check(status="in_progress", conclusion=None)
        self.run_script("owner/repo", "7")
        self.assert_rejected_without_writes("completed")

    def test_rejects_stale_check_without_write(self):
        self.state["checks"][0] = check(head=CHANGED_HEAD)
        self.run_script("owner/repo", "7")
        self.assert_rejected_without_writes("current head")

    def test_rejects_head_change_before_write(self):
        self.state["pr_heads"] = [HEAD, CHANGED_HEAD]
        self.run_script("owner/repo", "7")
        self.assert_rejected_without_writes("changed")

    def test_create_uses_canonical_app_and_preserves_siblings(self):
        sibling_before = copy.deepcopy(self.state["rulesets"])
        self.state["page_size"] = 1
        self.state["checks"] = [check(codecov=False), check()]
        self.run_script("owner/repo", "7")
        self.assertEqual(self.last.returncode, 0, self.last.stderr)
        self.assertEqual(len(self.state["writes"]), 1)
        self.assertEqual(self.state["writes"][0]["method"], "POST")
        created = self.codecov_rulesets()
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["name"], "pr-gate-codecov")
        self.assertEqual(created[0]["enforcement"], "active")
        self.assertEqual(created[0]["bypass_actors"], [])
        required = created[0]["rules"][0]["parameters"]["required_status_checks"]
        self.assertEqual(required, [{"context": "codecov/patch", "integration_id": 254}])
        for identifier, sibling in sibling_before.items():
            self.assertEqual(self.state["rulesets"][identifier], sibling)

    def test_create_reads_app_id_from_api(self):
        self.state["app"] = {"id": 4321, "slug": "codecov"}
        self.state["checks"][0]["app"] = {"id": 4321, "slug": "codecov"}
        self.run_script("owner/repo", "7")
        self.assertEqual(self.last.returncode, 0, self.last.stderr)
        required = self.codecov_rulesets()[0]["rules"][0]["parameters"][
            "required_status_checks"
        ]
        self.assertEqual(required[0]["integration_id"], 4321)

    def test_updates_only_dedicated_ruleset(self):
        existing = ruleset(2, "pr-gate-codecov", "codecov/patch", 999)
        existing["enforcement"] = "evaluate"
        self.state["rulesets"]["2"] = existing
        sibling_before = {
            identifier: copy.deepcopy(value)
            for identifier, value in self.state["rulesets"].items()
            if identifier != "2"
        }
        self.state["page_size"] = 1
        self.run_script("owner/repo", "7")
        self.assertEqual(self.last.returncode, 0, self.last.stderr)
        self.assertEqual(len(self.state["writes"]), 1)
        self.assertEqual(self.state["writes"][0]["method"], "PUT")
        self.assertEqual(self.state["writes"][0]["endpoint"], "repos/owner/repo/rulesets/2")
        self.assertEqual(self.codecov_rulesets()[0]["enforcement"], "active")
        required = self.codecov_rulesets()[0]["rules"][0]["parameters"][
            "required_status_checks"
        ]
        self.assertEqual(required[0]["integration_id"], 254)
        for identifier, sibling in sibling_before.items():
            self.assertEqual(self.state["rulesets"][identifier], sibling)

    def test_exact_ruleset_is_idempotent(self):
        self.state["rulesets"]["2"] = ruleset(
            2, "pr-gate-codecov", "codecov/patch", 254
        )
        self.state["page_size"] = 1
        sibling_before = copy.deepcopy(self.state["rulesets"])
        self.run_script("owner/repo", "7")
        self.assertEqual(self.last.returncode, 0, self.last.stderr)
        self.assertEqual(self.state["writes"], [])
        self.assertEqual(self.state["rulesets"], sibling_before)

    def test_plain_gate_apply_retains_codecov_ruleset(self):
        self.state["rulesets"]["2"] = ruleset(
            2, "pr-gate-codecov", "codecov/patch", 254
        )
        codecov_before = copy.deepcopy(self.state["rulesets"]["2"])
        self.run_script("owner/repo", "7")
        self.assertEqual(self.last.returncode, 0, self.last.stderr)
        self.assertEqual(self.state["writes"], [])
        self.state["calls"] = []
        self.run_script("owner/repo", script=PLAIN_SCRIPT)
        self.assertEqual(self.last.returncode, 0, self.last.stderr)
        self.assertEqual(self.state["rulesets"]["2"], codecov_before)
        self.assertEqual(
            [(write["method"], write["endpoint"]) for write in self.state["writes"]],
            [("PUT", "repos/owner/repo/rulesets/1")],
        )

    def test_rejects_duplicate_dedicated_rulesets_without_write(self):
        self.state["rulesets"]["2"] = ruleset(
            2, "pr-gate-codecov", "codecov/patch", 254
        )
        self.state["rulesets"]["3"] = ruleset(
            3, "pr-gate-codecov", "codecov/patch", 254
        )
        self.run_script("owner/repo", "7")
        self.assert_rejected_without_writes("duplicate")

    def test_rejects_conflicting_dedicated_ruleset_without_write(self):
        self.state["rulesets"]["2"] = ruleset(
            2, "pr-gate-codecov", "codecov/patch", 254
        )
        self.state["rulesets"]["2"]["target"] = "tag"
        self.run_script("owner/repo", "7")
        self.assert_rejected_without_writes("conflict")

    def test_rejects_incompatible_existing_ruleset_without_write(self):
        for mutation in (
            "extra_check",
            "extra_rule",
            "extra_condition",
            "scope",
            "bypass",
            "strict",
        ):
            with self.subTest(mutation=mutation):
                self.state = base_state()
                existing = ruleset(2, "pr-gate-codecov", "codecov/patch", 254)
                if mutation == "extra_check":
                    existing["rules"][0]["parameters"]["required_status_checks"].append(
                        {"context": "manual-approval", "integration_id": 999}
                    )
                elif mutation == "extra_rule":
                    existing["rules"].append({"type": "deletion"})
                elif mutation == "extra_condition":
                    existing["conditions"]["repository_name"] = {
                        "include": ["~ALL"],
                        "exclude": [],
                    }
                elif mutation == "scope":
                    existing["conditions"]["ref_name"]["include"].append(
                        "refs/heads/release"
                    )
                elif mutation == "bypass":
                    existing["bypass_actors"].append(
                        {"actor_id": 1, "actor_type": "Team", "bypass_mode": "always"}
                    )
                elif mutation == "strict":
                    existing["rules"][0]["parameters"][
                        "strict_required_status_checks_policy"
                    ] = True
                self.state["rulesets"]["2"] = existing
                self.run_script("owner/repo", "7")
                self.assert_rejected_without_writes("conflict")

    def test_api_error_makes_no_write(self):
        self.state["api_errors"] = {
            "GET repos/owner/repo/rulesets?per_page=100": "rulesets unavailable"
        }
        self.run_script("owner/repo", "7")
        self.assert_rejected_without_writes("github api")


if __name__ == "__main__":
    unittest.main()
