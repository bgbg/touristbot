---
description: Comprehensive self-review before PR submission
---

# Git Pre-PR

Perform a fast, high-signal self-review of the current branch before opening a PR for the project. Produce actionable improvements, risk callouts, and a concise review report. Do not generate a PR or PR text. Do not create any files - only report to the user.

## Behavior
0) Run unit tests (skip if `--no-tests` is provided)
   - `scripts/run_tests.sh` runs both backend and frontend tests. If tests fail, abort with a notice that specifies which tests failed.

1) Setup
   - You may work in a worktree or the main repo. Keep this in mind.
   - Detect repo, current branch, and default base (`gh repo view --json defaultBranchRef`).
   - Do not check for GitHub authentication beforehand. If authentication fails, handle the error and attempt to authenticate.
   - Fetch and fast-forward base: `git fetch --prune --tags`, then `git checkout <base> && git pull --ff-only && git checkout -`.
   - Compute comparison base: `git merge-base <base> HEAD`.

3) GitHub Issue Analysis
   - If working on an issue, it is possible that a file named todo__<issue number>.md exists. Read its content.
   - If the todo file does not eFetch the GitHub issue referenced in branch name or commit messages.
   - Read the issue description and all comments to understand requirements.
   - Compare issue requirements against commit log and changes in this branch.
   - Answer: Have we addressed the issue? Are all items in the GitHub issue taken care of?
   - Flag any missing requirements or incomplete implementations.

4) Checks
   - Secrets/debug leftovers scan in changed hunks only.
   - Lockfile/manifest mismatches (requirements.txt, pyproject.toml).
   - Generated/binary files committed.
   - Prompt YAML validation (check for missing required fields).
   - **Exception handling violations**: Search for `except` blocks that catch exceptions but allow code to continue without either:
     a) Fixing the root cause of the exception, OR
     b) Re-raising the exception (with `raise` or `raise SomeException`)
     Note: Mere logging (logger.warning, logger.error, print, etc.) does NOT qualify as fixing the exception.

5) Suggestions
   - Small, concrete refactors for the largest-touched files or duplicated patterns.
   - Follow-ups when too risky to change now.
   - What can be simplified, cleared, removed before the PR?
   - **Commit splitting**: If the commit is large or touches multiple scopes/areas, suggest splitting into manageable, focused commits by scope.

6) Output
   - Short markdown report with: Summary, Changes, Risks, Tests, Checklist.
   - Do not include any signature lines or trailers (e.g., `Signed-off-by:`).

## Performance
- **Fast analysis**: Focus on critical checks and high-impact suggestions
- **Comprehensive review**: Deep analysis of code quality, patterns, and completeness

## Arguments (from {{ARGS}})
- `--area-threshold <n>`: Flag when more than N top-level areas are touched (default: 8).
- `--no-tests`: Skip running unit tests and assume all tests pass.

## Heuristics
- If the current branch equals the base branch, abort with a short notice.
- If only docs/config were changed, adjust checklist and simplify the review report.
- If lockfiles changed without manifests, highlight and propose reinstall/regenerate.
- If test deltas are zero while code delta is high, suggest targeted tests.
- If diff is extremely large, recommend splitting by area or commit sequence.
- If prompt files changed, validate YAML structure and required fields.
