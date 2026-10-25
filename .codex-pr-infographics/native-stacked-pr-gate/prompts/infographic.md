---
references:
  - ref_id: 01
    filename: refs/01-ref-native-stacked-pr-gate.png
    usage: direct
---

Use the referenced infographic as the composition and style reference. Render a fresh, faithful version with the exact text below. Do not copy the reference bytes.

Create a professional English infographic in landscape 16:9. Use structural-breakdown layout with technical-schematic styling. Opaque light gray canvas, visible navy border, high-contrast navy typography, restrained teal and red accents, and generous whitespace.

Title: "NATIVE STACKS USE THE TRUNK GATE"
Subtitle: "GitHub applies the bottom PR's rules to every layer"

Use two panels side by side.

Left panel, headed "SUPPORTED STACK": show three pull request cards in a vertical chain from bottom to top. Bottom card text "BOTTOM PR" and "Base is main". Middle card text "STACK" and "Every layer follows the trunk". Top card text "CHILD PR" and "Base is the branch below". Draw upward connecting arrows. Beside the chain place a navy shield labeled "MAIN RULESET" and "Requires gate for every layer". Add a teal check mark.

Right panel, headed "FEATURE RULESET FAILS": show a vertical four-step warning sequence. Step labels exactly: "FEATURE-BRANCH RULESET", "PUSH NEW COMMIT", "GATE IS MISSING", "UPDATE REJECTED". Use navy boxes and a red warning accent on the last step. Add the line "CI starts after a push, but GitHub checks the rule before it."

Below both panels, place a wide action band labeled "LINK THE STACK" with the command "gh stack link 41 42" and the note "Pass pull requests bottom to top."

Footer: "Do not put required status checks on feature branches."
Small bottom caption: "Verified on komaksym/prc: an unchecked branch update was rejected, so the rule was removed."

Use exact text. Spell every word exactly as written. Keep all labels legible. Do not show invented metrics, pass counts, or fabricated screenshots.
