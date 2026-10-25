# Native stacked PR gate

## Audience

Repository maintainers who need required checks on every layer of a GitHub pull request stack.

## Content type

Technical comparison between the supported native stack behavior and an unsafe feature-branch required-check ruleset.

## Learning objectives

- Show that GitHub evaluates every native stack layer against the stack trunk.
- Show that the existing `pr-gate` ruleset on `main` therefore covers the stack.
- Show why a required-check rule on feature branches blocks work before CI can run.
- Give the command that links existing pull requests into a stack.

## Design choices

- Layout: `structural-breakdown`, because the stack, trunk policy, and blocked push form one system.
- Style: `technical-schematic`, because the content describes repository behavior.
- Aspect: `16:9` for a side-by-side supported and unsafe flow.
- Language: English, matching the repository documentation.
- Backend: auto, using Codex image generation first.
- Palette: light gray canvas, navy structure, teal success accent, restrained red warning accent.

## Constraints

- Use the exact labels from the prompt.
- Show no invented metrics, pass counts, or fabricated screenshots.
- Keep the distinction between branch updates and pull request merges clear.
