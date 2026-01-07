---
description: Create a well-formed GitHub Pull Request with auto-generated title and body
---

# Git PR

Create a well-formed GitHub Pull Request for the current project, ensuring the branch is pushed, metadata is set (title, body, reviewers, labels), and handling forks/drafts intelligently.

## Behavior
1) Ensure remote and push (attempt fast path)
   - Attempt `git push -u origin <branch>` if no upstream; otherwise `git push`.
   - On failure:
     - If behind: print actionable hint to run `git pull --rebase` and retry.
     - If no upstream: suggest `git push -u origin <branch>` and retry after user action.
     - If working tree is dirty or hooks fail: show exact git error and stop without masking it.

2) If asked to detect existing PR (best-effort) (default: disabled)
   - Query `gh pr view --json number,state,url,headRefName,baseRefName,isDraft` for the branch.
   - If an open PR exists and is not draft, print URL and exit.
   - If an open PR exists and is draft, note it for later processing and continue to step 3.
   - If this lookup errors (e.g., no PR found, fork nuance), proceed to create a PR.

3) Title and body generation
   - Generate title:
     - Use last commit subject from `git log -1 --pretty=%s`
     - If branch name matches pattern `feature/123-foo` or `fix/456-bar`, extract issue number for later use
   - Generate body:
     - Concatenate all commit messages between `<base>..HEAD` using `git log --pretty=%B`
     - Never include emojis or `Signed-off-by` or any signature lines in the PR body.
     - **CRITICAL - Issue linking**: The PR body MUST include `Closes #<issue-number>` footer:
       - If `--issues` parameter provided: add `Closes #<number>` for each issue
       - Otherwise, infer issue number from branch name (e.g., `feature/123-add-auth` → `Closes #123`)
       - If no issue number can be determined, ask once whether to proceed without an issue link; abort if declined.

4) Create PR (bias for action)
   - Execute `gh pr create` with generated `--title`, `--body`, `--base` (from argument or default to 'main'). Set `--head` for forks if needed.
   - On failure, surface the exact `gh` error; suggest likely next steps (e.g., set upstream, authenticate, fix insufficient scopes) and stop.
   - Print resulting PR URL.

5) Post-create actions (run in parallel where possible)
   - If an existing draft PR was detected in step 2, remove draft status with `gh pr ready` and print updated URL.
   - If readying fails (e.g., permissions), show the error and keep the PR as-is.
   - Remove `work-in-progress` and/or `planning` label from linked issue(s):
     - Execute `gh issue edit <issue-number> --remove-label "work-in-progress"`
     - If no issue is linked or removal fails, log the error but continue (non-blocking)
     - Run this in parallel with PR ready operation when both apply
   - If `--comment` flag provided, add a summary comment to the linked issue(s):
     - Generate a very concise summary of changes from commit messages, without calling any tools
     - Post via `gh issue comment <issue-number> --body "<summary>"`
     - Include a link back to the created PR
     - If no issue is linked or comment fails, log the error but continue (non-blocking)

## Arguments (from {{ARGS}})
- `--issues "123,456"`: Explicitly specify issue numbers to close (adds `Closes #<number>` footers to PR body). If not provided, the command will try to infer the issue number from the branch name pattern (e.g., `feature/123-add-auth` → issue #123).
- `--comment`: Add a summary comment to linked issue(s) with PR details. (default: skip)
- `--base "<branch>"`: Target branch to merge into. (default: main)
  - Most PRs target `main` (feature development)
  - PRs targeting `staging` or `prod` are rare (only for fixes in those branches)
  - Normal workflow: features merge to main, then forward merge main → staging → prod

## Heuristics
- Prefer optimistic execution; let git/gh errors drive remediation.
- If an open PR already exists, avoid duplicate creation and exit early.
- Never swallow errors; print them verbatim and stop with clear next steps.

## Examples
- `git-pr` → create PR from current branch to main, auto-generate title/body, print URL.
- `git-pr --base "develop"` → create PR targeting the develop branch instead of main.
- `git-pr --issues "123,456"` → create PR closing issues #123 and #456.
- `git-pr --comment` → create PR and post summary comment to linked issue(s).
- `git-pr --base "staging" --issues "789" --comment` → create PR to staging branch, closing issue #789, with summary comment.
