# Native stacks use the trunk gate

## Learning objective

Explain how GitHub applies trunk rules to every native stack layer and why a feature-branch required-check ruleset is unsafe.

## Supported path

| Order | Label | Detail |
| --- | --- | --- |
| Top | CHILD PR | Base is the branch below |
| Middle | STACK | Every layer is checked against the trunk |
| Bottom | BOTTOM PR | Base is `main` |

## Trunk policy

| Label | Detail |
| --- | --- |
| MAIN RULESET | Requires `gate` for every layer |

## Unsafe path

| Order | Label |
| --- | --- |
| 1 | FEATURE-BRANCH RULESET |
| 2 | PUSH NEW COMMIT |
| 3 | GATE IS MISSING |
| 4 | UPDATE REJECTED |

The `gate` workflow cannot run until the push succeeds. GitHub checks the rule before the push.

## Action

Use `gh stack link` with pull requests in bottom-to-top order.
