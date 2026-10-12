#!/bin/bash
# Skills Hub Manager - Linux/macOS Version (Simplified)
# Manages skill listing, downloading, and updating

set -e

# Single-slot archive cache (no normalization): keep at most one downloaded temp archive at a time.
CURRENT_ARCHIVE_KEY_FILE="/tmp/skills-hub-archive-key"
CURRENT_TEMP_ARCHIVE_PATH="/tmp/skills-hub-archive-current"

cleanup_archive_slot() {
    rm -f "$CURRENT_TEMP_ARCHIVE_PATH" "${CURRENT_TEMP_ARCHIVE_PATH}.part" "$CURRENT_ARCHIVE_KEY_FILE"
}

# Ensure deterministic cleanup on normal exit and most interrupted exits.
trap cleanup_archive_slot EXIT INT TERM

# Remove stale slot files from previous interrupted runs.
cleanup_archive_slot

# Parse command line arguments
SKILLS=()
LIST_ONLY=false
PREPARE_ENV=false
UPDATE=false
FORCE=false
EXACT=false
CONFIRM_ALL=false
CONFIG_FILE=""
SRC_ROOT_OVERRIDE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --list-only|-l) LIST_ONLY=true; shift ;;
        --prepare-env|-p) PREPARE_ENV=true; shift ;;
        --update|-u) UPDATE=true; shift ;;
        --force|-f) FORCE=true; shift ;;
        --exact|-e) EXACT=true; shift ;;
        --confirm-all|-y) CONFIRM_ALL=true; shift ;;
        --config|-c) CONFIG_FILE="$2"; shift 2 ;;
        --src-root) SRC_ROOT_OVERRIDE="$2"; shift 2 ;;
        --skills|-s)
            shift
            while [[ $# -gt 0 ]] && [[ ! $1 =~ ^- ]]; do
                SKILLS+=("$1"); shift
            done
            ;;
        *) SKILLS+=("$1"); shift ;;
    esac
done

# Determine config file path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${CONFIG_FILE:-$SCRIPT_DIR/config.json}"

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Error: Configuration file not found at $CONFIG_FILE" >&2
    exit 1
fi

if ! command -v jq &>/dev/null; then
    echo "Error: jq is required but not installed" >&2
    exit 1
fi

# Helper: expand ~ to $HOME
expand_tilde() {
    local value="$1"
    if [[ "$value" == "~"* ]]; then value="${HOME}${value:1}"; fi
    echo "$value"
}

# Helper: resolve a config path with env var override, tilde expansion.
resolve_config_path() {
    local env_val="$1" config_val="$2" default_val="$3"
    local val="${env_val:-${config_val:-$default_val}}"
    echo "$(expand_tilde "$val")"
}

# Entity proxy types: marker|envvar|config_field|extension|default_dir
# Each proxied entity type copies its marker file to .github/<type>/ for GHCP.
ENTITY_PROXY_TYPES=(
    "AGENT.md|SKILLS_HUB_AGENT_PROXY_DIR|agentProxyDir|.agent.md|.github/agents"
    "PROMPT.md|SKILLS_HUB_PROMPT_PROXY_DIR|promptProxyDir|.prompt.md|.github/prompts"
    "CHATMODE.md|SKILLS_HUB_CHATMODE_PROXY_DIR|chatmodeProxyDir|.chatmode.md|.github/modes"
    "INSTRUCTIONS.md|SKILLS_HUB_INSTRUCTIONS_PROXY_DIR|instructionsProxyDir|.instructions.md|.github/instructions"
)

# Helper: resolve proxy dir for a given entity proxy type spec.
_resolve_proxy_dir() {
    local env_var="$1" config_field="$2" default_dir="$3"
    local env_val="${!env_var:-}"
    local config_val=""
    # Try proxyDirs map first, then legacy agentProxyDir for agents
    config_val=$(jq -r ".general.proxyDirs.$config_field // empty" "$CONFIG_FILE" 2>/dev/null || true)
    if [[ -z "$config_val" && "$config_field" == "agentProxyDir" ]]; then
        config_val=$(jq -r '.general.agentProxyDir // empty' "$CONFIG_FILE" 2>/dev/null || true)
    fi
    resolve_config_path "$env_val" "$config_val" "$default_dir"
}

# Helper: copy entity marker files as proxies for all proxied entity types.
copy_entity_proxies() {
    local dest="$1" skill_name="$2"
    for spec in "${ENTITY_PROXY_TYPES[@]}"; do
        IFS='|' read -r marker env_var config_field extension default_dir <<< "$spec"
        if [[ -f "$dest/$marker" ]]; then
            local proxy_dir
            proxy_dir=$(_resolve_proxy_dir "$env_var" "$config_field" "$default_dir")
            mkdir -p "$proxy_dir"
            cp "$dest/$marker" "$proxy_dir/${skill_name}${extension}"
            touch -r "$dest/$marker" "$proxy_dir/${skill_name}${extension}"
            echo "  Entity proxy created: $proxy_dir/${skill_name}${extension}"
        fi
    done
}

# Helper: clean up a failed skill install (dest folder + all entity proxies).
remove_failed_skill() {
    local dest="$1" skill_name="$2"
    if [[ -d "$dest" ]]; then rm -rf "$dest"; fi
    for spec in "${ENTITY_PROXY_TYPES[@]}"; do
        IFS='|' read -r marker env_var config_field extension default_dir <<< "$spec"
        local proxy_dir
        proxy_dir=$(_resolve_proxy_dir "$env_var" "$config_field" "$default_dir")
        if [[ -f "$proxy_dir/${skill_name}${extension}" ]]; then
            rm -f "$proxy_dir/${skill_name}${extension}"
        fi
    done
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

is_http_url() {
    local value="$1"
    [[ "$value" =~ ^https?:// ]]
}

is_github_url() {
    local value="$1"
    [[ "$value" =~ ^(https?://)?(github\.com|raw\.githubusercontent\.com)/ ]]
}

# Cache for GitHub token so we only call GCM once per script run
_GITHUB_TOKEN=""
_GITHUB_TOKEN_RESOLVED=false

get_github_token() {
    if $_GITHUB_TOKEN_RESOLVED; then
        echo "$_GITHUB_TOKEN"
        return
    fi
    _GITHUB_TOKEN_RESOLVED=true

    # Prefer token injected by the VS Code extension
    if [[ -n "${GITHUB_TOKEN:-}" ]]; then
        _GITHUB_TOKEN="$GITHUB_TOKEN"
        echo "  [auth] Using injected GitHub token" >&2
        echo "$_GITHUB_TOKEN"
        return
    fi

    local result
    result=$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill 2>/dev/null) || true
    if [[ -n "$result" ]]; then
        local line
        while IFS= read -r line; do
            if [[ "$line" =~ ^password=(.+)$ ]]; then
                _GITHUB_TOKEN="${BASH_REMATCH[1]}"
                echo "  [auth] Using GCM credential" >&2
                echo "$_GITHUB_TOKEN"
                return
            fi
        done <<< "$result"
    fi
    echo "  [auth] No GitHub token available" >&2
    echo ""
}

to_github_raw_url() {
    local url="$1"

    if [[ "$url" =~ ^github\.com/ ]]; then
        url="https://$url"
    fi

    if [[ "$url" =~ ^https?://raw\.githubusercontent\.com/ ]]; then
        echo "$url"
        return
    fi

    if [[ "$url" =~ ^https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$ ]]; then
        local owner="${BASH_REMATCH[1]}"
        local repo="${BASH_REMATCH[2]}"
        local branch="${BASH_REMATCH[3]}"
        local file_path="${BASH_REMATCH[4]}"
        echo "https://raw.githubusercontent.com/${owner}/${repo}/${branch}/${file_path}"
        return
    fi

    if [[ "$url" =~ ^https?://github\.com/([^/]+)/([^/]+)/raw/([^/]+)/(.+)$ ]]; then
        local owner="${BASH_REMATCH[1]}"
        local repo="${BASH_REMATCH[2]}"
        local branch="${BASH_REMATCH[3]}"
        local file_path="${BASH_REMATCH[4]}"
        echo "https://raw.githubusercontent.com/${owner}/${repo}/${branch}/${file_path}"
        return
    fi

    if [[ "$url" =~ ^https?://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.+)$ ]]; then
        local owner="${BASH_REMATCH[1]}"
        local repo="${BASH_REMATCH[2]}"
        local branch="${BASH_REMATCH[3]}"
        local file_path="${BASH_REMATCH[4]}"
        echo "https://raw.githubusercontent.com/${owner}/${repo}/${branch}/${file_path}"
        return
    fi

    if [[ "$url" =~ ^https?://github\.com/([^/]+)/([^/]+)/(.+)$ ]]; then
        local owner="${BASH_REMATCH[1]}"
        local repo="${BASH_REMATCH[2]}"
        local file_path="${BASH_REMATCH[3]}"
        echo "https://raw.githubusercontent.com/${owner}/${repo}/main/${file_path}"
        return
    fi

    echo ""
}

download_archive_to_temp() {
    local archive_url="$1"

    if ! is_github_url "$archive_url"; then
        echo "Error: only GitHub archive URLs are supported. Received: $archive_url" >&2
        return 1
    fi

    local download_url
    download_url=$(to_github_raw_url "$archive_url")
    if [[ -z "$download_url" || ! "$download_url" =~ ^https?://raw\.githubusercontent\.com/[^/]+/[^/]+/[^/]+/.+$ ]]; then
        echo "Error: invalid GitHub archive path (must point to a file in a repository): $archive_url" >&2
        return 1
    fi

    local cached_key
    cached_key=$(cat "$CURRENT_ARCHIVE_KEY_FILE" 2>/dev/null)

    if [[ "$cached_key" == "$archive_url" && -f "$CURRENT_TEMP_ARCHIVE_PATH" ]]; then
        echo "  Reusing downloaded archive slot for: $archive_url" >&2
        echo "$CURRENT_TEMP_ARCHIVE_PATH"
        return 0
    fi

    if [[ -n "$cached_key" && -f "$CURRENT_TEMP_ARCHIVE_PATH" ]]; then
        echo "  Replacing archive slot with: $archive_url" >&2
    fi
    cleanup_archive_slot

    local temp_part="${CURRENT_TEMP_ARCHIVE_PATH}.part"

    local gh_token
    gh_token=$(get_github_token)

    echo "  Downloading archive to slot: $archive_url" >&2
    if command -v curl &>/dev/null; then
        if [[ -n "$gh_token" ]]; then
            HTTP_PROXY="$HTTP_PROXY" HTTPS_PROXY="$HTTPS_PROXY" curl --fail --location --progress-bar --connect-timeout 10 --max-time 300 -H "Authorization: Bearer $gh_token" "$download_url" -o "$temp_part"
        else
            HTTP_PROXY="$HTTP_PROXY" HTTPS_PROXY="$HTTPS_PROXY" curl --fail --location --progress-bar --connect-timeout 10 --max-time 300 "$download_url" -o "$temp_part"
        fi
    elif command -v wget &>/dev/null; then
        if [[ -n "$gh_token" ]]; then
            HTTP_PROXY="$HTTP_PROXY" HTTPS_PROXY="$HTTPS_PROXY" wget --header="Authorization: Bearer $gh_token" -qO "$temp_part" "$download_url"
        else
            HTTP_PROXY="$HTTP_PROXY" HTTPS_PROXY="$HTTPS_PROXY" wget -qO "$temp_part" "$download_url"
        fi
    else
        echo "Error: neither curl nor wget is available for URL archive download" >&2
        rm -f "$temp_part"
        return 1
    fi

    mv -f "$temp_part" "$CURRENT_TEMP_ARCHIVE_PATH"
    echo "$archive_url" > "$CURRENT_ARCHIVE_KEY_FILE"
    echo "$CURRENT_TEMP_ARCHIVE_PATH"
}

# Read config values
DEST_ROOT=$(resolve_config_path "$SKILLS_HUB_DESTROOT" "$(jq -r '.general.destRoot // empty' "$CONFIG_FILE")" ".claude/skills")
if [[ -n "$SKILLS_HUB_PYTHON_ENV_HOME" ]]; then
    echo "Using SKILLS_HUB_PYTHON_ENV_HOME=$SKILLS_HUB_PYTHON_ENV_HOME for Python environment paths"
fi
SRC_ROOT=$(expand_tilde "$(jq -r '.srcRoot.linux // empty' "$CONFIG_FILE")")

# Override SRC_ROOT if --src-root was provided
if [[ -n "$SRC_ROOT_OVERRIDE" ]]; then
    SRC_ROOT=$(expand_tilde "$SRC_ROOT_OVERRIDE")
    echo "Using override source root: $SRC_ROOT"
fi

# Read active environment name and get type from within the environment config
ENV_NAME=$(jq -r '.activeEnvironment // "miniPython"' "$CONFIG_FILE")
ENV_TYPE=$(jq -r ".environments.$ENV_NAME.type // \"sourced\"" "$CONFIG_FILE")

# Read environment-specific settings from environments.<name>
MINI_PYTHON_ARCHIVE=$(expand_tilde "$(jq -r ".environments.$ENV_NAME.archiveFile.linux // .environments.miniPython.archiveFile.linux // empty" "$CONFIG_FILE")")
MINI_PYTHON_DEST=$(expand_env_tilde "$(jq -r ".environments.$ENV_NAME.dest.linux // .environments.miniPython.dest.linux // empty" "$CONFIG_FILE")")
MINI_PYTHON_EXTRACT_TO=$(dirname "$MINI_PYTHON_DEST")
USE_SUDO=$(jq -r ".environments.$ENV_NAME.useSudo.linux // \"false\"" "$CONFIG_FILE")
HTTP_PROXY=$(jq -r '.proxy.http // empty' "$CONFIG_FILE")
HTTPS_PROXY=$(jq -r '.proxy.https // empty' "$CONFIG_FILE")

SUDO_CMD=""
if [[ "$USE_SUDO" == "true" ]]; then SUDO_CMD="sudo"; fi

# Helper: compare semver versions (returns 0 if v1 > v2, 1 otherwise)
# Missing version treated as "0.0.0"
version_greater() {
    local v1="${1:-0.0.0}"
    local v2="${2:-0.0.0}"
    
    # Split versions into arrays
    IFS='.' read -ra V1_PARTS <<< "$v1"
    IFS='.' read -ra V2_PARTS <<< "$v2"
    
    # Compare each part (major, minor, patch)
    for i in 0 1 2; do
        local p1="${V1_PARTS[$i]:-0}"
        local p2="${V2_PARTS[$i]:-0}"
        # Remove non-numeric suffixes for comparison
        p1="${p1%%[^0-9]*}"
        p2="${p2%%[^0-9]*}"
        p1="${p1:-0}"
        p2="${p2:-0}"
        
        if (( p1 > p2 )); then
            return 0  # v1 > v2
        elif (( p1 < p2 )); then
            return 1  # v1 < v2
        fi
    done
    return 1  # v1 == v2, not greater
}

# Handle PrepareEnv
if [[ "$PREPARE_ENV" == true ]]; then
    if [[ -d "$MINI_PYTHON_DEST" && -n "$(ls -A "$MINI_PYTHON_DEST" 2>/dev/null)" ]]; then
        echo "$MINI_PYTHON_DEST already exists and is not empty -- skipping."
    else
        if [[ -d "$MINI_PYTHON_DEST" ]]; then
            echo "$MINI_PYTHON_DEST exists but is empty -- will re-extract."
        else
            echo "$MINI_PYTHON_DEST does not exist -- will extract."
        fi
        resolved_archive="$MINI_PYTHON_ARCHIVE"
        if is_http_url "$MINI_PYTHON_ARCHIVE" || is_github_url "$MINI_PYTHON_ARCHIVE"; then
            resolved_archive=$(download_archive_to_temp "$MINI_PYTHON_ARCHIVE") || exit 1
        fi
        if [[ ! -f "$resolved_archive" ]]; then
            echo "Error: Archive not found at $MINI_PYTHON_ARCHIVE" >&2
            exit 1
        fi
        echo "Preparing MiniPython from $MINI_PYTHON_ARCHIVE..."
        $SUDO_CMD mkdir -p "$MINI_PYTHON_EXTRACT_TO"
        $SUDO_CMD tar -xzf "$resolved_archive" -C "$MINI_PYTHON_EXTRACT_TO"
        extracted_name=$(tar -tzf "$resolved_archive" | head -1 | cut -d'/' -f1)
        extracted_path="$MINI_PYTHON_EXTRACT_TO/$extracted_name"
        if [[ "$extracted_path" != "$MINI_PYTHON_DEST" && -d "$extracted_path" ]]; then
            if [[ -d "$MINI_PYTHON_DEST" ]]; then
                # Dest exists (possibly a symlink) -- move contents into it
                $SUDO_CMD cp -a "$extracted_path/." "$MINI_PYTHON_DEST/"
                $SUDO_CMD rm -rf "$extracted_path"
            else
                $SUDO_CMD mv "$extracted_path" "$MINI_PYTHON_DEST"
            fi
        fi
        echo "$MINI_PYTHON_DEST has been prepared."
    fi
    exit 0
fi

# Identify Skills
TARGET_SKILLS=()

# Helper: Check if skills-hub is explicitly requested
SKILLS_HUB_EXPLICITLY_REQUESTED=false
for pattern in "${SKILLS[@]}"; do
    if [[ "skills-hub" == *"$pattern"* ]]; then
        SKILLS_HUB_EXPLICITLY_REQUESTED=true
        break
    fi
done

if [[ "$UPDATE" == true ]]; then
    echo "Checking for installed skills in $DEST_ROOT..."
    if [[ -d "$DEST_ROOT" ]]; then
        # Exclude skills-hub unless explicitly requested
        if [[ "$SKILLS_HUB_EXPLICITLY_REQUESTED" == true ]]; then
            mapfile -t INSTALLED < <(find "$DEST_ROOT" -maxdepth 1 -type d ! -name "_*" ! -path "$DEST_ROOT" -exec basename {} \;)
        else
            mapfile -t INSTALLED < <(find "$DEST_ROOT" -maxdepth 1 -type d ! -name "_*" ! -name "skills-hub" ! -path "$DEST_ROOT" -exec basename {} \;)
        fi
        
        # If specific skills are requested, filter to only those
        if [[ ${#SKILLS[@]} -gt 0 ]]; then
            FILTERED_INSTALLED=()
            for name in "${INSTALLED[@]}"; do
                for pattern in "${SKILLS[@]}"; do
                    if [[ "$EXACT" == true ]]; then
                        if [[ "$name" == "$pattern" ]]; then
                            FILTERED_INSTALLED+=("$name")
                            break
                        fi
                    else
                        if [[ "$name" == *"$pattern"* ]]; then
                            FILTERED_INSTALLED+=("$name")
                            break
                        fi
                    fi
                done
            done
            INSTALLED=("${FILTERED_INSTALLED[@]}")
        fi
        
        for name in "${INSTALLED[@]}"; do
            if [[ -d "$SRC_ROOT/$name" ]]; then TARGET_SKILLS+=("$SRC_ROOT/$name"); echo " - Found: $name"; fi
        done
    fi
elif [[ ${#SKILLS[@]} -eq 0 ]]; then
    # No filter provided: exclude skills-hub
    if [[ -d "$SRC_ROOT" ]]; then mapfile -t TARGET_SKILLS < <(find "$SRC_ROOT" -maxdepth 1 -type d ! -name "_*" ! -name "skills-hub" ! -path "$SRC_ROOT"); fi
else
    for pattern in "${SKILLS[@]}"; do
        # Exclude skills-hub unless explicitly requested
        find_pattern=""
        if [[ "$EXACT" == true ]]; then
            find_pattern="$pattern"
        else
            find_pattern="*$pattern*"
        fi
        if [[ "$SKILLS_HUB_EXPLICITLY_REQUESTED" == true ]]; then
            mapfile -t MATCHES < <(find "$SRC_ROOT" -maxdepth 1 -type d -name "$find_pattern" ! -name "_*")
        else
            mapfile -t MATCHES < <(find "$SRC_ROOT" -maxdepth 1 -type d -name "$find_pattern" ! -name "_*" ! -name "skills-hub")
        fi
        TARGET_SKILLS+=("${MATCHES[@]}")
    done
fi

if [[ ${#TARGET_SKILLS[@]} -eq 0 ]]; then echo "No skills identified."; exit 0; fi

# List only
if [[ "$LIST_ONLY" == true ]]; then
    echo -e "\nAvailable skills:"
    for skill in "${TARGET_SKILLS[@]}"; do echo " - $(basename "$skill")"; done
    exit 0
fi

# Confirm
echo -e "\nSkills to download/update:"
for skill in "${TARGET_SKILLS[@]}"; do echo " - $(basename "$skill")"; done
echo ""
if [[ "$CONFIRM_ALL" != true ]]; then
    read -p "Proceed? (y/n) " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then echo "Cancelled."; exit 0; fi
fi

# Download/Update Skills
success_count=0
FAILED_INSTALLS=()
_env_report_file="/tmp/skills-hub-env-report-$$"
rm -f "$_env_report_file"
for skill in "${TARGET_SKILLS[@]}"; do
    set +e  # Disable set -e for the loop body; the subshell has its own set -e
    skill_name=$(basename "$skill")
    dest="$DEST_ROOT/$skill_name"
    
    # Version check for update mode only (skip if force is enabled)
    if [[ "$UPDATE" == true && -d "$dest" ]]; then
        if [[ "$FORCE" == true ]]; then
            echo "Force updating: $skill_name..."
        else
            installed_version=""
            source_version=""
            
            # Get installed version (missing = treat as lower)
            if [[ -f "$dest/config.json" ]]; then
                installed_version=$(jq -r '.metadata.version // empty' "$dest/config.json" 2>/dev/null)
            fi
            
            # Get source version
            if [[ -f "$skill/config.json" ]]; then
                source_version=$(jq -r '.metadata.version // empty' "$skill/config.json" 2>/dev/null)
            fi
            
            # If both versions exist, compare them
            if [[ -n "$installed_version" && -n "$source_version" ]]; then
                if ! version_greater "$source_version" "$installed_version"; then
                    echo "Skipping: $skill_name (installed: $installed_version, source: $source_version)"
                    continue
                fi
                echo "Updating: $skill_name ($installed_version -> $source_version)"
            else
                # Missing version = treat local as lower, proceed with update
                echo "Updating: $skill_name (version missing, forcing update)"
            fi
        fi
    else
        echo "Downloading: $skill_name..."
    fi
    
    if [[ -d "$dest" ]]; then rm -rf "$dest"; fi
    mkdir -p "$DEST_ROOT"
    if ! cp -r "$skill" "$dest"; then
        echo "  FAILED: $skill_name - file copy failed"
        remove_failed_skill "$dest" "$skill_name"
        FAILED_INSTALLS+=("$skill_name")
        continue
    fi
    
    # Run install body in a subshell so failures don't abort the entire script.
    _err_file="/tmp/skills-hub-err-$$-$skill_name"
    rm -f "$_err_file"
    (
    set -e
    # Helper: record error reason and exit subshell
    fail_install() { echo "$1" > "$_err_file"; exit 1; }
    # Helper: record environment creation (appends to shared report file)
    record_env_created() { echo "$1|$2|$3|$4" >> "$_env_report_file"; }
    # Load skill config and merge with hub config
    skill_config="$dest/config.json"
    skill_has_config=false
    if [[ -f "$skill_config" ]]; then skill_has_config=true; fi
    
    # Merge configs: hub as base, skill overrides (deep merge)
    if [[ "$skill_has_config" == true ]]; then
        merged_config=$(jq -s '.[0] * .[1]' "$CONFIG_FILE" "$skill_config")
    else
        merged_config=$(cat "$CONFIG_FILE")
    fi
    
    # Determine active environment:
    # - If skill has config.json with activeEnvironment -> use it
    # - If skill has config.json without activeEnvironment -> default to "none" (no Python needed)
    # - If skill has no config.json -> use hub's activeEnvironment (backward compatible)
    skill_active_env=""
    if [[ "$skill_has_config" == true ]]; then
        skill_active_env=$(jq -r '.activeEnvironment // empty' "$skill_config" 2>/dev/null)
    fi
    
    if [[ -n "$skill_active_env" ]]; then
        env_name="$skill_active_env"
    elif [[ "$skill_has_config" == true ]]; then
        env_name="none"  # Skill has config but didn't specify env = no Python needed
    else
        env_name=$(echo "$merged_config" | jq -r '.activeEnvironment // "miniPython"')  # No skill config = use hub default
    fi
    
    env_type=$(echo "$merged_config" | jq -r ".environments.$env_name.type // \"sourced\"")
    echo "  Environment: $env_name (type: $env_type)"
    
    # Handle 'none' type - skip environment preparation entirely
    if [[ "$env_type" == "none" ]]; then
        echo "  No Python environment required"
        copy_entity_proxies "$dest" "$skill_name"
        echo "  Done: $skill_name"
        exit 0
    fi
    
    # Skip Python environment setup if SKILLS_HUB_SKIP_PYTHON_ENV=1
    if [[ "$SKILLS_HUB_SKIP_PYTHON_ENV" == "1" ]]; then
        echo "  [SKIP_PYTHON_ENV] Skipping Python environment setup and pip install for '$skill_name'"
    else

    req_file="$dest/requirements.txt"
    has_requirements=false
    if [[ -f "$req_file" ]]; then has_requirements=true; fi
    
    PYTHON_EXE=""
    
    if [[ "$env_type" == "venv" ]]; then
        # venv mode: use existing venv from environments.<name>
        venv_path=$(expand_env_tilde "$(echo "$merged_config" | jq -r ".environments.$env_name.path.linux // empty")")
        venv_python_exe=$(expand_tilde "$(echo "$merged_config" | jq -r ".environments.$env_name.pythonExecutable.linux // empty")")
        
        if [[ -z "$venv_path" ]]; then
            echo "Error: environments.$env_name.path.linux is not configured for skill '$skill_name'" >&2
            fail_install "venv path not configured"
        fi
        
        # Resolve venv path (relative to skill dir or absolute)
        if [[ "$venv_path" != /* ]]; then
            venv_path="$dest/$venv_path"
        fi
        
        PYTHON_EXE="$venv_path/bin/python"
        echo "  Using venv: $venv_path"
        
        if [[ ! -f "$PYTHON_EXE" ]]; then
            echo "Error: venv not found at $venv_path for skill '$skill_name'" >&2
            if [[ -n "$venv_python_exe" ]]; then
                echo "  Create it with: $venv_python_exe -m venv $venv_path" >&2
            fi
            fail_install "venv not found at $venv_path"
        fi
    else
        # sourced mode (default): use portable Python from environments.<name>
        skill_python_dest=$(expand_env_tilde "$(echo "$merged_config" | jq -r ".environments.$env_name.dest.linux // empty")")
        skill_archive=$(expand_tilde "$(echo "$merged_config" | jq -r ".environments.$env_name.archiveFile.linux // empty")")
        skill_use_sudo=$(echo "$merged_config" | jq -r ".environments.$env_name.useSudo.linux // \"false\"")
        skill_sudo_cmd=""
        if [[ "$skill_use_sudo" == "true" ]]; then skill_sudo_cmd="sudo"; fi
        
        # Prepare sourced environment if needed (also re-extract if dest is empty)
        if [[ -d "$skill_python_dest" && -n "$(ls -A "$skill_python_dest" 2>/dev/null)" ]]; then
            echo "  Environment exists at $skill_python_dest"
        elif [[ -z "$skill_python_dest" ]]; then
            echo "Error: No dest.linux configured for environment '$env_name' (skill '$skill_name')" >&2
            fail_install "no dest.linux configured for environment '$env_name'"
        else
            resolved_skill_archive="$skill_archive"
            if is_http_url "$skill_archive" || is_github_url "$skill_archive"; then
                if ! resolved_skill_archive=$(download_archive_to_temp "$skill_archive"); then
                    echo "Error: archive download failed at '$skill_archive' for skill '$skill_name'" >&2
                    fail_install "archive download failed"
                fi
            fi

            if [[ -z "$resolved_skill_archive" || ! -f "$resolved_skill_archive" ]]; then
                echo "Error: environment archive not found at '$skill_archive' for skill '$skill_name'" >&2
                fail_install "environment archive not found"
            else
                if [[ -d "$skill_python_dest" ]]; then
                    echo "  Preparing environment at $skill_python_dest (exists but empty)..."
                else
                    echo "  Preparing environment at $skill_python_dest..."
                fi
                skill_extract_to=$(dirname "$skill_python_dest")
                $skill_sudo_cmd mkdir -p "$skill_extract_to"
                $skill_sudo_cmd tar -xzf "$resolved_skill_archive" -C "$skill_extract_to"
                record_env_created "$env_name" "sourced" "$skill_python_dest" "$skill_archive"
                extracted_name=$(tar -tzf "$resolved_skill_archive" | head -1 | cut -d'/' -f1)
                extracted_path="$skill_extract_to/$extracted_name"
                if [[ "$extracted_path" != "$skill_python_dest" && -d "$extracted_path" ]]; then
                    if [[ -d "$skill_python_dest" ]]; then
                        # Dest exists (possibly a symlink) -- move contents into it
                        $skill_sudo_cmd cp -a "$extracted_path/." "$skill_python_dest/"
                        $skill_sudo_cmd rm -rf "$extracted_path"
                    else
                        $skill_sudo_cmd mv "$extracted_path" "$skill_python_dest"
                    fi
                fi
            fi
        fi

        PYTHON_EXE="$skill_python_dest/bin/python"
        if [[ ! -f "$PYTHON_EXE" ]]; then
            echo "Error: Python executable not found at '$PYTHON_EXE' for environment '$env_name' (skill '$skill_name')" >&2
            fail_install "Python executable not found"
        fi
        echo "  Using sourced environment: $skill_python_dest"
    fi
    
    # Install dependencies only if requirements.txt exists
    if [[ "$has_requirements" == true ]]; then
        echo "  Installing dependencies..."
        export HTTP_PROXY="$HTTP_PROXY" HTTPS_PROXY="$HTTPS_PROXY"
        PYTHONNOUSERSITE=1 "$PYTHON_EXE" -m pip install -r "$req_file" --disable-pip-version-check --no-warn-script-location
    else
        echo "  No requirements.txt found, skipping dependency installation"
    fi

    fi # end SKILLS_HUB_SKIP_PYTHON_ENV gate

    copy_entity_proxies "$dest" "$skill_name"

    echo "  Done: $skill_name"
    )
    subshell_rc=$?
    if [[ $subshell_rc -ne 0 ]]; then
        _err_reason=""
        if [[ -f "$_err_file" ]]; then
            _err_reason=$(cat "$_err_file")
            rm -f "$_err_file"
        fi
        echo "  FAILED: $skill_name${_err_reason:+ - $_err_reason}"
        remove_failed_skill "$dest" "$skill_name"
        FAILED_INSTALLS+=("$skill_name${_err_reason:+: $_err_reason}")
    else
        ((success_count++))
    fi
done
set -e  # Re-enable for post-loop code

echo -e "\nSuccessfully installed: $success_count"

if [[ ${#FAILED_INSTALLS[@]} -gt 0 ]]; then
    echo -e "\nFailed installs (${#FAILED_INSTALLS[@]}):"
    for name in "${FAILED_INSTALLS[@]}"; do
        echo "  - $name"
    done
    echo ""
fi

if [[ -f "$_env_report_file" ]]; then
    # Deduplicate by path (3rd field)
    mapfile -t _env_lines < <(sort -t'|' -k3 -u "$_env_report_file")
    echo -e "Environments created (${#_env_lines[@]}):"
    for line in "${_env_lines[@]}"; do
        IFS='|' read -r _name _type _path _archive <<< "$line"
        echo "  - $_name ($_type): $_path"
        echo "    Archive: $_archive"
    done
    rm -f "$_env_report_file"
    echo ""
fi

if [[ ${#FAILED_INSTALLS[@]} -eq 0 ]]; then
    echo -e "Operation completed."
fi
