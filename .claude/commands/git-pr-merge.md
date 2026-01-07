---
description: Merge the PR for current branch and clean up branches
---

# Git PR Merge

Take the last created PR for the current branch, merge it, and clean up the branch both locally and remotely.

Assume we are authenticated with GitHub. Run the commands without checking and deal with errors if they occur.

## Behavior

1) Get current branch
   - Run `git branch --show-current` to get the current branch name.
   - Assume we are on the correct branch. Do not validate.

2) Find and merge PR
   - Query `gh pr list --head <current-branch> --json number,state` for the current branch.
   - If no PR exists, abort with error message.
   - Execute `gh pr merge <pr-number> --merge` to merge the PR.
   - If merge fails, abort with error message.

3) Post-merge cleanup (default behavior)
   - Run `git checkout main` (or master if that's the default).
   - Run `git pull --ff-only`.
   - Remove worktrees using the branch: Run `git worktree list` and parse output to find worktrees on `<branch-name>`, then `git worktree remove <worktree-path>` for each (non-blocking; continue if fails or no worktrees found).
   - Delete branches (run in parallel):
     - Delete local merged branch: `git branch -d <branch-name>`
     - Delete remote merged branch: `git push origin --delete <branch-name>`
   - Remove todo file if was present (non-blocking).
   - Close open PR review comment threads: Use `gh api` to resolve any open review comment conversations on the merged PR (non-blocking; continue if none found).
   - If it is clear what github issue this PR was for (e.g., from branch name or PR title), verify it was closed by the merge. If not, notify the user.

## Arguments (from {{ARGS}})
- `--no-cleanup`: Skip branch deletion (both local and remote).
- `--force-delete`: Force delete local branch even if not fully merged (use `-D` instead of `-d`).

## Error handling
- If PR doesn't exist: abort with "No PR found for current branch '<branch-name>'"
- If merge fails: abort with "Failed to merge PR #<number>. Check the PR status and try again."

## Examples
- `git-pr-merge` → merge last PR for current branch and clean up
- `git-pr-merge --no-cleanup` → merge PR but keep branches
- `git-pr-merge --force-delete` → merge PR and force delete local branch

## Heuristics
- This is a fast, script-like action. Minimal validation, maximum speed.
- Use merge strategy (not squash or rebase) to preserve commit history.
- Clean up both local and remote branches by default for hygiene.
