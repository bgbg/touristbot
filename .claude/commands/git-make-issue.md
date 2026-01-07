---
description: Generate clear GitHub issue title and description, then create it
---

# Git Make Issue

Generate a clear GitHub issue title and description, confirm, then create it.

## Behavior
1) Input handling:
   - If `--body` provided: use it as the issue prompt.
   - Otherwise: ask for a brief problem description.
2) Generate:
   - Title: descriptive, specific.
   - Description: concise, clear, no emojis.
   - If `--propose-labels`: propose a short list of labels (3 max).
3) Confirm:
   - Show title, description, and any proposed labels; allow edits and ask to proceed.
   - If `--no-confirm`, proceed automatically with the generated title, description, and proposed labels.
4) Create:
   - Create the issue via `gh issue create` with title and body.
   - If labels were proposed (and not removed during confirm), pass them to `gh issue create` as `--label` values.

## Arguments (from {{ARGS}})
- `--repo <owner/repo>`: Target repository (defaults to current repo).
- `--body <text>`: Use provided text as source material.
- `--no-confirm`: Skip confirmation prompt and create immediately.
- `--propose-labels`: Propose labels for the issue and apply them on create unless removed.

## Notes
- No milestones or assignees unless specifically requested. Labels are only added when `--propose-labels` is used (and confirmed or auto-applied with `--no-confirm`).
