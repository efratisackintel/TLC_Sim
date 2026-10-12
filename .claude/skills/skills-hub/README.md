# Skills Hub Manager

A utility for managing GHCP (GitHub Copilot) skills from a central repository. Supports listing, downloading, updating, and environment preparation.

## First-Time Installation

To install the skills-hub for the first time, paste the following text **exactly as written** into VS Code's GitHub Copilot Chat:

```
Execute the command:
robocopy "\\infs089.iil.intel.com\wcd_win\ChAI_Skills\skills-hub" ".claude\skills\skills-hub" /E /R:3 /W:5
```

This will copy the skills-hub from the network share to your workspace's `.claude/skills/skills-hub` directory.

## Prerequisites

- **Windows**: PowerShell 5.1+
- **Linux/macOS**: Bash, `jq` (for JSON parsing)

## Usage

Once installed, use natural language prompts with GitHub Copilot:

| Task | Example Prompts |
|------|-----------------|
| List skills | "list available skills", "show hub skills" |
| Download skills | "download all skills", "install archflow skills" |
| Update skills | "update my installed skills", "sync skills from hub" |
| Prepare environment | "prepare python env", "setup skill environment" |

## Manual Script Usage

### Windows (PowerShell)
```powershell
# List all available skills
& ".claude\skills\skills-hub\skills_hub.ps1" -ListOnly

# Download specific skills
& ".claude\skills\skills-hub\skills_hub.ps1" -Skills "Archflow*"

# Download all skills
& ".claude\skills\skills-hub\skills_hub.ps1" -All

# Update installed skills
& ".claude\skills\skills-hub\skills_hub.ps1" -Update

# Force update (ignore version checks)
& ".claude\skills\skills-hub\skills_hub.ps1" -Update -Force

# Prepare Python environment
& ".claude\skills\skills-hub\skills_hub.ps1" -PrepareEnv
```

### Linux/macOS (Bash)
```bash
# List all available skills
bash ".claude/skills/skills-hub/skills_hub.sh" --list-only

# Download specific skills
bash ".claude/skills/skills-hub/skills_hub.sh" --skills "Archflow*"

# Update installed skills
bash ".claude/skills/skills-hub/skills_hub.sh" --update

# Force update (ignore version checks)
bash ".claude/skills/skills-hub/skills_hub.sh" --update --force

# Prepare Python environment
bash ".claude/skills/skills-hub/skills_hub.sh" --prepare-env
```

## Running Skills

Skills are executed via the shared runner scripts, not directly. The runner scripts handle Python environment activation, config merging, and cross-platform execution.

### Windows (PowerShell)
```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" -Entrypoint "main.py" -UserArgs "--arg", "value"
```

### Linux/macOS (Bash)
```bash
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "main.py" --arg "value"
```

Where:
- `<SKILL_DIR>` is the directory containing the specific skill
- `<RUN_SKILL_DIR>` is the `skills-hub` directory: `<SKILL_DIR>/../skills-hub`

## Configuration

Configuration is stored in `config.json`. Key settings:

| Setting | Description |
|---------|-------------|
| `srcRoot.windows` / `srcRoot.linux` | Source repository path |
| `general.destRoot` | Installation directory (`.claude/skills`) |
| `activeEnvironment` | Active Python environment name |
| `environments.<name>` | Environment-specific settings |
| `environments.<name>.type` | Environment type: `sourced`, `venv`, or `none` |
| `proxy.http` / `proxy.https` | Proxy for pip installs |

### Environment Types

| Type | Description |
|------|-------------|
| `sourced` | Portable Python extracted from an archive (e.g., miniPython) |
| `venv` | Existing Python virtual environment |
| `none` | No Python environment needed (standalone scripts) |

### Configuration Inheritance

Configuration follows a **deep-merge inheritance model**:

1. **Hub config** serves as the base/default configuration
2. **Skill config** overrides hub config where specified
3. Merging is recursive: nested keys are merged, not replaced wholesale
4. Only specified keys override — omitting a key preserves the parent's value

See [CONFIG_SCHEMA.md](CONFIG_SCHEMA.md) for the full configuration schema.

## Files

| File | Description |
|------|-------------|
| `skills_hub.ps1` | Windows PowerShell hub manager script |
| `skills_hub.sh` | Linux/macOS Bash hub manager script |
| `run-skill.ps1` | Windows PowerShell skill runner |
| `run-skill.sh` | Linux/macOS Bash skill runner |
| `config.json` | Hub configuration |
| `SKILL.md` | AI agent instructions |
| `CONFIG_SCHEMA.md` | Configuration schema documentation |

## Troubleshooting

### "jq is required but not installed" (Linux)
Install jq: `sudo apt install jq` or `brew install jq`

### Security warning on Windows
When prompted, select `[R] Run once` to allow the script to execute.

### Skills not updating
Use `-Force` (Windows) or `--force` (Linux) to bypass version checks.

### Python skill fails after adding config.json
If your skill has a `config.json` but omits `activeEnvironment`, the runner defaults to `"none"` (no Python). Set `"activeEnvironment": "miniPython"` (or another environment) explicitly if your skill requires Python.
