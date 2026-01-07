---
description: Generate implementation plan from GitHub issue or general task
---

# Plan work on a task

Create a concise, implementation-ready plan that a developer can quickly review and hand off to an LLM for execution. DON'T change any existing code.

## Behavior

### Common: Branch Strategy Detection
Before generating plan content, analyze user input for branch strategy:
1. Extract branch name:
   - User-specified via `--branch <name>` flag, OR
   - Auto-generate using pattern: `[feat|develop|fix|chore]/<issue_number>-short-description`
     - `feat`: new features
     - `develop`: development/experimental work
     - `fix`: bug fixes
     - `chore`: maintenance, refactoring, docs
2. Detect worktree preference:
   - **Default**: work in worktree (unless `--no-tree` specified)
   - Check for `--tree` flag (explicit worktree request)
   - Look for contextual indicators in prompt that suggest not using worktree
3. Determine whether to include Branch Strategy section:
   - **If branch name can be determined and worktree preference is clear**: Include "Branch Strategy" section at beginning of plan with branch name and worktree decision
   - **If branch name pattern unclear or worktree preference ambiguous**: Omit Branch Strategy section and add Open Question Q0 asking about branch name pattern and worktree preference with options A/B/C and implications

### Issue Mode
If `--from-issue <number|url>` is provided:
1. Fetch issue and repo data: `gh issue view <issue> --json number,title,state,body,comments,repository`
   - If authentication fails, handle error and attempt to authenticate
2. Verify issue is open. Abort if closed.
3. Add "planning" label to issue: `gh issue edit <issue-number> --add-label "planning"` (non-blocking; continue if fails).
4. **Check for existing plan**:
   - Search issue comments (newest to oldest) for existing plan. Plan comment typically contains sections: "## Title", "## Assumptions", "## Open Questions", "## Steps"
   - **If plan found in comments**:
     - Inform user: "Found existing plan in issue comments. Copying to todo file..."
     - Copy complete plan content
     - Collect subsequent comments referencing open questions (look for "Q1:", "Q2:", "A:", "B:", "C:" patterns)
     - Write plan to `todo__<issue-number>.md` with copied content
     - If question-related comments found, append "## Comments on Open Questions" section
     - **Do not regenerate or rethink** - just copy and format
     - Confirm: "Plan copied to todo__<issue-number>.md with N comment(s) on open questions"
     - Exit after writing file
   - **If no plan in comments**, check for existing `todo__<issue-number>.md` file:
     - If exists, inform user and ask whether to regenerate or keep existing
     - If user wants to keep existing, exit
5. **Only if no existing plan found**: Analyze issue content (title, description, comments, dependencies, affected components)
6. Generate plan following Plan Structure below
7. **CRITICAL**: Use Write tool to create `todo__<issue-number>.md` with complete plan content. File path must be absolute. Never skip this step.

### General Mode
If not in issue mode:
1. First argument must be output file path
2. Use entire project as context
3. Generate plan following Plan Structure below
4. **CRITICAL**: Use Write tool to create specified output file with complete plan content. File path must be absolute. Never skip this step.

### Post-Generation
After generating plan, if Steps section includes sub-issues:
- Ask user to create them on GitHub
- If confirmed, run `gh issue create` for each
- Update plan file with actual issue numbers (replace `#<ISSUE_NUMBER>` placeholders)

## Arguments (from {{ARGS}})
- `<output-file>`: Output file path (required in general mode)
- `--from-issue <number|url>`: Generate plan from GitHub issue (writes to `todo__<issue-number>.md`)
- `<issue>`: Positional issue identifier (alternative to --from-issue)
- `--tree`: Explicitly work in git worktree (default behavior)
- `--no-tree`: Disable worktree, work in main repo
- `--branch <name>`: Specify custom branch name (overrides auto-generation)

## Style
- Expert audience: crisp, skimmable
- Bullet lists over paragraphs
- Backticks for code elements: `file.py`, `function()`, `ClassName`
- LLM-optimized: deterministic, explicit, no pronouns
- Numbered flat lists over nested bullets
- No time estimates or emojis
- Sub-issues: basic markdown only (headings, bullets, backticks, links) for `gh issue create` compatibility

## Plan Structure

Required sections:
1. **Title**: one-line goal statement. The nature of the task should be immediately obvious from the title. Good title "Multi-worker deployment (#311)". Bad title: "Implementation Plan: Issue #311"
2. **Branch Strategy** (if specified): Branch name and worktree decision. Omit if not specified - capture as Open Question Q0 instead.
3. **Issue Summary** (issue mode only): brief description from GitHub issue
4. **Assumptions**: key assumptions that materially affect scope or design
5. **Open Questions**: Think hard about what's unclear or ambiguous. **If branch strategy not specified, add Q0 about branch name and worktree preference with options A/B/C and implications**. Continue with Q1, Q2, ... for other questions. For each question provide up to three possible reasonable answers (A, B, C). **For each option, provide a short description (1-2 sentences) of its implications** including impact on complexity, performance, maintainability, or other relevant factors. It's OK not to ask anything. If no questions after careful consideration, write "No questions".
6. **Approach**: rationale, alternatives briefly noted
7. **Steps**: Think hard and produce numbered, outcome-focused. For complex tasks, break into sub-issues. If issue number is known, add "Related to #<ISSUE_NUMBER>" line at the end of each step.

Optional sections (add only if they reduce ambiguity or risk):
8. **Scope and Non-Goals**: inclusions and explicit exclusions
9. **Requirements and Constraints**: functional, performance, security, compatibility
10. **Risks & Mitigations**: top risks with practical mitigations
11. **Dependencies**: code, data, services; note ownership/availability
12. **Verification & Acceptance Criteria**: tests, success metrics
13. **Deliverables**: artifacts to produce
14. **Rollout & Backout**: release steps, monitoring, rollback

## LLM-Friendliness
- Stable section headers, no "above/below" references
- Explicit entity references (files, functions, data)
- Specify inputs, outputs, constraints with limits when relevant
- Provide schema and example when structure matters
- Deterministic, idempotent steps
- Consistent terminology

## Examples
```bash
# General planning
plan output.md add cancel button to the home page

# Issue-based planning (worktree is default)
plan --from-issue 42                                    # writes to todo__42.md, auto-generates branch like feat/42-add-auth
plan 42                                                 # same (positional)
plan --from-issue 42 --no-tree                         # work in main repo instead
plan --from-issue 42 --branch feat/custom-feature      # specify custom branch name
plan 42 --branch fix/42-validation-bug                 # custom branch with fix prefix
```

## File Writing Requirements
**MANDATORY**: Every execution must end with Write tool call:
- Issue mode: Write to `todo__<issue-number>.md` in current directory (`pwd`)
- General mode: Write to specified output file path
- Use absolute paths (resolve relative paths to absolute)
- Overwrite existing files without asking
- Confirm file creation by showing file path to user
- **IMPORTANT**: Even if work will be done in a worktree, the todo file is always created in `pwd`, NOT in the worktree directory

## Notes
- **Optimization**: Copy existing plans instead of regenerating (from issue comments or todo file). Preserves original structure and saves time
- When copying existing plan from comments, collect and append comments addressing open questions
- Output file always required in general mode
- Issue mode: use only git/gh commands, focus on planning not implementation
- Honor compact output requests while preserving structure
- Ensure valid Markdown with proper heading hierarchy
- Avoid bold, italic, underline, emojis unless absolutely necessary
