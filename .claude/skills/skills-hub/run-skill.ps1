# Generic skill runner for Windows
# Usage: .\run-skill.ps1 -SkillDir <skill-dir> -Entrypoint <entrypoint> [additional-args...]

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$SkillDir,
    
    [Parameter(Mandatory=$true, Position=1)]
    [string]$Entrypoint,
    
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$UserArgs
)

$ErrorActionPreference = "Stop"

# Helper: Expand ~ to $HOME
function Expand-Tilde {
    param([string]$Path)
    if ($Path -and $Path.StartsWith("~")) {
        return $Path.Replace("~", $HOME)
    }
    return $Path
}

# Helper: Expand ~ for Python environment paths.
# Uses SKILLS_HUB_PYTHON_ENV_HOME if set, otherwise falls back to $HOME.
# When SKILLS_HUB_PYTHON_ENV_HOME_REMAP_ENABLED is '1', also treats
# SKILLS_HUB_PYTHON_ENV_HOME_REMAP_PATTERN (default c:\) as equivalent to ~.
function Expand-EnvTilde {
    param([string]$Path)
    if ($Path -and $Path.StartsWith("~")) {
        $rest = $Path.Substring(1)
        if ($env:SKILLS_HUB_PYTHON_ENV_HOME) {
            return $env:SKILLS_HUB_PYTHON_ENV_HOME + $rest
        }
        return $HOME + $rest
    }
    if ($env:SKILLS_HUB_PYTHON_ENV_HOME_REMAP_ENABLED -eq '1' -and $env:SKILLS_HUB_PYTHON_ENV_HOME -and $env:SKILLS_HUB_PYTHON_ENV_HOME_REMAP_PATTERN) {
        $pattern = $env:SKILLS_HUB_PYTHON_ENV_HOME_REMAP_PATTERN
        if ($Path -and $Path.Length -ge $pattern.Length -and $Path.Substring(0, $pattern.Length).ToLower() -eq $pattern.ToLower()) {
            return Join-Path $env:SKILLS_HUB_PYTHON_ENV_HOME $Path.Substring($pattern.Length)
        }
    }
    return $Path
}

# Helper: Deep merge two PSObjects (second overrides first, recursively)
function Merge-Objects {
    param($Base, $Override)
    if ($null -eq $Base) { return $Override }
    if ($null -eq $Override) { return $Base }
    
    $result = $Base.PSObject.Copy()
    foreach ($prop in $Override.PSObject.Properties) {
        if ($prop.Value -is [PSCustomObject] -and $result.PSObject.Properties[$prop.Name]) {
            $result.$($prop.Name) = Merge-Objects $result.$($prop.Name) $prop.Value
        } else {
            if ($result.PSObject.Properties[$prop.Name]) {
                $result.$($prop.Name) = $prop.Value
            } else {
                $result | Add-Member -NotePropertyName $prop.Name -NotePropertyValue $prop.Value -Force
            }
        }
    }
    return $result
}

# Validate entrypoint exists
$entrypointPath = Join-Path $SkillDir $Entrypoint
if (-not (Test-Path $entrypointPath)) {
    Write-Error "Error: Entrypoint '$Entrypoint' not found in $SkillDir"
    exit 1
}

# Determine config files: skill's config.json or skills-hub config.json
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillConfigPath = Join-Path $SkillDir "config.json"
$HubConfigPath = Join-Path $ScriptDir "config.json"

# Load and merge configs: hub as base, skill overrides (deep merge)
$hubConfigData = $null
$skillConfigData = $null

if (Test-Path $HubConfigPath) {
    $hubConfigData = Get-Content $HubConfigPath -Raw | ConvertFrom-Json
}
if (Test-Path $SkillConfigPath) {
    $skillConfigData = Get-Content $SkillConfigPath -Raw | ConvertFrom-Json
}

if (-not $hubConfigData -and -not $skillConfigData) {
    Write-Error "Error: No configuration found (neither hub nor skill config)"
    exit 1
}

$mergedConfig = Merge-Objects $hubConfigData $skillConfigData

# Determine active environment:
# - If skill has config.json with activeEnvironment -> use it
# - If skill has config.json without activeEnvironment -> default to "none" (no Python needed)
# - If skill has no config.json -> use hub's activeEnvironment (backward compatible)
$envName = $null
if ($mergedConfig.activeEnvironment) {
    $envName = $mergedConfig.activeEnvironment
} elseif ($skillConfigData) {
    $envName = "none"  # Skill has config but didn't specify env = no Python needed
} else {
    $envName = "miniPython"  # No skill config = use hub default
}

$envType = "sourced"
if ($mergedConfig.environments -and $mergedConfig.environments.$envName -and $mergedConfig.environments.$envName.type) {
    $envType = $mergedConfig.environments.$envName.type
}
Write-Output "Environment: $envName (type: $envType)"

# Get environment-specific config from environments.<name>
$envConfig = $null
if ($mergedConfig.environments -and $mergedConfig.environments.$envName) {
    $envConfig = $mergedConfig.environments.$envName
}

$pythonExe = $null

if ($envType -eq "none") {
    # none mode: execute entrypoint directly without Python
    Write-Output "Running without Python environment"
    
    & $entrypointPath @UserArgs
    exit $LASTEXITCODE
} elseif ($env:SKILLS_HUB_PYTHON_PATH) {
    # Explicit Python path override — skip all resolution
    $pythonExe = $env:SKILLS_HUB_PYTHON_PATH
    Write-Output "Using explicit Python: $pythonExe"
} elseif ($envType -eq "venv") {
    # venv mode: use existing venv from environments.<name>
    $venvPath = $null
    $venvPythonExe = $null
    
    if ($envConfig) {
        $venvPath = Expand-EnvTilde $envConfig.path.windows
        $venvPythonExe = Expand-Tilde $envConfig.pythonExecutable.windows
    }
    
    if (-not $venvPath) {
        Write-Error "Error: environments.$envName.path.windows not configured"
        exit 1
    }
    
    # Resolve venv path (relative to skill dir or absolute)
    if (-not [System.IO.Path]::IsPathRooted($venvPath)) {
        $venvPath = Join-Path $SkillDir $venvPath
    }
    
    $pythonExe = Join-Path $venvPath "Scripts\python.exe"
    Write-Output "Using venv: $venvPath"
    
    if (-not (Test-Path $pythonExe)) {
        Write-Error "Error: venv not found at $venvPath"
        if ($venvPythonExe) {
            Write-Error "Create it with: $venvPythonExe -m venv $venvPath"
        }
        exit 1
    }
} else {
    # sourced mode (default): use portable Python installation from environments.<name>
    $PythonDest = $null

    if ($envConfig -and $envConfig.dest) {
        $PythonDest = Expand-EnvTilde $envConfig.dest.windows
    }

    if (-not $PythonDest) {
        Write-Error "Error: environments.$envName.dest.windows not configured"
        exit 1
    }

    $pythonExe = Join-Path $PythonDest "python.exe"
    if (-not (Test-Path $pythonExe)) {
        Write-Error "Error: Python environment not found at $pythonExe"
        Write-Error "Run 'skills_hub.ps1 -PrepareEnv' to install the environment"
        exit 1
    }
    Write-Output "Using sourced environment: $PythonDest"
}

# Build argument list - use full path to entrypoint
# -s prevents loading packages from user site-packages (AppData\Roaming\Python\...)
# which can conflict with the skill's portable environment and cause segfaults
$allArgs = @("-s", $entrypointPath)
if ($UserArgs) {
    $allArgs += $UserArgs
}

# Execute the skill
& $pythonExe @allArgs
