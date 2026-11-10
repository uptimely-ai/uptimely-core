# Pull request summary

Summarize the changes on the current branch compared with `main`.

Inspect the branch diff from the merge base with `main`, plus relevant commit
messages. Include uncommitted changes only in a clearly separate section; do not
mix them into the branch summary. Do not modify files.

Return a concise PR-ready summary with:

- A short title
- What changed and why
- User-visible impact, if any
- Tests or checks known to have run (do not infer that they passed)

Give the PR summary as markdown that can be easily copied.

Do not claim behavior or validation that the diff and available evidence do not
support.
