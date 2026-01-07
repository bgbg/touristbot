---
description: Perform post-incident analysis on bugs and provide prevention recommendations
---

# Postmortem Analysis

Perform systematic post-incident analysis on resolved bugs by examining the issue, related PRs, code changes, and review comments to provide actionable prevention recommendations and lessons learned.

## Behavior

1) Parse input
   - **REQUIRED**: Accept positional argument: issue number/URL OR PR number/URL (but not both as positional)
   - If argument looks like issue: `<number>` or `github.com/.../issues/<number>` - treat as issue
   - If argument looks like PR: `github.com/.../pull/<number>` or explicit `--pr` flag - treat as PR
   - If no argument provided: abort with error message explaining usage
   - Accept optional `--pr <number|url>` flag to explicitly specify PR(s) when analyzing an issue
   - Accept optional `--issue <number|url>` flag to explicitly specify the issue when analyzing a PR
   - Accept optional `--fast` flag to analyze only the primary PR (when analyzing issue)
   - Accept optional `--deep` flag to force detailed diff analysis regardless of PR size
   - Validate numbers are numeric and non-zero

2) Fetch issue data
   - Execute: `gh issue view <issue> --json number,title,body,comments,state,closedAt,closedByPullRequestsReferences`
   - Parse JSON response to extract:
     - Issue title and description
     - All comments (chronological order)
     - Close date and state
     - PRs that closed the issue (from closedByPullRequestsReferences)
   - Handle errors:
     - Issue not found: abort with clear message
     - Auth errors: prompt to run `gh auth login`
     - Network errors: suggest retry

3) Discover related PRs
   - If `--pr` flag provided: use specified PR number(s)
   - Otherwise, auto-discover PRs:
     - Primary source: `closedByPullRequestsReferences` from issue data (most reliable)
     - Fallback: `gh pr list --search "fixes #<issue>" --state merged --json number,url,title,mergedAt`
     - If multiple PRs found and `--fast` flag set: use only the first (most recent)
     - If multiple PRs found and `--fast` not set: analyze all PRs
     - If no PRs found: proceed with issue-only analysis (limited scope)

4) Fetch PR data for each discovered PR
   - Execute: `gh pr view <pr> --json number,title,body,comments,files,commits,additions,deletions,changedFiles,reviews`
   - Parse JSON response to extract:
     - PR title, description, and discussion comments
     - Files changed count, lines added/deleted
     - Commit messages (for understanding implementation approach)
     - Review comments and feedback
   - Fetch full diff: `gh pr diff <pr>`
   - Determine analysis depth:
     - If `--deep` flag set: always do detailed analysis
     - If changed files > 20 OR total changes > 500 lines: summary-level only (with note)
     - Otherwise: detailed diff analysis

5) Analyze issue and PR data
   - **Research phase**: If analysis would benefit from additional context (e.g., understanding a library, framework feature, or error pattern), use WebSearch tool to gather relevant information
   - **Root Cause Analysis**:
     - What went wrong? (from issue description)
     - Why did it happen? (identify missing safeguards, edge cases, assumptions)
     - When was it discovered? (production, testing, code review)
   - **Fix Analysis**:
     - How was it fixed? (summarize approach from PR)
     - What changed? (files, functions, logic)
     - Review feedback themes (from PR comments)
   - **Pattern Detection** (from diff, if detailed analysis):
     - Error handling added/improved
     - Validation or type safety additions
     - Test coverage added
     - Edge case handling
     - Database/migration changes

6) Generate Prevention Recommendations
   - **IMPORTANT**: Only provide recommendations that are genuinely warranted based on the root cause analysis
   - Do NOT recommend for the sake of recommending - if the issue was a simple oversight or one-time mistake with no systematic prevention needed, say so
   - Based on root cause, suggest specific preventive measures ONLY when they would have actually prevented this issue:
     - **Validation**: Input validation, boundary checks, type safety (only if missing validation caused the issue)
     - **Testing**: Unit tests, integration tests, edge case coverage (only if lack of tests allowed the bug)
     - **Monitoring**: Health checks, alerting, logging (only if better monitoring would have caught it earlier)
     - **Documentation**: Update runbooks, architecture docs, API contracts (only if missing/unclear docs contributed)
   - Make recommendations actionable (specific files, functions, or processes to modify)
   - Group by category for clarity
   - If no systematic improvements are needed, state: "No systematic prevention measures needed - this was an isolated issue"

7) Generate Takeaways
   - Extract key lessons from the incident:
     - What patterns emerged?
     - What worked well in the detection/fix process?
     - What could apply to other areas of the codebase?
   - Keep takeaways concise and memorable

8) Generate Future Changes
   - Suggest improvements to:
     - **Process**: Code review checklists, testing requirements, deployment procedures
     - **Tooling**: Linters, pre-commit hooks, CI/CD checks, monitoring dashboards
     - **Documentation**: Standards, guides, onboarding materials
   - Prioritize high-impact, low-effort changes
   - Provide examples where applicable

9) Format and output analysis
   - Structure as markdown with clear sections:
     ```
     # Postmortem: <Issue Title>

     **Issue**: #<number> - <title>
     **Status**: <state> (closed <date>)
     **Related PRs**: #<pr1>, #<pr2>, ...

     ## Summary
     <Brief description of the problem>

     ## Root Cause
     <What went wrong and why>

     ## Fix Analysis
     <How it was fixed>
     <Files changed>
     <Key changes>

     ## Prevention
     <What could have prevented this>
     - **Validation**: ...
     - **Testing**: ...
     - **Monitoring**: ...
     - **Documentation**: ...

     ## Takeaways
     <Key lessons learned>

     ## Future Changes
     - **Process**: ...
     - **Tooling**: ...
     - **Documentation**: ...
     ```
   - If PR analysis was summary-level only (large PR), add note:
     ```
     **Note**: Diff analysis limited to summary due to PR size (N files, M lines changed).
     Use `--deep` flag for detailed code analysis.
     ```
   - Output to terminal (do not create files)

10) Prompt for follow-up actions
    - After analysis, ask user:
      - "Would you like to create follow-up issues for these recommendations?"
      - If yes, help user create issues with pre-filled titles/descriptions

## Arguments (from {{ARGS}})
- `<issue|pr>`: Required. Issue number/URL OR PR number/URL to analyze
- `--pr <number|url>`: Optional. Explicitly specify PR(s) when analyzing an issue (comma-separated for multiple)
- `--issue <number|url>`: Optional. Explicitly specify the issue when analyzing a PR
- `--fast`: Optional. Analyze only the primary PR instead of all related PRs (issue analysis only)
- `--deep`: Optional. Force detailed diff analysis even for large PRs

## Error Handling
- No argument provided: Abort with usage message "Usage: /postmortem <issue|pr> [--pr NUM] [--issue NUM] [--fast] [--deep]"
- Issue not found: Clear error message with issue number
- PR not found: Clear error message with PR number
- No PRs found (when analyzing issue): Proceed with issue-only analysis (note limited scope)
- Auth failure: Prompt to run `gh auth login`
- Network errors: Suggest retry
- Invalid PR number: Skip invalid PR, continue with others

## Examples
```bash
# Analyze issue #400 (auto-discover all related PRs)
/postmortem 400

# Analyze issue with full URL
/postmortem https://github.com/owner/repo/issues/400

# Analyze PR #401 directly
/postmortem 401 --issue 400
# OR with full URL
/postmortem https://github.com/owner/repo/pull/401

# Analyze issue #400 with specific PR
/postmortem 400 --pr 401

# Fast analysis (primary PR only)
/postmortem 400 --fast

# Deep analysis (detailed diff for large PRs)
/postmortem 400 --deep

# Analyze multiple specific PRs for an issue
/postmortem 400 --pr 401,402,403

# No argument - will show error
/postmortem
# Error: Usage: /postmortem <issue|pr> [--pr NUM] [--issue NUM] [--fast] [--deep]
```

## Notes
- Command requires either an issue or PR as input - will not proceed without one
- Command focuses on completed incidents (closed issues with merged PRs)
- Analysis quality depends on issue/PR description quality
- Use WebSearch when additional context would improve analysis (library docs, error explanations, etc.)
- Recommendations should only be provided when genuinely warranted - avoid recommending for the sake of it
- If no systematic improvements are needed, explicitly state that it was an isolated issue
- User controls follow-up issue creation
- Large PRs default to summary-level analysis for performance
