# Skill Configuration Schema (config.json)

This document describes the `config.json` schema for skills-hub.

## Overview

Each skill can optionally include a `config.json` file with metadata.
If `config.json` is not present, the skill inherits all settings from the hub config.

## Configuration Inheritance

Configuration follows an **inheritance model** similar to class inheritance:

1. **Hub config** serves as the base/default configuration
2. **Skill config** overrides hub config where specified
3. Merging is **recursive/deep**: nested keys are merged, not replaced wholesale
4. **Only specified keys override** — omitting a key preserves the parent's value

### Example

**Hub config:**
```json
{
  "environments": {
    "miniPython": {
      "archiveFile": { "linux": "MiniPython.tar.gz" },
      "dest": { "linux": "~/MiniPython" },
      "useSudo": { "linux": false }
    }
  }
}
```

**Skill config (only overrides dest):**
```json
{
  "environments": {
    "miniPython": {
      "dest": { "linux": "~/TmpPython" }
    }
  }
}
```

**Effective merged config:**
```json
{
  "environments": {
    "miniPython": {
      "archiveFile": { "linux": "MiniPython.tar.gz" },
      "dest": { "linux": "~/TmpPython" },
      "useSudo": { "linux": false }
    }
  }
}
```

---

## Skills-Hub Config (config.json)

Located in the skills-hub directory, defines global settings:

```json
{
  "general": {
    "destRoot": ".claude/skills"
  },
  "srcRoot": {
    "windows": "\\\\server\\share\\skills",
    "linux": "skills_repo"
  },
  "activeEnvironment": "miniPython",
  "environments": {
    "miniPython": {
      "type": "sourced",
      "archiveFile": {
        "windows": "\\\\server\\share\\skills\\MiniPython.zip",
        "linux": "/path/to/MiniPython.tar.gz"
      },
      "dest": {
        "windows": "c:\\MiniPython",
        "linux": "~/MiniPython"
      },
      "useSudo": {
        "linux": false
      }
    },
    "venv": {
      "type": "venv",
      "pythonExecutable": {
        "windows": "python",
        "linux": "python3"
      },
      "path": {
        "windows": "~\\.venv",
        "linux": "~/.venv"
      }
    }
  },
  "proxy": {
    "http": "http://proxy.example.com:8080",
    "https": "http://proxy.example.com:8080"
  }
}
```

### Field Descriptions

| Field | Description |
|-------|-------------|
| `general.destRoot` | Destination folder for installed skills (relative to workspace) |
| `srcRoot.windows` | Source path for skills on Windows |
| `srcRoot.linux` | Source path for skills on Linux |
| `activeEnvironment` | Name of the active environment (key under `environments`) |
| `environments.<name>` | Named environment configurations (allows multiple sourced/venv environments) |
| `environments.<name>.type` | Environment type: `"sourced"` (archive-based), `"venv"` (virtual environment), or `"none"` (no Python environment needed) |
| `proxy.http` | HTTP proxy URL |
| `proxy.https` | HTTPS proxy URL |

---

## Skill Config (config.json)

Located in each skill's directory, defines skill metadata and runtime environment:

```json
{
  "metadata": {
    "name": "skill-name",
    "version": "1.0.0",
    "description": "Brief description of the skill",
    "envVars": [
      { "name": "API_TOKEN", "description": "API authentication token", "required": true }
    ]
  },
  "activeEnvironment": "miniPython"
}
```

### Field Descriptions

| Field | Required | Description |
|-------|----------|-------------|
| `metadata.name` | Yes | Skill identifier |
| `metadata.version` | Yes | Semantic version |
| `metadata.description` | No | Brief description |
| `metadata.envVars` | No | Array of environment variables the skill requires (secrets, tokens, API keys). Each entry has `name` (required), `description` (optional), and `required` (boolean, default `true`). Displayed in the Quick Run form's about section. |
| `activeEnvironment` | No | Name of the active environment (key under `environments`). **If omitted when skill has `config.json`, defaults to `"none"` (no Python needed). If skill has no `config.json`, uses hub's `activeEnvironment`.** |

---

## Environment Configuration

Skills specify which Python environment to use via `activeEnvironment`, which points to a named environment under the `environments` root key. Each environment has a `type` field that determines how it's handled.

### environments Root Key

All environment configurations are stored under the `environments` root key. Each named environment contains:
- `type`: `"sourced"`, `"venv"`, or `"none"`
- Type-specific settings

```json
{
  "environments": {
    "none": { "type": "none" },
    "miniPython": { "type": "sourced", /* sourced config */ },
    "customPython": { "type": "sourced", /* another sourced config */ },
    "venv": { "type": "venv", /* venv config */ },
    "projectVenv": { "type": "venv", /* another venv config */ }
  }
}
```

### none Type

Indicates that the skill does not require any Python environment. Use this for skills that are standalone scripts, shell commands, or don't have Python dependencies.

**This is the default when a skill has `config.json` but does not specify `activeEnvironment`.**

```json
{
  "metadata": { "name": "my-skill", "version": "1.0.0" },
  "activeEnvironment": "standalone",
  "environments": {
    "standalone": {
      "type": "none"
    }
  }
}
```

When `type` is `"none"`, the skills-hub will skip dependency installation entirely, even if a `requirements.txt` file exists.

---

### sourced Type (Default)

Uses a portable Python installation extracted from an archive. This is similar to the original miniPython approach.

```json
{
  "metadata": { "name": "my-skill", "version": "1.0.0" },
  "activeEnvironment": "miniPython",
  "environments": {
    "miniPython": {
      "type": "sourced",
      "archiveFile": {
        "windows": "\\\\server\\share\\MiniPython.zip",
        "linux": "/path/to/MiniPython.tar.gz"
      },
      "dest": {
        "windows": "c:\\MiniPython",
        "linux": "~/MiniPython"
      },
      "useSudo": {
        "linux": false
      }
    }
  }
}
```

| Field | Description |
|-------|-------------|
| `environments.<name>.type` | Must be `"sourced"` for archive-based environments |
| `environments.<name>.archiveFile` | Absolute path to Python archive file per platform |
| `environments.<name>.dest` | Installation path for the extracted Python per platform |
| `environments.<name>.useSudo.linux` | Whether to use sudo for installation |

**Python executable paths:**
- Linux: `<dest>/bin/python`
- Windows: `<dest>\python.exe`

### venv Type

Uses an existing Python virtual environment.

```json
{
  "metadata": { "name": "my-skill", "version": "1.0.0" },
  "activeEnvironment": "venv",
  "environments": {
    "venv": {
      "type": "venv",
      "pythonExecutable": {
        "windows": "C:\\Python311\\python.exe",
        "linux": "/usr/bin/python3.11"
      },
      "path": {
        "windows": ".venv",
        "linux": ".venv"
      }
    }
  }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `environments.<name>.type` | Yes | Must be `"venv"` for virtual environment |
| `environments.<name>.pythonExecutable` | No | Path to base Python executable (for error hints if venv missing) |
| `environments.<name>.path` | Yes | Path to the venv directory. Can be relative (to skill dir) or absolute. |

**Python executable paths:**
- Linux: `<path>/bin/python`
- Windows: `<path>\Scripts\python.exe`

**Note:** The venv must already exist. If not found, the scripts will show an error with a hint to create it using the configured `pythonExecutable`.

---

## Multiple Environments Example

A skill can define and use custom environments:

```json
{
  "metadata": { "name": "data-science-skill", "version": "2.0.0" },
  "activeEnvironment": "dataSciencePython",
  "environments": {
    "dataSciencePython": {
      "type": "sourced",
      "archiveFile": {
        "windows": "\\\\server\\share\\DataSciencePython.zip",
        "linux": "/path/to/DataSciencePython.tar.gz"
      },
      "dest": {
        "windows": "c:\\DataSciencePython",
        "linux": "~/DataSciencePython"
      }
    },
    "devVenv": {
      "type": "venv",
      "pythonExecutable": {
        "windows": "python",
        "linux": "python3"
      },
      "path": {
        "windows": "~\\.dev-venv",
        "linux": "~/.dev-venv"
      }
    }
  }
}
```

To switch to the venv, simply change:
```json
{
  "activeEnvironment": "devVenv"
}
```

---

## Runtime Behavior

The `run-skill.sh` and `run-skill.ps1` scripts determine the Python environment:

1. Deep-merge hub config with skill config (skill overrides hub)
2. Determine `activeEnvironment`:
   - If merged config has `activeEnvironment` → use it
   - If skill has `config.json` but no `activeEnvironment` → default to `"none"`
   - If skill has no `config.json` → use hub's `activeEnvironment` (usually `"miniPython"`)
3. Look up the environment config from `environments.<activeEnvironment>`
4. Read `type` from the environment config (defaults to `"sourced"`)
5. If `type` is `"none"`: execute entrypoint directly without Python
6. If `type` is `"venv"`: use existing venv at the configured path
7. If `type` is `"sourced"`: use portable Python from the environment config

Execution details (entrypoint, arguments) are defined in each skill's SKILL.md.