# Review rule for agents

AI review bots advise. Their unresolved threads block the merge. Their checks never gate it.

## Before the PR opens

Run the local review your workflow defines, such as pstack `interrogate`. It costs no bot credits.

## When the PR is ready

1. Pick the tier. A risky PR touches auth, data, billing, extension permissions, or CI. It gets two bots. Every other PR gets one.
2. Trigger bots in this order. Skip a bot that has no free review left.
   - Public repo: CodeRabbit (`@coderabbitai review`), then Greptile, then cubic.
   - Private repo: Greptile, then cubic. CodeRabbit gives private repos summaries only.
3. Trigger each bot once, on the ready head. Do not re-trigger on every push.
4. Wait up to 15 minutes for the review on the current head.
5. When a bot replies that its limit is reached, trigger the next bot.
6. When no bot can review, note that in the PR and continue.

## Handling comments

- Tag each comment `fix`, `dismiss`, or `ask`.
- Reply with the fix commit or the reason before you resolve a thread.
- Ask the operator about `ask` comments. Do not guess.

## Merging

Merge when `gate` passes and no thread is open. A reviewer check that reports neutral or never reports does not block the merge.

Each month, count the `fix` tags per bot and reorder the chain by that count.
