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

- `main.py` - Main entry point with sample code
- `.idea/` - PyCharm IDE configuration files

## Notes

This is a new repository with minimal structure. As the project grows, consider adding:
- `requirements.txt` or `pyproject.toml` for dependency management
- Testing framework (pytest, unittest)
- Project-specific modules and packages
- Documentation as the codebase expands