---
description: Plan is approved and ready to start work
---

# Plan OK

Start implementing the plan, adhering to the plan and the user's instructions.

## Behavior

### 1) Determine plan source
Accept either:
- `--file <path>`: Path to plan markdown file (explicit)
- `--issue <number|url>`: GitHub issue number or URL (explicit)
- `<argument>`: Positional argument with smart detection:
  - If argument is purely numeric (e.g., "42"): treat as GitHub issue number
  - If argument contains "github.com": treat as GitHub issue URL
  - Otherwise: treat as todo file name/path
- If no arguments provided, ask user for plan source

### 2) Fetch plan content

**If plan file provided:**
- Use Read tool to load plan from the specified markdown file
- Extract issue number from filename if it matches pattern `todo__<issue-number>.md`
- If no issue number found in filename, ask user for the associated GitHub issue number

**If issue number/URL provided:**
- Fetch issue with comments: `gh issue view <issue> --json number,title,state,body,comments,repository`
- Do not check for GitHub authentication beforehand. If authentication fails, handle the error and attempt to authenticate.
- Verify issue is open. Abort if closed.
- Search comments (from newest to oldest) for plan content. A plan comment typically contains markdown sections like "## Title", "## Assumptions", "## Open Questions", "## Steps", etc.
- If no plan found in comments, abort and inform user that no plan exists for this issue yet.

### 3) Parse and validate plan

**Extract branch strategy:**
- Look for "## Branch Strategy" section or branch information in the plan
- Extract branch name and worktree preference
- If branch strategy information is missing or unclear, check "## Open Questions" for Q0 about branch strategy
- **If branch strategy is not specified and not in open questions, abort with message**: "Cannot proceed - plan must specify branch name and worktree preference"

**Extract open questions:**
- Look for "## Open Questions" section in the plan
- If section says "No questions", proceed to step 4
- If section contains numbered questions (Q1, Q2, etc.), extract all questions

**Verify questions are answered:**
- If plan source is **issue comments**:
  - Search subsequent comments (after the plan comment) for answers to open questions
  - Look for explicit references like "Q1:", "Question 1:", or "A:", "B:", "C:" selections
  - For each unanswered question with multiple options, list it and abort with message: "Cannot proceed - open questions remain unanswered in GitHub issue"
  - If all questions have single option only, consider them resolved and proceed automatically

- If plan source is **plan file**:
  - Check if all questions have only single option (A) - if so, consider them resolved and proceed automatically
  - If any question has multiple options (A/B/C), present those questions to user
  - Ask user to confirm questions have been resolved or to provide answers
  - If user indicates questions are not resolved, abort

- Check for contradictions:

  - If the plan of actions contradicts the answers to the open questions, the answers have precedence. Change he plan and start working
  - If two answers contradict each other, ask the user to resolve the contradiction
  - If the plan contains other contradictions, show them to the user and abort


### 4) Post plan to GitHub
- Update issue labels: `gh issue edit <issue-number> --add-label "work-in-progress" --remove-label "planning"`
  - This command adds `work-in-progress` and removes `planning` in a single operation
  - If `planning` label doesn't exist, GitHub CLI will handle it gracefully (the command succeeds, only the removal is skipped)
  - Continue even if label operations fail (non-blocking)
- Post plan as comment to issue: `gh issue comment <issue-number> --body "<plan-content>"`
  - Include the branch name and worktree path in the comment.
  - Use heredoc for proper formatting of multi-line plan content
  - Do not include any signature lines (e.g., `Signed-off-by`)


### 5) Setup branch and worktree
Using the branch strategy extracted in step 3:

**If worktree is required:**
1. Check if worktree already exists: `git worktree list`
2. If worktree exists for this branch, switch to it
3. If worktree doesn't exist:
   - Create worktree directory path: `.trees/<branch-name>` or similar
   - Create worktree with new branch: `git worktree add <path> -b <branch-name>`
   - If branch already exists remotely, use: `git worktree add <path> <branch-name>`
4. Change to worktree directory: `cd <worktree-path>`
5. Confirm working location to user

**If working in project directory (no worktree):**
1. Check if branch exists: `git branch --list <branch-name>`
2. If branch exists locally:
   - Switch to branch: `git checkout <branch-name>`
3. If branch doesn't exist locally but exists remotely:
   - Checkout remote branch: `git checkout -b <branch-name> origin/<branch-name>`
4. If branch doesn't exist at all:
   - Create new branch: `git checkout -b <branch-name>`
5. Confirm working location to user

### 6) Work
 - Start implementing the plan, step by step.
 - If possible, test your changes as you go, don't wait for the end of the plan to test. Fix errors as you go.
 - From time to time, when it makes sense (for example, after completing a step, or after a significant milestone), mark completed and partially completed steps as such, commit the changes to the branch and push them.
 - If there are tasks that require user's intervention, ask them to review the plan and adjust if needed.


### 7) Final step
- Run `/git-pre-pr` to perform pre-PR checks


## Arguments (from {{ARGS}})
- `--file <path>`: Path to plan markdown file (flag form)
- `--issue <number|url>`: GitHub issue number or URL (flag form)
- `<argument>`: Positional argument (smart detection):
  - If numeric string (e.g., "42"): treat as GitHub issue number
  - If URL (contains "github.com"): treat as GitHub issue URL
  - Otherwise: treat as todo file name/path
- If no arguments: prompt user for plan source

## Notes
- **Automation**: Minimize user interaction. Proceed automatically when:
  - No open questions exist in plan
  - All open questions have single option only
  - Only ask for user confirmation when questions have multiple unanswered options
- Assume `gh` commands will work correctly - don't try to authenticate beforehand
- If authentication fails, handle error and attempt to authenticate
- Use heredoc format for multi-line content: `gh issue comment <issue> --body "$(cat <<'EOF'\n<content>\nEOF\n)"`
- Abort early if open questions with multiple options are unanswered
- Always verify issue is open before proceeding
- **Final action**: Always run `/git-pre-pr` after completing all tasks

## Examples
```bash
# From plan file (positional - smart detection)
plan-ok todo__42.md

# From plan file (explicit flag)
plan-ok --file todo__42.md

# From issue number (positional - smart detection)
plan-ok 42

# From issue number (explicit flag)
plan-ok --issue 42

# From issue URL (positional - smart detection)
plan-ok https://github.com/owner/repo/issues/42

# From issue URL (explicit flag)
plan-ok --issue https://github.com/owner/repo/issues/42
```
