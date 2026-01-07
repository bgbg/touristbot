---
description: Read and analyze code review comments, grouped by severity
---

# Code Review

Read code review comments from the current PR (or specified PR), analyze them, and provide grouped feedback by severity. Simple and fast. **Do not edit code** - only summarize findings and ask the user what to do next.

## Behavior

1) Detect PR
   - If `--pr <number>` provided, use that PR number.
   - Otherwise, use the context.
   - If no context, detect current branch's PR: `gh pr view --json number,url,state,headRefName`.
   - If no PR found, abort with clear message.
   - If PR is closed/merged, still proceed (reviews may still be useful).

1a) (Optional) if user asked to sleep (--sleep 5), sleep that amount of MINUTES before proceeding. Default: don't sleep.
   - If sleep is requested, print a timestamped message showing when sleep started and the target duration
   - Sleep intelligently: check every minute if code reviews exist
   - If reviews are found during sleep period, immediately stop sleeping and proceed
   - If no reviews found after full sleep duration, proceed to fetch anyway
   - Print status update each minute: "Sleep check X/Y: [reviews found | no reviews yet]"
   - If sleep is not requested, skip this step entirely


2) Fetch review comments (single GraphQL query)
   - Execute single GraphQL query via `gh api graphql` to fetch:
     - PR reviews (state, author, body, submittedAt)
     - Review comments (path, line, body, author, createdAt)
     - Review threads grouped by path
   - Query filters out PENDING reviews server-side.
   - Parse JSON response to extract all review data.
   - If no review is found, and there is a --retry flag, wait a bit and try again. Waiting time is 3 minutes by default, unless --sleep is provided. Retry only once. If no review is found after the retry, abort with a message that no reviews were found.

3) Analyze and group by severity
   - **Critical**: Security issues, breaking changes, data loss risks, exception swallowing, missing error handling
   - **High**: Logic errors, performance issues, missing tests, API contract violations, incorrect assumptions
   - **Medium**: Code style, refactoring opportunities, documentation gaps, minor bugs, edge cases
   - **Low**: Nitpicks, formatting, naming suggestions, optional improvements
   - **Questions**: Clarifications, "why" questions, discussion points

4) Output
   - Print PR URL and basic stats (review count, comment count, reviewers)
   - Group feedback by severity with clear headers
   - For each comment: show reviewer, file/line context, and the comment text
   - Provide summary counts per severity level
   - Keep output concise and actionable
   - **Do not edit code** - only summarize findings
   - After summarizing, ask the user what they want to do next (e.g., address specific issues, create fixes, etc.)

## Arguments (from {{ARGS}})
- `--pr <number>`: Specify PR number explicitly. If not provided, detect from current branch.

## Heuristics
- Prefer fast execution: single GraphQL query fetches all review data efficiently
- If no reviews/comments exist, report that clearly
- Group similar comments together when they appear on the same file/area
- Extract actionable items from discussion threads

## Examples
- `gh-code-review` → analyze reviews for current branch's PR
- `gh-code-review --pr 123` → analyze reviews for PR #123
- `gh-code-review https://github.com/bgbg/tvunah_gap_analysis/pull/211` → analyze reviews for PR #211
- `gh-code-review --sleep 5` → sleep for 5 minutes before analyzing reviews
