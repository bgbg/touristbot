# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a minimal Python project currently containing a single starter script (`main.py`). The repository uses PyCharm as the IDE (based on `.idea/` configuration).

## Development Setup

The project uses a Python virtual environment stored at `.venv/`, which is also configured as the VS Code interpreter for this workspace.

To set up the development environment:
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Linux/Mac
# or: .venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

In VS Code, select the interpreter at `.venv/bin/python` (or `.venv\Scripts\python.exe` on Windows) for linting, running, and debugging.

## Running Code

Currently, the main script can be run with:
```bash
python main.py
```

## Project Structure

- `gemini/` - Main package with core functionality
- `tests/` - Test suite organized to mirror source structure
- `pytest.ini` - pytest configuration
- `.idea/` - PyCharm IDE configuration files

## Testing

- Preferred framework: pytest.
- Skipping tests is not allowed. Mark tests for retry if needed, but never skip.
- Failing tests are never acceptable. If a test fails when you run the suite, either fix it or alert the user and ask how to proceed.
