---
description: Execute the macOS 'say' command to speak text aloud
---

# Say Command

Execute the macOS `say` command to speak the provided text aloud.

## Behavior

When invoked with `/say <text>`, extract the text from the command arguments and execute:
```bash
say "<text>"
```

The text should be passed directly to the `say` command. If no text is provided, inform the user that text is required.

## Examples

- `/say Hello, world!` - Speaks "Hello, world!"
- `/say Task completed` - Speaks "Task completed"
- `/say Testing one two three` - Speaks "Testing one two three"

## Notes

- Works on macOS systems only (requires macOS `say` command)
- Text is passed as a single argument to `say`
