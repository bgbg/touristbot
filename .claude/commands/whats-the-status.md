# Project Status Report: Branches vs Todo Files

Analyze git branches/worktrees and todo files to report development status.

## Inputs
- Optional: `<todo_file>` or `<branch_name>` to analyze specific item only

## Analysis Steps

1. **Discover branches and worktrees**
   - List all git branches
   - List all git worktrees
   - Treat worktrees as regular branches for reporting

2. **Discover todo files**
   - Find all `todo__*.md` files in project root
   - Extract issue numbers from filenames (pattern: `todo__<number>.md`)

3. **Correlate branches with todo files**
   - Match branches to todo files using issue numbers
   - Branch pattern: `<prefix>/<number>-<description>` where `<number>` matches todo file

4. **Analyze each matched pair** (todo file + branch)
   - Read todo file plan
   - Review branch commit history (`git log`)
   - Compare branch code, commit history vs todo plan steps
   - Summarize: completion status, pending items, deviations

5. **Check merge status**
   - Determine if branch is merged into `main`
   - For merged branches: recommend removal

6. **Report orphaned items**
   - Todo files without corresponding branches: ask user for action (delete or other)
   - Branches without corresponding todo files: report as orphaned

7. **Update todo files**
   - if the user asked to update todo file(s) either by context or using --update-todo flag, update the todo file(s) with the current status of the branch(es) and the todo plan steps.
   - the todo file(s) should be updated with by marking the completed, partially completed and not started steps as such using emojis.

## Output Format

Compact report with sections:

### Active Development
- `<branch>` ↔ `<todo_file>`: brief status, completion summary

### Merged (Can Remove)
- `<branch>` ↔ `<todo_file>`: merged into main

### Orphaned Todo Files
- `<todo_file>`: no corresponding branch found, action needed?

### Orphaned Branches
- `<branch>`: no corresponding todo file

## Notes
- Issue numbers in branch names and todo filenames must match for correlation
- Analysis compares todo plan steps against actual branch commits and code changes
- Only check merge status against `main` branch
