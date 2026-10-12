#!/bin/bash
# Generic skill runner for Linux
# Usage: ./run-skill.sh <skill-dir> <entrypoint> [additional-args...]

set -e

SKILL_DIR="$1"
ENTRYPOINT="$2"
shift 2 2>/dev/null || true  # Remaining args are passed to the skill

if [ -z "$SKILL_DIR" ] || [ -z "$ENTRYPOINT" ]; then
    echo "Usage: $0 <skill-dir> <entrypoint> [args...]"
    exit 1
fi

# Validate entrypoint exists
if [ ! -f "$SKILL_DIR/$ENTRYPOINT" ]; then
    echo "Error: Entrypoint '$ENTRYPOINT' not found in $SKILL_DIR"
    exit 1
fi

# Helper: expand ~ to $HOME
expand_tilde() {
    local value="$1"
    [[ "$value" == "~"* ]] && value="${HOME}${value:1}"
    echo "$value"
}

# Helper: expand ~ for Python environment paths.
# Uses SKILLS_HUB_PYTHON_ENV_HOME if set, otherwise falls back to $HOME.
expand_env_tilde() {
    local value="$1"
    if [[ "$value" == "~"* ]]; then
        if [[ -n "$SKILLS_HUB_PYTHON_ENV_HOME" ]]; then
            value="${SKILLS_HUB_PYTHON_ENV_HOME}${value:1}"
        else
            value="${HOME}${value:1}"
        fi
    fi
    echo "$value"
}

# Require jq for config parsing
if ! command -v jq &>/dev/null; then
    echo "Error: jq is required but not installed" >&2
    exit 1
fi

# Determine config file: skill's config.json or skills-hub config.json
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_CONFIG="$SKILL_DIR/config.json"
HUB_CONFIG="$SCRIPT_DIR/config.json"

# Merge configs: hub as base, skill overrides (deep merge)
# jq's * operator does recursive merge: skill values override hub values
if [ -f "$HUB_CONFIG" ] && [ -f "$SKILL_CONFIG" ]; then
    MERGED_CONFIG=$(jq -s '.[0] * .[1]' "$HUB_CONFIG" "$SKILL_CONFIG")
elif [ -f "$SKILL_CONFIG" ]; then
    MERGED_CONFIG=$(cat "$SKILL_CONFIG")
elif [ -f "$HUB_CONFIG" ]; then
    MERGED_CONFIG=$(cat "$HUB_CONFIG")
else
    echo "Error: No configuration found (neither hub nor skill config)" >&2
    exit 1
fi

# Determine active environment:
# - If skill has config.json with activeEnvironment -> use it
# - If skill has config.json without activeEnvironment -> default to "none" (no Python needed)
# - If skill has no config.json -> use hub's activeEnvironment (backward compatible)
skill_has_config=false
[[ -f "$SKILL_CONFIG" ]] && skill_has_config=true

active_env=$(echo "$MERGED_CONFIG" | jq -r '.activeEnvironment // empty')

if [[ -n "$active_env" ]]; then
    ENV_NAME="$active_env"
elif [[ "$skill_has_config" == true ]]; then
    ENV_NAME="none"  # Skill has config but didn't specify env = no Python needed
else
    ENV_NAME="miniPython"  # No skill config = use hub default
fi

ENV_TYPE=$(echo "$MERGED_CONFIG" | jq -r ".environments.$ENV_NAME.type // \"sourced\"")
echo "Environment: $ENV_NAME (type: $ENV_TYPE)"

PYTHON_EXE=""

if [ "$ENV_TYPE" = "none" ]; then
    # none mode: execute entrypoint directly without Python
    echo "Running without Python environment"
    
    exec "$SKILL_DIR/$ENTRYPOINT" "$@"
elif [ -n "$SKILLS_HUB_PYTHON_PATH" ]; then
    # Explicit Python path override — skip all resolution
    PYTHON_EXE="$SKILLS_HUB_PYTHON_PATH"
    echo "Using explicit Python: $PYTHON_EXE"
elif [ "$ENV_TYPE" = "venv" ]; then
    # venv mode: use existing venv from environments.<name>
    VENV_PATH=$(expand_env_tilde "$(echo "$MERGED_CONFIG" | jq -r ".environments.$ENV_NAME.path.linux // empty")")
    VENV_PYTHON_EXE=$(expand_tilde "$(echo "$MERGED_CONFIG" | jq -r ".environments.$ENV_NAME.pythonExecutable.linux // empty")")
    
    if [ -z "$VENV_PATH" ]; then
        echo "Error: environments.$ENV_NAME.path.linux not configured" >&2
        exit 1
    fi
    
    # Resolve venv path (relative to skill dir or absolute)
    if [[ "$VENV_PATH" != /* ]]; then
        VENV_PATH="$SKILL_DIR/$VENV_PATH"
    fi
    
    PYTHON_EXE="$VENV_PATH/bin/python"
    echo "Using venv: $VENV_PATH"
    
    if [ ! -f "$PYTHON_EXE" ]; then
        echo "Error: venv not found at $VENV_PATH" >&2
        if [ -n "$VENV_PYTHON_EXE" ]; then
            echo "Create it with: $VENV_PYTHON_EXE -m venv $VENV_PATH" >&2
        fi
        exit 1
    fi
else
    # sourced mode (default): use portable Python installation from environments.<name>
    PYTHON_DEST=$(expand_env_tilde "$(echo "$MERGED_CONFIG" | jq -r ".environments.$ENV_NAME.dest.linux // empty")")

    if [ -z "$PYTHON_DEST" ]; then
        echo "Error: environments.$ENV_NAME.dest.linux not configured" >&2
        exit 1
    fi

    PYTHON_EXE="$PYTHON_DEST/bin/python"
    if [ ! -f "$PYTHON_EXE" ]; then
        echo "Error: Python environment not found at $PYTHON_EXE" >&2
        echo "Run 'skills_hub.sh --prepare-env' to install the environment" >&2
        exit 1
    fi
    echo "Using sourced environment: $PYTHON_DEST"
fi

# Execute the skill
"$PYTHON_EXE" "$SKILL_DIR/$ENTRYPOINT" "$@"
