# Writing Cross-Platform Skills for the Skills Hub

A comprehensive guide to authoring GitHub Copilot (GHCP) skills that run on both **Windows (PowerShell)** and **Linux/macOS (Bash)** using the Skills Hub framework.

---

## Table of Contents

**Building a New Skill (Step-by-Step)**

1. [Overview](#overview)
2. [Skill Anatomy — Required & Optional Files](#skill-anatomy)
3. [Step 1: Create the Skill Directory](#step-1-create-the-skill-directory)
4. [Step 2: Write SKILL.md (The Skill Contract)](#step-2-write-skillmd)
5. [Step 3: Write config.json (Metadata & Environment)](#step-3-write-configjson)
6. [Step 4: Implement the Python Entry Point](#step-4-implement-the-python-entry-point)
7. [Step 5: Declare Dependencies in requirements.txt](#step-5-declare-dependencies)
8. [Step 6: Cross-Platform Execution via run-skill Scripts](#step-6-cross-platform-execution)

**Deep Dives & Advanced Topics**

9. [Environment Configuration In Depth](#environment-configuration-in-depth) — environment types, per-skill isolation
10. [Configuration Inheritance (Hub → Skill Merge)](#configuration-inheritance)
11. [Non-Python Skills](#non-python-skills)

**Practical Guides**

12. [Best Practices & Checklist](#best-practices--checklist)
13. [Complete Worked Example](#complete-worked-example) — building a Word-Count skill from scratch
14. [Converting an Existing Skill to Cross-Platform](#converting-an-existing-skill-to-cross-platform) — migrating a Windows-only skill

**Reference**

15. [Troubleshooting](#troubleshooting)
16. [Quick Reference Card](#quick-reference-card)
17. [Available Skills Catalog](#available-skills-catalog) — all skills in the hub with descriptions, versions, and environments

---

## Overview

The **Skills Hub** is a centralized distribution framework for GHCP skills. It provides:

- **Shared runner scripts** (`run-skill.ps1` / `run-skill.sh`) that handle Python environment activation, config merging, and skill execution on any platform.
- **Configuration inheritance** — skills inherit safe defaults from the hub and only override what they need.
- **Automatic dependency management** — `requirements.txt` is installed into the active Python environment during download.
- **Version-based update detection** — the hub compares `metadata.version` in `config.json` to decide whether to update a skill.

A cross-platform skill is one that can be invoked identically on Windows, Linux, and macOS without the user (or the AI agent) needing to write different logic per OS. You achieve this by delegating all platform-specific work to the shared runner scripts.

### Architecture at a Glance

```
Skills Repository (network share or local folder)
├── skills-hub/              ← Framework: runners, hub config, manager scripts
│   ├── run-skill.ps1        ← Windows runner
│   ├── run-skill.sh         ← Linux/macOS runner
│   ├── skills_hub.ps1       ← Hub manager (Windows)
│   ├── skills_hub.sh        ← Hub manager (Linux)
│   └── config.json          ← Hub-level defaults
│
├── My-Skill/                ← Your skill
│   ├── SKILL.md             ← AI instructions (required)
│   ├── config.json          ← Metadata & env overrides (recommended)
│   ├── requirements.txt     ← Python dependencies (if any)
│   └── main.py              ← Entry point
└── ...
```

When a skill is installed into a workspace it lands in `.claude/skills/<Skill-Name>/`, and the runner scripts live alongside it at `.claude/skills/skills-hub/`.

---

## Skill Anatomy

| File | Required | Purpose |
|------|----------|---------|
| `SKILL.md` | **Yes** | The AI-facing contract: frontmatter metadata, when to invoke, how to run, arguments, examples |
| `config.json` | Recommended | Metadata (`name`, `version`, `description`), `activeEnvironment` selection, optional environment overrides |
| `requirements.txt` | If Python deps | Standard pip requirements — installed automatically during download |
| `main.py` (or any `.py`) | If Python skill | The entry-point script executed by the runner |
| Other files | Optional | Helper modules, data files, `.env` templates, etc. |

---

## Step 1: Create the Skill Directory

Create a folder whose name becomes the skill identifier. Use **PascalCase-with-Hyphens** to match existing conventions:

```
skills/
└── My-Cool-Skill/
    ├── SKILL.md
    ├── config.json
    ├── requirements.txt
    └── main.py
```

> **Naming convention**: The folder name should match `metadata.name` in `config.json` and the `name` field in the SKILL.md frontmatter.

---

## Step 2: Write SKILL.md

SKILL.md is the **most important file**. It tells the AI agent (GitHub Copilot) *when* to invoke your skill and *exactly how* to run it on every platform.

### 2.1 Frontmatter

The YAML frontmatter between `` ```skill `` fences and `---` delimiters is what Copilot uses for skill discovery:

`````markdown
````skill
---
name: My-Cool-Skill
description: Does something useful. Use this skill when the user asks to
             "do X", "perform Y", or "compute Z".
---
````
`````

| Field | Description |
|-------|-------------|
| `name` | Unique skill identifier (matches folder name) |
| `description` | One or two sentences. **Include trigger phrases** ("Use this skill when the user asks to…") so the AI knows when to invoke it. |

### 2.2 Sections to Include

A well-structured SKILL.md contains these sections:

#### When to Use This Skill

Bullet list of scenarios. Be specific — the AI matches user intent against these.

```markdown
## When to use this skill
- User wants to hash a string or text
- User asks for MD5, SHA256, or other hash of content
- User needs to compute a checksum of text
```

#### How to Run (Cross-Platform Commands)

This is the **cross-platform core**. Always provide both Windows and Linux/macOS commands using the **shared runner scripts** and **path variables**.

Define these path variables at the top:

```markdown
**Path Variables:**
- `<SKILL_DIR>` - The directory containing this skill
- `<RUN_SKILL_DIR>` - The skills-hub directory: `<SKILL_DIR>/../skills-hub`
```

Then provide execution commands for both platforms:

```markdown
### Linux/macOS
```bash
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "main.py" --arg "value"
```

### Windows (PowerShell)
```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" -Entrypoint "main.py" -UserArgs "--arg", "value"
```
```

> **Key pattern**: On Windows, arguments after `-UserArgs` are passed as a **comma-separated array of strings**. On Linux, they are passed as normal positional arguments after the entrypoint.

#### Arguments Table

Document every CLI argument in a table:

```markdown
## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--text` | Yes | The text to process |
| `--format` | No | Output format: `json`, `markdown` (default: `json`) |
```

#### Examples

Provide concrete examples for both platforms:

```markdown
## Examples

**Basic usage:**
```bash
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "main.py" --text "Hello"
```

**Windows:**
```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" -Entrypoint "main.py" -UserArgs "--text", "Hello"
```
```

#### Output

Describe the expected output format so the AI can parse/present it.

#### Dependencies

Mention that dependencies are installed automatically from `requirements.txt`.

---

## Step 3: Write config.json

### Minimal config.json (Python skill using hub defaults)

```json
{
  "metadata": {
    "name": "My-Cool-Skill",
    "version": "1.0.0",
    "description": "Brief description of what the skill does"
  },
  "activeEnvironment": "miniPython"
}
```

### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `metadata.name` | Yes | Skill identifier — should match folder name |
| `metadata.version` | Yes | Semantic version (`MAJOR.MINOR.PATCH`). Used by the hub for update detection. |
| `metadata.description` | No | Human-readable description |
| `activeEnvironment` | No | Which named environment to use. Common values: `"miniPython"` (default portable Python), `"venv"` (virtual environment), or omit for `"none"` (no Python). |

### When to omit `activeEnvironment`

| Scenario | `activeEnvironment` value | Effect |
|----------|---------------------------|--------|
| Python skill, use hub's portable Python | `"miniPython"` | Runner uses pre-extracted Python archive |
| Python skill, use a venv | `"venv"` | Runner activates specified virtual environment |
| Non-Python skill (shell, data-only, etc.) | *Omit the field entirely* | Runner defaults to `"none"`, skips Python |
| Skill has no `config.json` at all | N/A | Falls back to hub's `activeEnvironment` (usually `"miniPython"`) |

> ### ⚠️ Critical: `config.json` presence changes default behavior
>
> The runner uses **three-way logic** to decide the environment:
>
> 1. **No `config.json` at all** → The hub's `activeEnvironment` is used (typically `"miniPython"`). This means a skill with only a `requirements.txt` and no `config.json` **will** trigger miniPython environment setup and dependency installation automatically.
>
> 2. **Has `config.json` but `activeEnvironment` is omitted** → Defaults to `"none"`. No Python environment is activated, `requirements.txt` is **not installed**, and the entrypoint is executed directly. This is the most common mistake: if your skill needs Python, you **must** set `activeEnvironment` explicitly in `config.json`.
>
> 3. **Has `config.json` with `activeEnvironment` set** → Uses the specified environment (e.g., `"miniPython"`, `"venv"`), installs dependencies, and runs the skill with that Python.
>
> **In short:** Adding a `config.json` without `activeEnvironment` will *break* a Python skill that previously worked without one. Always set `"activeEnvironment": "miniPython"` (or another environment) in `config.json` if your skill has Python dependencies.

---

## Step 4: Implement the Python Entry Point

Write standard Python CLI scripts. Use `argparse` or `click` for argument parsing.

### Guidelines for Cross-Platform Python Code

1. **Use `os.path` or `pathlib.Path` for file paths** — never hardcode `\` or `/`:
   ```python
   from pathlib import Path
   output_dir = Path(args.output) / "results"
   output_dir.mkdir(parents=True, exist_ok=True)
   ```

2. **Use `sys.stdout` / `print()` for output** — the runner captures stdout.

3. **Handle environment variables portably**:
   ```python
   import os
   from dotenv import load_dotenv
   load_dotenv()  # Reads .env file in current directory
   secret = os.environ.get("MY_SECRET")
   ```

4. **Exit with proper codes**:
   ```python
   import sys
   if error:
       print(f"Error: {error}", file=sys.stderr)
       sys.exit(1)
   ```

5. **Avoid platform-specific system calls** — don't shell out to `cmd`, `bash`, `powershell`, etc. If you need subprocess calls, use `subprocess.run()` with `shell=False`.

### Example: Minimal Skill Entry Point

```python
#!/usr/bin/env python3
"""My Cool Skill - Does something useful."""

import click

@click.command()
@click.option('--text', '-t', required=True, help='Input text to process')
@click.option('--format', '-f', default='json',
              type=click.Choice(['json', 'markdown'], case_sensitive=False),
              help='Output format (default: json)')
def main(text: str, format: str):
    """Process text and return results."""
    result = do_something(text)

    if format == 'json':
        import json
        print(json.dumps({"input": text, "result": result}, indent=2))
    else:
        print(f"# Result\n\n**Input:** {text}\n\n**Output:** {result}")

def do_something(text: str) -> str:
    return text.upper()  # Placeholder

if __name__ == '__main__':
    main()
```

### Example: Using argparse (no extra dependencies)

```python
#!/usr/bin/env python3
"""My Skill using argparse."""

import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="My Skill")
    parser.add_argument("--query", required=True, help="The query to run")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    try:
        result = process(args.query)
        print(result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

def process(query: str) -> str:
    return f"Processed: {query}"

if __name__ == "__main__":
    main()
```

---

## Step 5: Declare Dependencies

Create `requirements.txt` with pinned or minimum-version dependencies:

```
click>=8.0.0
requests>=2.28.0
python-dotenv
```

### Tips

- **Pin major versions** to avoid breaking changes: `click>=8.0.0,<9.0.0`
- **Keep dependencies minimal** — fewer packages means faster installs and fewer conflicts.
- Common utility packages already available in `miniPython` may not need listing, but it's safer to declare them.
- The hub installs dependencies with proxy support from `config.json` automatically during skill download.

---

## Step 6: Cross-Platform Execution

You never call Python directly. Instead, the **shared runner scripts** handle everything:

### What the Runner Does

1. **Merges configuration**: Deep-merges hub `config.json` with the skill's `config.json` (skill values override hub values).
2. **Resolves the environment**: Reads `activeEnvironment` → looks up `environments.<name>` → determines `type` (`sourced`, `venv`, or `none`).
3. **Locates Python**: Based on environment type and platform-specific paths.
4. **Executes the skill**: `python <entrypoint> <user-args>`

### Runner Script Signatures

**Linux/macOS** (`run-skill.sh`):
```
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "<ENTRYPOINT>" [args...]
```

| Positional | Description |
|------------|-------------|
| `$1` — Skill Dir | Absolute path to the skill folder |
| `$2` — Entrypoint | Filename of the Python script (e.g., `main.py`) |
| `$3+` — User Args | Additional arguments passed through to the Python script |

**Windows** (`run-skill.ps1`):
```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" -Entrypoint "<ENTRYPOINT>" -UserArgs "<arg1>", "<arg2>", ...
```

| Parameter | Description |
|-----------|-------------|
| `-SkillDir` | Absolute path to the skill folder |
| `-Entrypoint` | Filename of the Python script |
| `-UserArgs` | Comma-separated array of string arguments |

### Path Variables Convention

In SKILL.md, always define and use these placeholders:

| Variable | Meaning |
|----------|---------|
| `<SKILL_DIR>` | The directory containing this skill's files |
| `<RUN_SKILL_DIR>` | The skills-hub directory, always at `<SKILL_DIR>/../skills-hub` |

The AI agent resolves these to absolute paths at runtime based on where the skill is installed (typically `.claude/skills/<Skill-Name>`).

---

## Environment Configuration In Depth

### Environment Types

| Type | `activeEnvironment` | Use Case | Python Location |
|------|---------------------|----------|-----------------|
| **sourced** | `"miniPython"` | Corporate environments, portable Python archive | Windows: `<dest>\python.exe`, Linux: `<dest>/bin/python` |
| **venv** | `"venv"` or custom name | Dev machines with Python installed | Windows: `<path>\Scripts\python.exe`, Linux: `<path>/bin/python` |
| **none** | Omit `activeEnvironment` (or set explicitly) | Non-Python skills | N/A — entrypoint executed directly |

### Sourced (miniPython) — Default

The hub ships a pre-packaged portable Python distribution. No system Python required.

```json
{
  "activeEnvironment": "miniPython"
}
```

The runner reads the `dest` path from the merged config:
- Windows: `c:\MiniPython\python.exe`
- Linux: `~/MiniPython/bin/python`

### Virtual Environment (venv)

Use when the target machine has Python installed and you want an isolated venv.

```json
{
  "activeEnvironment": "myVenv",
  "environments": {
    "myVenv": {
      "type": "venv",
      "pythonExecutable": {
        "windows": "python",
        "linux": "python3"
      },
      "path": {
        "windows": "~\\.my-skill-venv",
        "linux": "~/.my-skill-venv"
      }
    }
  }
}
```

> The venv must already exist. If missing, the runner shows an error with a `python -m venv` hint.

### None — No Python

For skills that are purely prompt-based (like Demo-echo-skill) or use non-Python executables. Simply omit `activeEnvironment` from your config.json:

```json
{
  "metadata": {
    "name": "My-Prompt-Skill",
    "version": "1.0.0",
    "description": "A skill that needs no runtime"
  }
}
```

### Per-Skill Python Isolation

By default, all skills that use `"miniPython"` share the **same** Python installation (e.g., `c:\MiniPython`). This means `pip install` from one skill's `requirements.txt` affects every other skill using that environment. If two skills need conflicting package versions, they will clash.

You can give a skill its **own separate Python environment** by overriding the `dest` path (for sourced) or defining a custom venv:

#### Option A: Separate sourced environment (own copy of miniPython)

```json
{
  "metadata": { "name": "My-Isolated-Skill", "version": "1.0.0" },
  "activeEnvironment": "miniPython",
  "environments": {
    "miniPython": {
      "dest": {
        "windows": "c:\\MyIsolatedSkillPython",
        "linux": "~/MyIsolatedSkillPython"
      }
    }
  }
}
```

The hub will extract a fresh copy of the Python archive into `c:\MyIsolatedSkillPython` (or `~/MyIsolatedSkillPython`), and this skill's `requirements.txt` will be installed **only there** — completely separate from the default `c:\MiniPython`.

#### Option B: Dedicated venv per skill

```json
{
  "metadata": { "name": "My-Venv-Skill", "version": "1.0.0" },
  "activeEnvironment": "skillVenv",
  "environments": {
    "skillVenv": {
      "type": "venv",
      "pythonExecutable": { "windows": "python", "linux": "python3" },
      "path": {
        "windows": "~\\.my-skill-venv",
        "linux": "~/.my-skill-venv"
      }
    }
  }
}
```

This creates a completely independent virtual environment. The venv must be created beforehand (`python -m venv ~/.my-skill-venv`); the runner will use it and install `requirements.txt` into it.

#### Option C: Named custom environment

You can also define an entirely new named environment (not overriding `miniPython`):

```json
{
  "metadata": { "name": "Data-Science-Skill", "version": "2.0.0" },
  "activeEnvironment": "dataSciencePython",
  "environments": {
    "dataSciencePython": {
      "type": "sourced",
      "archiveFile": {
        "windows": "\\\\server\\share\\DataSciencePython.zip",
        "linux": "/mnt/share/DataSciencePython.tar.gz"
      },
      "dest": {
        "windows": "c:\\DataSciencePython",
        "linux": "~/DataSciencePython"
      }
    }
  }
}
```

This uses a completely different Python distribution archive — useful when a skill needs a Python version or base packages that differ from the standard miniPython.

> **When to isolate:** Use a separate environment when your skill has dependency conflicts with other skills, needs a different Python version, or requires heavy packages (e.g., `numpy`, `pandas`) that you don't want polluting the shared miniPython.

---

## Configuration Inheritance

The runner performs a **recursive deep merge** of hub config → skill config. This means your skill only needs to specify the fields it wants to override.

### Example

**Hub config.json (base defaults):**
```json
{
  "activeEnvironment": "miniPython",
  "environments": {
    "miniPython": {
      "type": "sourced",
      "dest": {
        "windows": "c:\\MiniPython",
        "linux": "~/MiniPython"
      },
      "archiveFile": {
        "windows": "\\\\server\\share\\MiniPython.zip",
        "linux": "/mnt/share/MiniPython.tar.gz"
      }
    }
  },
  "proxy": {
    "http": "http://proxy.example.com:912",
    "https": "http://proxy.example.com:912"
  }
}
```

**Skill config.json (overrides only dest):**
```json
{
  "metadata": {
    "name": "My-Skill",
    "version": "1.0.0"
  },
  "activeEnvironment": "miniPython",
  "environments": {
    "miniPython": {
      "dest": {
        "windows": "c:\\MySkillPython",
        "linux": "~/MySkillPython"
      }
    }
  }
}
```

**Effective merged config:**
```json
{
  "activeEnvironment": "miniPython",
  "environments": {
    "miniPython": {
      "type": "sourced",
      "dest": {
        "windows": "c:\\MySkillPython",
        "linux": "~/MySkillPython"
      },
      "archiveFile": {
        "windows": "\\\\server\\share\\MiniPython.zip",
        "linux": "/mnt/share/MiniPython.tar.gz"
      }
    }
  },
  "proxy": {
    "http": "http://proxy.example.com:912",
    "https": "http://proxy.example.com:912"
  }
}
```

Only `dest` was replaced; everything else was inherited.

---

## Non-Python Skills

Not every skill needs Python. The **Demo-echo-skill** is an example of a pure "prompt skill" — it has no runtime. Its SKILL.md contains all the logic directly as formatting instructions.

### Prompt-Only Skill

If your skill's logic can be expressed entirely as instructions for the AI:

1. Write a `SKILL.md` with the full instructions.
2. Create a `config.json` **without** `activeEnvironment`:
   ```json
   {
     "metadata": {
       "name": "My-Prompt-Skill",
       "version": "1.0.0",
       "description": "A skill with no runtime"
     }
   }
   ```
3. No `requirements.txt` or Python files needed.
4. No runner invocation — the AI follows the SKILL.md instructions directly.

### Shell/Binary Skills

If your skill runs a non-Python executable, set environment type to `"none"` explicitly:

```json
{
  "metadata": { "name": "My-Shell-Skill", "version": "1.0.0" },
  "activeEnvironment": "standalone",
  "environments": {
    "standalone": { "type": "none" }
  }
}
```

The runner will execute the entrypoint directly without wrapping it in a Python call.

---

## Best Practices & Checklist

### Skill Authoring Checklist

- [ ] **Folder name** matches `metadata.name` in `config.json`
- [ ] **SKILL.md** has frontmatter with `name` and `description` (including trigger phrases)
- [ ] **SKILL.md** documents "When to use" scenarios
- [ ] **SKILL.md** provides both Linux and Windows run commands using runner scripts
- [ ] **SKILL.md** defines `<SKILL_DIR>` and `<RUN_SKILL_DIR>` path variables
- [ ] **SKILL.md** has an arguments table
- [ ] **SKILL.md** has concrete examples for both platforms
- [ ] **SKILL.md** describes expected output format
- [ ] **config.json** has `metadata.name` and `metadata.version`
- [ ] **config.json** sets `activeEnvironment` (or omits it for non-Python skills)
- [ ] **requirements.txt** lists all Python dependencies with version constraints
- [ ] Python code uses **`os.path` or `pathlib`** (no hardcoded path separators)
- [ ] Python code uses **`argparse` or `click`** for CLI parsing
- [ ] Python code exits with code `1` on error, `0` on success
- [ ] Tested on both Windows and Linux

### Writing Good Trigger Descriptions

The `description` field in SKILL.md frontmatter is how the AI decides to use your skill. Include:

- Action verbs the user might say: *"Use this skill when the user asks to hash, compute hash, get hash of…"*
- Domain terms: *"…asks about Intel WiFi, Bluetooth, TOP products…"*
- Be specific enough to avoid false matches with other skills.

### Cross-Platform Python Tips

| Do | Don't |
|----|-------|
| `Path(a) / b` | `a + "\\b"` |
| `os.environ.get("VAR")` | Platform-specific env syntax |
| `subprocess.run([...], shell=False)` | `os.system("bash ...")` |
| `print(result)` to stdout | Write to platform-specific temp paths |
| `sys.exit(1)` on error | Raise unhandled exceptions silently |

### Version Bumping

Always increment `metadata.version` when you publish changes:

| Change Type | Version Bump | Example |
|-------------|-------------|---------|
| Bug fix | Patch | `1.0.0` → `1.0.1` |
| New feature (backward-compatible) | Minor | `1.0.1` → `1.1.0` |
| Breaking change | Major | `1.1.0` → `2.0.0` |

This ensures the hub's update mechanism detects and distributes your changes.

---

## Complete Worked Example

Let's build a **Word-Count Skill** from scratch.

### Directory Structure

```
Word-Count/
├── SKILL.md
├── config.json
├── requirements.txt
└── count.py
```

### SKILL.md

`````markdown
````skill
---
name: Word-Count
description: Counts words, lines, and characters in a text file or string.
             Use this skill when the user asks to "count words", "word count",
             "how many words", "line count", or "character count".
---

# Word Count Skill

Counts words, lines, and characters in a given text file or inline string.

## When to use this skill
- User wants to count words in a file
- User asks "how many words in this document?"
- User needs line or character counts

## How to Run

The skill uses shared runner scripts from the skills-hub folder for cross-platform execution.

**Path Variables:**
- `<SKILL_DIR>` - The directory containing this skill
- `<RUN_SKILL_DIR>` - The skills-hub directory: `<SKILL_DIR>/../skills-hub`

### Linux/macOS
```bash
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "count.py" --file "document.txt"
```

### Windows (PowerShell)
```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" -Entrypoint "count.py" -UserArgs "--file", "document.txt"
```

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--file` | Conditional | Path to the text file to count (required if `--text` not provided) |
| `--text` | Conditional | Inline text string to count (required if `--file` not provided) |
| `--format` | No | Output format: `text`, `json` (default: `text`) |

## Examples

**Count words in a file:**
```bash
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "count.py" --file "README.md"
```

**Count inline text (Windows):**
```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" -Entrypoint "count.py" -UserArgs "--text", "Hello world, this is a test"
```

**JSON output:**
```bash
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "count.py" --file "README.md" --format json
```

## Output

```
File: README.md
Lines: 42
Words: 318
Characters: 1847
```

## Dependencies

Uses only the Python standard library — no additional packages required.
````
`````

### config.json

```json
{
  "metadata": {
    "name": "Word-Count",
    "version": "1.0.0",
    "description": "Counts words, lines, and characters in text files or strings"
  },
  "activeEnvironment": "miniPython"
}
```

### requirements.txt

```
# No external dependencies — uses standard library only
```

### count.py

```python
#!/usr/bin/env python3
"""Word Count Skill - Counts words, lines, and characters."""

import argparse
import json
import sys
from pathlib import Path


def count_text(text: str) -> dict:
    """Count words, lines, and characters in text."""
    lines = text.splitlines()
    return {
        "lines": len(lines),
        "words": sum(len(line.split()) for line in lines),
        "characters": len(text),
    }


def main():
    parser = argparse.ArgumentParser(description="Count words, lines, and characters")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", "-f", help="Path to text file")
    group.add_argument("--text", "-t", help="Inline text string")
    parser.add_argument("--format", default="text",
                        choices=["text", "json"], help="Output format")
    args = parser.parse_args()

    try:
        if args.file:
            file_path = Path(args.file)
            if not file_path.exists():
                print(f"Error: File not found: {args.file}", file=sys.stderr)
                sys.exit(1)
            content = file_path.read_text(encoding="utf-8")
            source = str(file_path)
        else:
            content = args.text
            source = "(inline text)"

        counts = count_text(content)

        if args.format == "json":
            print(json.dumps({"source": source, **counts}, indent=2))
        else:
            print(f"File: {source}")
            print(f"Lines: {counts['lines']}")
            print(f"Words: {counts['words']}")
            print(f"Characters: {counts['characters']}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

---

## Converting an Existing Skill to Cross-Platform

If you already have a working skill that only runs on one platform (typically Windows with hardcoded paths), you can convert it to a cross-platform skill by following the checklist below.

> **Tip for GHCP agent users:** You can paste the following instructions into GitHub Copilot Chat along with a reference to this manual:
>
> *"Read the cross-platform skill manual at `.claude/skills/skills-hub/Writing-Cross-Platform-Skills.md`, then rewrite `<my-skill>/SKILL.md` to conform to the cross-platform pattern."*

### Conversion Checklist

#### 1. Replace hardcoded Python paths with runner scripts

**Before** (Windows-only):
```powershell
c:\MiniPython\python "<PATH_TO_SKILL>\main.py" --arg "value"
```

**After** (cross-platform):
```bash
# Linux/macOS
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "main.py" --arg "value"
```
```powershell
# Windows
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" -Entrypoint "main.py" -UserArgs "--arg", "value"
```

The runner scripts handle Python environment resolution automatically — you never call `python` directly.

#### 2. Add path variables to SKILL.md

Add this block near the top of your "How to Run" section:

```markdown
**Path Variables:**
- `<SKILL_DIR>` - The directory containing this skill
- `<RUN_SKILL_DIR>` - The skills-hub directory: `<SKILL_DIR>/../skills-hub`
```

Then remove any hardcoded absolute paths like `c:\wcs-skills-hub\skills\My-Skill\`.

#### 3. Provide both platform commands for every example

Every run command in SKILL.md should have both a Linux/macOS and a Windows variant. Don't just show one platform and say "adapt for the other".

**Before:**
```powershell
c:\MiniPython\python "c:\wcs-skills-hub\skills\Req-Decomposer\decompose_req.py" --dcr "DCR-1202"
```

**After:**
```bash
# Linux/macOS
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "decompose_req.py" --dcr "DCR-1202"
```
```powershell
# Windows
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" -Entrypoint "decompose_req.py" -UserArgs "--dcr", "DCR-1202"
```

#### 4. Add or fix config.json

If the skill has no `config.json` and relies on Python, it works by accident (falls back to hub's `miniPython`). Make it explicit:

```json
{
  "metadata": {
    "name": "My-Skill",
    "version": "1.0.0",
    "description": "What the skill does"
  },
  "activeEnvironment": "miniPython"
}
```

If the skill already has a `config.json` but is missing `activeEnvironment`, **add it** — otherwise the runner defaults to `"none"` and won't use Python at all (see [the warning in Step 3](#step-3-write-configjson)).

#### 5. Fix platform-specific Python code

Search the `.py` files for these patterns and replace them:

| Find | Replace with |
|------|-------------|
| `"\\\\path\\\\to\\\\file"` or `"C:\\..."` | `pathlib.Path(args.path)` or `os.path.join()` |
| `os.system("bash ...")` / `os.system("cmd ...")` | `subprocess.run([...], shell=False)` |
| `open("hardcoded/path")` | `open(Path(args.input))` |
| Platform-specific temp dirs | `tempfile.mkdtemp()` |
| `\r\n` assumptions | `os.linesep` or universal newline mode |

#### 6. Add an arguments table

If SKILL.md lists arguments only in prose or examples, add a formal table:

```markdown
## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--dcr` | Conditional | DCR ID to decompose (required if `--text` not provided) |
| `--text` | Conditional | Free-text input (required if `--dcr` not provided) |
| `--format` | No | Output format: `json`, `markdown`, `both` (default: `json`) |
```

#### 7. Remove platform-specific workarounds from SKILL.md

Remove instructions like "Python Interpreter: `c:\MiniPython\python` is available (no need to verify)" — the runner scripts handle this.

### Real-World Example: Converting Req-Decomposer

The Req-Decomposer skill is an example of a Windows-only skill that hardcodes `c:\MiniPython\python` and absolute paths. Here's what a conversion looks like:

| What | Before | After |
|------|--------|-------|
| Python call | `c:\MiniPython\python "<PATH>\decompose_req.py"` | Runner scripts with `<SKILL_DIR>` / `<RUN_SKILL_DIR>` |
| Path to skill | `c:\wcs-skills-hub\skills\Req-Decomposer\decompose_req.py` | `"<SKILL_DIR>"` resolved at runtime |
| Platform coverage | PowerShell examples only | Both bash and PowerShell examples |
| Prerequisites section | "Python Interpreter: `c:\MiniPython\python` is available" | Removed — runner handles it |
| Arguments | Scattered in prose | Formal `## Arguments` table |

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `"Entrypoint not found"` | Wrong filename in SKILL.md or `-Entrypoint` | Verify the `.py` filename matches exactly |
| `"Python environment not found"` | miniPython not extracted | Run `skills_hub.ps1 -PrepareEnv` or `skills_hub.sh --prepare-env` |
| `"jq is required"` (Linux) | `jq` not installed | `sudo apt install jq` or `brew install jq` |
| Dependencies fail to install | Proxy not configured | Add `proxy.http` / `proxy.https` to hub `config.json` |
| Skill not discovered by AI | Missing or malformed SKILL.md frontmatter | Ensure `` ````skill `` fences and `---` delimiters are correct |
| Updates not detected | Version not bumped | Increment `metadata.version` in `config.json` |
| Path errors on Linux | Hardcoded `\` separators in Python code | Use `pathlib.Path` or `os.path.join()` |
| Skill runs on Windows but not Linux | Windows path in SKILL.md examples | Provide both platform commands using runner scripts |
| `venv not found` | venv not created | Run: `python -m venv <path>` as shown in error message |

---

## Quick Reference Card

### File Checklist

```
My-Skill/
├── SKILL.md           ← Frontmatter: name, description (with trigger phrases)
│                        Sections: When to use, How to Run (both OS), Arguments, Examples, Output
├── config.json        ← { metadata: {name, version}, activeEnvironment: "miniPython" }
├── requirements.txt   ← pip deps (one per line, version-pinned)
└── main.py            ← argparse/click CLI, pathlib paths, sys.exit on error
```

### SKILL.md Run Commands Template

**Linux/macOS:**
```bash
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "ENTRYPOINT.py" ARGS...
```

**Windows (PowerShell):**
```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" -Entrypoint "ENTRYPOINT.py" -UserArgs "ARG1", "ARG2", ...
```

### config.json Minimal Template

```json
{
  "metadata": {
    "name": "SKILL-NAME",
    "version": "1.0.0",
    "description": "DESCRIPTION"
  },
  "activeEnvironment": "miniPython"
}
```

### Environment Quick Reference

| I need… | Set `activeEnvironment` to… | Notes |
|---------|---------------------------|-------|
| Portable Python (no system Python) | `"miniPython"` | Default, works everywhere |
| My own venv | `"venv"` or custom name | Define `environments.<name>` with `type: "venv"` |
| Custom portable Python path | `"miniPython"` + override `dest` | Uses config inheritance |
| No Python at all | *Omit the field* | Skill treated as non-Python |

---

## Available Skills Catalog

The following skills are currently available in the Skills Hub. Each skill follows the cross-platform conventions described in this guide.

### Document Conversion

| Skill | Version | Description | Environment |
|-------|---------|-------------|-------------|
| [Doc2Md-convert](../Doc2Md-convert/SKILL.md) | 1.1.0 | Converts a single Word document to Markdown using LLM with image extraction and Mermaid diagrams | `miniPython` (shared) |
| [Doc2Md-batch-convert](../Doc2Md-batch-convert/SKILL.md) | 1.1.1 | Recursively batch-converts all Word documents in a directory tree to Markdown with images and Mermaid diagrams. Supports subagent-based parallel processing. | `miniPython` (shared) |
| [Pdf2Md-convert](../Pdf2Md-convert/SKILL.md) | 1.2.0 | Converts PDF files to Markdown using Docling with auto-detected hardware acceleration, image extraction, automatic watermark removal, and optional ChAI-powered image descriptions | `miniPython` → `c:\pdf2mdPython` |
| [Video2Md-convert](../Video2Md-convert/SKILL.md) | 1.0.0 | Converts video files to Markdown by extracting key frames, transcribing audio, and generating structured notes with optional ChAI-powered frame descriptions | `miniPython` → `c:\video2mdPython` |
| [Video2PDF-convert](../Video2PDF-convert/SKILL.md) | 1.0.0 | Converts videos into PDF reports combining Whisper audio transcription (dual-engine: OpenVINO/native) with Phi-3.5 Vision VLM frame analysis. Supports Hebrew, translation, and standalone SRT fusion. | `miniPython` → `c:\video2pdfPython` |
| [Audio2Md-convert](../Audio2Md-convert/SKILL.md) | 1.0.0 | Dual-engine speech-to-text transcription using Whisper. OpenVINO GenAI (fast, English) and native OpenAI Whisper (best for Hebrew and multilingual). Outputs SRT, text, or JSON. | `miniPython` → `c:\audio2mdPython` |

### Diagram & Image Conversion

| Skill | Version | Description | Environment |
|-------|---------|-------------|-------------|
| [Doc2Md-image2mermaid](../Doc2Md-image2mermaid/SKILL.md) | 1.0.6 | Converts diagram images to Mermaid code using AI vision and generates descriptions for non-diagram images | `miniPython` (shared) |
| [Doc2Md-refine-mermaid](../Doc2Md-refine-mermaid/SKILL.md) | 1.0.0 | Iterative Mermaid quality refinement agent. Validates mermaid diagrams against source images and refines them until quality score exceeds 85% or max 3 attempts. | `miniPython` (shared) |
| [Visio2Md-image2mermaid](../Visio2Md-image2mermaid/SKILL.md) | 1.0.0 | Converts Visio (.vsdx) diagrams to Mermaid code via XML extraction + LLM, or via AI vision analysis of diagram images. Supports page-selective conversion, validation, and batch processing. | `miniPython` → `c:\visio2mdPython` |

### Video & Media Processing

| Skill | Version | Description | Environment |
|-------|---------|-------------|-------------|
| [Video-clip-extractor](../Video-clip-extractor/SKILL.md) | 1.0.0 | Extracts video clips by timestamp using ffmpeg. Supports single clips, multiple segments, batch JSON input, and frame-accurate re-encoding. | `miniPython` → `c:\clipextPython` |

### Architecture & Specification Generation

| Skill | Version | Description | Environment |
|-------|---------|-------------|-------------|
| [Spec-create](../Spec-create/SKILL.md) | 1.0.0 | Creates lean spec documents from feature ideas with WREQ-compliant format, 13-section template, and no-filler generation via ChAI LLM. | `miniPython` → `c:\speccreatePython` |

### Intel Platform & Data Access

| Skill | Version | Description | Environment |
|-------|---------|-------------|-------------|
| [ChAI-Assistant](../ChAI-Assistant/SKILL.md) | 1.0.0 | Queries Intel AI Assistants (ChAI) for answers about WiFi, Bluetooth, TOP, and ICA products | `miniPython` (shared) |
| [ChAI-Jira-SQL](../ChAI-Jira-SQL/SKILL.md) | 1.0.0 | Executes SQL queries against the Jira database to retrieve Intel documents by key or matching criteria | `miniPython` (shared) |
| [ChAI-Vector-Store](../ChAI-Vector-Store/SKILL.md) | 1.0.0 | Retrieves context from Intel knowledge bases using embedding similarity search via the ChAI API | `miniPython` (shared) |
| [Access-SharePoint](../Access-SharePoint/SKILL.md) | 1.0.0 | Access Intel SharePoint sites — list files, search documents, download files, and read content | `miniPython` (shared) |
| [Access-Wiki](../Access-Wiki/SKILL.md) | 1.2.0 | Access Intel Confluence wiki — read pages, search content, list spaces and pages. Cross-platform: Windows, Linux, macOS. | `miniPython` (shared) |
| [Jira-Skills](../Jira-Skills/SKILL.md) | 1.0.0 | Downloads, searches, and updates JIRA issues by ID, folder path, or natural language query | `miniPython` (shared) |

### Design Workflow (Archflow)

| Skill | Version | Description | Environment |
|-------|---------|-------------|-------------|
| [Archflow-Download-DCR](../Archflow-Download-DCR/SKILL.md) | 1.0.0 | Downloads a JIRA DCR issue and its linked WREQ requirements as Markdown files | `miniPython` (shared) |
| [Archflow-Gen-Gap-Tests](../Archflow-Gen-Gap-Tests/SKILL.md) | 1.0.0 | Analyzes a downloaded DCR and its WREQs to identify test coverage gaps and generate new tests | `miniPython` (shared) |

### Demo & Templates

| Skill | Version | Description | Environment |
|-------|---------|-------------|-------------|
| [Demo-echo-skill](../Demo-echo-skill/SKILL.md) | 1.0.0 | Non-Python skill. Echoes the user's prompt in a fancy, formatted way with decorative borders and styling | `none` (prompt-only) |
| [Demo-hash-skill](../Demo-hash-skill/SKILL.md) | 1.0.0 | Computes cryptographic hashes of text prompts | `miniPython` → `c:\DemoHashPython` |

### Framework

| Skill | Version | Description | Environment |
|-------|---------|-------------|-------------|
| [skills-hub](../skills-hub/SKILL.md) | 1.0.0 | Hub manager — downloads, updates, and prepares skills and Python environments | `miniPython` → `c:\MiniPython` |

### Environment Summary

Skills use either the **shared** `miniPython` environment (`c:\MiniPython` / `~/MiniPython`) or an **isolated** environment to avoid dependency conflicts:

| Environment Path (Windows) | Skills Using It |
|---------------------------|----------------|
| `c:\MiniPython` (shared) | skills-hub, Doc2Md-convert, Doc2Md-batch-convert, Doc2Md-image2mermaid, Doc2Md-refine-mermaid, ChAI-Assistant, ChAI-Jira-SQL, ChAI-Vector-Store, Access-SharePoint, Access-Wiki, Jira-Skills, Archflow-Download-DCR, Archflow-Gen-Gap-Tests |
| `c:\pdf2mdPython` | Pdf2Md-convert |
| `c:\video2mdPython` | Video2Md-convert |
| `c:\video2pdfPython` | Video2PDF-convert |
| `c:\audio2mdPython` | Audio2Md-convert |
| `c:\clipextPython` | Video-clip-extractor |
| `c:\visio2mdPython` | Visio2Md-image2mermaid |
| `c:\speccreatePython` | Spec-create |
| `c:\DemoHashPython` | Demo-hash-skill |
| *(none)* | Demo-echo-skill |
