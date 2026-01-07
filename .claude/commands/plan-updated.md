---
description: Review user-edited plan for contradictions and validate coherence
---

# Plan Updated

Review the user's changes to the plan, check for contradictions between edits and original content, validate coherence, and confirm readiness for approval.

## Behavior

### 1) Determine plan source
Accept either:
- `--file <path>`: Path to plan markdown file (explicit)
- `--issue <number|url>`: GitHub issue number or URL (explicit)
- `<argument>`: Positional argument with smart detection:
  - If argument is purely numeric (e.g., "42"): treat as GitHub issue number
  - If argument contains "github.com": treat as GitHub issue URL
  - Otherwise: treat as todo file name/path
- If no arguments provided, look for recently edited `todo__*.md` files

### 2) Load plan content

**If plan file provided:**
- Use Read tool to load the edited plan from the specified markdown file
- Extract issue number from filename if it matches pattern `todo__<issue-number>.md`

**If issue number/URL provided:**
- Check for local todo file: `todo__<issue-number>.md`
- If local file exists, use it (assumes user edited local file)
- If no local file, fetch from issue comments: `gh issue view <issue> --json number,title,state,body,comments,repository`
- Search comments (newest to oldest) for most recent plan

**If no arguments:**
- List `todo__*.md` files modified in last 24 hours
- If single file found, use it automatically
- If multiple files found, use history context to select one, and verify with the user

### 3) Analyze plan for contradictions

**Priority rule**: User edits always take precedence. Update contradicting parts silently when context clearly indicates user intent.

**If unresolvable contradictions found**:
- Show user the contradictions with specific line references
- Ask user to clarify
- Do not proceed until resolved

### 4) Validate completeness

**Verify open questions handling:**
- If questions have multiple options (A/B/C), verify user has indicated preference
- Check if answers are reflected in the Approach and Steps sections
- If misalignment detected, propose updates to align with answers

**Validate steps:**
- Verify steps align with stated approach
- Confirm dependencies are noted

### 5) Unify language and structure

User edits may have created inconsistencies in language, formatting, or whitespace. Perform minor edits to ensure the final document is readable and well-structured.

### 6) Final coherence pass

Read through entire plan as a human reviewer would:
- Does the plan make sense as a whole?
- Are the steps achievable given the assumptions?
- Does the approach address the open questions (if any were answered)?
- Is the scope clear and reasonable?

### 7) Confirm readiness

**If plan is ready:**
- Summarize key changes user made (brief, 2-3 bullet points)
- Confirm no contradictions remain
- **If `--proceed` flag is set**: Automatically invoke `/plan-ok` to begin implementation
- **If `--proceed` flag is NOT set** (default): State "Plan is ready. Run `/plan-ok` to begin implementation."

**If issues remain:**
- List specific issues by category (Critical/Major/Minor)
- For each issue, provide:
  - Location (section name, line reference if possible)
  - Description of the problem
  - Suggested resolution
- Ask user to address issues before proceeding
- **Never invoke `/plan-ok` if issues remain**, regardless of `--proceed` flag

## Arguments (from {{ARGS}})
- `--file <path>`: Path to plan markdown file (flag form)
- `--issue <number|url>`: GitHub issue number or URL (flag form)
- `--proceed`: If set, automatically run `/plan-ok` when plan is ready (default: False)
- `<argument>`: Positional argument (smart detection):
  - If numeric string (e.g., "42"): treat as GitHub issue number
  - If URL (contains "github.com"): treat as GitHub issue URL
  - Otherwise: treat as todo file name/path
- If no arguments: auto-detect recently edited plan files

## Style
- Concise, actionable feedback
- Reference specific sections when pointing out issues
- Use markdown formatting for clarity:
  - **Bold** for severity levels
  - `Backticks` for section names and code elements
  - Bullet lists for issues and changes
- No time estimates or emojis
- Professional but friendly tone

## Notes
- **User edits have absolute precedence** - AI-generated content is adjusted to match user intent
- Focus on contradictions and coherence, not on perfecting writing style
- Don't be overly pedantic - only flag issues that could cause implementation problems
- Auto-detect plan file when possible to minimize user friction
- If plan is in good shape, confirm quickly - don't create unnecessary work

## Examples
```bash
# Review recently edited plan (auto-detect)
plan-updated

# Review and auto-proceed if ready
plan-updated --proceed

# Review specific plan file (positional)
plan-updated todo__42.md

# Review specific plan file and auto-proceed
plan-updated todo__42.md --proceed

# Review specific plan file (explicit flag)
plan-updated --file todo__42.md

# Review plan for issue (positional)
plan-updated 42

# Review plan for issue and auto-proceed
plan-updated 42 --proceed

# Review plan for issue (explicit flag)
plan-updated --issue 42

# Review plan from issue URL (positional)
plan-updated https://github.com/owner/repo/issues/42
```
