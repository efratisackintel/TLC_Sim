# Skills Hub Manager - Windows Version (Simplified)
# Manages skill listing, downloading, and updating

param(
    [string[]]$Skills = @(),
    [switch]$ListOnly,
    [switch]$PrepareEnv,
    [switch]$Update,
    [switch]$Force,
    [switch]$Exact,
    [switch]$ConfirmAll,
    [string]$ConfigFile = "",
    [string]$SrcRoot = ""
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

# Helper: Resolve a config path with env var override, tilde expansion.
function Resolve-ConfigPath {
    param([string]$EnvValue, [string]$ConfigValue, [string]$Default)
    $val = if ($EnvValue) { $EnvValue } elseif ($ConfigValue) { $ConfigValue } else { $Default }
    return Expand-Tilde $val
}

# Entity type proxy mapping: marker file -> (proxy dir env var suffix, proxy file extension, config field)
# Each proxied entity type copies its marker file to .github/<type>/ for GHCP.
$EntityProxyTypes = @(
    @{ Marker = 'AGENT.md';        EnvVar = 'SKILLS_HUB_AGENT_PROXY_DIR';        ConfigField = 'agentProxyDir';        Extension = '.agent.md';        DefaultDir = '.github/agents' }
    @{ Marker = 'PROMPT.md';        EnvVar = 'SKILLS_HUB_PROMPT_PROXY_DIR';       ConfigField = 'promptProxyDir';       Extension = '.prompt.md';       DefaultDir = '.github/prompts' }
    @{ Marker = 'CHATMODE.md';      EnvVar = 'SKILLS_HUB_CHATMODE_PROXY_DIR';     ConfigField = 'chatmodeProxyDir';     Extension = '.chatmode.md';     DefaultDir = '.github/modes' }
    @{ Marker = 'INSTRUCTIONS.md';  EnvVar = 'SKILLS_HUB_INSTRUCTIONS_PROXY_DIR'; ConfigField = 'instructionsProxyDir'; Extension = '.instructions.md'; DefaultDir = '.github/instructions' }
)

# Helper: Resolve proxy directory for a given entity proxy type descriptor.
function Resolve-EntityProxyDir {
    param([hashtable]$ProxyType, [psobject]$Config)
    $envVal = [System.Environment]::GetEnvironmentVariable($ProxyType.EnvVar)
    $configVal = $null
    if ($Config.general.proxyDirs -and $Config.general.proxyDirs.($ProxyType.ConfigField -replace 'ProxyDir$','')) {
        $configVal = $Config.general.proxyDirs.($ProxyType.ConfigField -replace 'ProxyDir$','')
    }
    # Legacy fallback for agent
    if (-not $configVal -and $ProxyType.Marker -eq 'AGENT.md' -and $Config.general.agentProxyDir) {
        $configVal = $Config.general.agentProxyDir
    }
    return Resolve-ConfigPath -EnvValue $envVal -ConfigValue $configVal -Default $ProxyType.DefaultDir
}

# Helper: Copy entity marker files as proxies for all proxied entity types.
function Copy-EntityProxies {
    param([string]$SkillDest, [string]$SkillName, [hashtable[]]$ProxyTypes, [psobject]$Config)
    foreach ($pt in $ProxyTypes) {
        $markerPath = Join-Path $SkillDest $pt.Marker
        if (Test-Path $markerPath) {
            $proxyDir = Resolve-EntityProxyDir -ProxyType $pt -Config $Config
            if (-not (Test-Path $proxyDir)) {
                New-Item -ItemType Directory -Path $proxyDir -Force | Out-Null
            }
            $proxyPath = Join-Path $proxyDir "$SkillName$($pt.Extension)"
            Copy-Item -Path $markerPath -Destination $proxyPath -Force
            (Get-Item $proxyPath).LastWriteTime = (Get-Item $markerPath).LastWriteTime
            Write-Output "  Entity proxy created: $proxyPath"
        }
    }
}

# Helper: Clean up a failed skill install (dest folder + all entity proxies).
function Remove-FailedSkill {
    param([string]$SkillDest, [string]$SkillName, [hashtable[]]$ProxyTypes, [psobject]$Config)
    if (Test-Path $SkillDest) {
        Remove-Item -Path $SkillDest -Recurse -Force -ErrorAction SilentlyContinue
    }
    foreach ($pt in $ProxyTypes) {
        $proxyDir = Resolve-EntityProxyDir -ProxyType $pt -Config $Config
        $proxyPath = Join-Path $proxyDir "$SkillName$($pt.Extension)"
        if (Test-Path $proxyPath) {
            Remove-Item -Path $proxyPath -Force -ErrorAction SilentlyContinue
        }
    }
}

# Helper: Extract an archive into a known destination folder via temp directory.
# Transactional: on failure, cleans up both temp and partial destination.
function Expand-ArchiveToDest {
    param([string]$Archive, [string]$Destination)
    $tempExtract = Join-Path ([System.IO.Path]::GetTempPath()) "skills-hub-env-$([guid]::NewGuid().ToString('N'))"
    try {
        New-Item -ItemType Directory -Path $tempExtract -Force | Out-Null
        Expand-Archive -Path $Archive -DestinationPath $tempExtract -Force
        $extracted = Get-ChildItem -Path $tempExtract -Directory | Select-Object -First 1
        if (-not $extracted) {
            throw "Archive '$Archive' contained no top-level directory"
        }
        if (Test-Path $Destination) {
            Remove-Item -Path $Destination -Recurse -Force
        }
        $destParent = Split-Path -Parent $Destination
        if ($destParent -and -not (Test-Path $destParent)) {
            New-Item -ItemType Directory -Path $destParent -Force | Out-Null
        }
        Move-Item -Path $extracted.FullName -Destination $Destination -Force
    }
    catch {
        if (Test-Path $Destination) {
            Remove-Item -Path $Destination -Recurse -Force -ErrorAction SilentlyContinue
        }
        throw
    }
    finally {
        if (Test-Path $tempExtract) {
            Remove-Item -Path $tempExtract -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
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

function Test-IsHttpUrl {
    param([string]$Value)
    return $Value -match '^https?://'
}

function Test-IsGitHubUrl {
    param([string]$Value)
    if (-not $Value) { return $false }
    return $Value -match '^(https?://)?(github\.com|raw\.githubusercontent\.com)/'
}

# Cache for GitHub token so we only call GCM once per script run
$script:GitHubToken = $null
$script:GitHubTokenResolved = $false

# Single-slot archive cache (no normalization): keep at most one downloaded temp archive at a time.
$script:ArchiveSlotBase = Join-Path ([System.IO.Path]::GetTempPath()) "skills-hub-archive-current"
$script:CurrentArchiveKey = $null
$script:CurrentTempArchivePath = $null

function Clear-ArchiveSlot {
    param([switch]$IncludeStale)

    if ($script:CurrentTempArchivePath -and (Test-Path $script:CurrentTempArchivePath)) {
        Remove-Item -Path $script:CurrentTempArchivePath -Force -ErrorAction SilentlyContinue
    }

    if ($IncludeStale) {
        $tempRoot = [System.IO.Path]::GetTempPath()
        Get-ChildItem -Path $tempRoot -Filter "skills-hub-archive-current*" -File -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }

    $script:CurrentArchiveKey = $null
    $script:CurrentTempArchivePath = $null
}

function Get-GitHubToken {
    if ($script:GitHubTokenResolved) {
        return $script:GitHubToken
    }
    $script:GitHubTokenResolved = $true

    # Prefer token injected by the VS Code extension
    if ($env:GITHUB_TOKEN) {
        $script:GitHubToken = $env:GITHUB_TOKEN
        Write-Host "  [auth] Using injected GitHub token"
        return $script:GitHubToken
    }

    try {
        $input = "protocol=https`nhost=github.com`n`n"
        $result = $input | git credential fill 2>$null
        if ($LASTEXITCODE -eq 0 -and $result) {
            foreach ($line in $result -split "`n") {
                if ($line -match '^password=(.+)$') {
                    $script:GitHubToken = $Matches[1].Trim()
                    Write-Host "  [auth] Using GCM credential"
                    return $script:GitHubToken
                }
            }
        }
    } catch {
        # GCM not available — continue without auth
    }
    Write-Host "  [auth] No GitHub token available"
    return $null
}

function Convert-ToGitHubRawUrl {
    param([string]$Url)

    if (-not $Url) { return $Url }

    $normalized = $Url.Trim()
    if ($normalized -match '^github\.com/') {
        $normalized = "https://$normalized"
    }

    if ($normalized -match '^https?://raw\.githubusercontent\.com/') {
        return $normalized
    }

    if ($normalized -match '^https?://github\.com/(?<owner>[^/]+)/(?<repo>[^/]+)/blob/(?<branch>[^/]+)/(?<filePath>.+)$') {
        $owner = $Matches['owner']
        $repo = $Matches['repo']
        $branch = $Matches['branch']
        $filePath = $Matches['filePath']
        return "https://raw.githubusercontent.com/$owner/$repo/$branch/$filePath"
    }

    if ($normalized -match '^https?://github\.com/(?<owner>[^/]+)/(?<repo>[^/]+)/raw/(?<branch>[^/]+)/(?<filePath>.+)$') {
        $owner = $Matches['owner']
        $repo = $Matches['repo']
        $branch = $Matches['branch']
        $filePath = $Matches['filePath']
        return "https://raw.githubusercontent.com/$owner/$repo/$branch/$filePath"
    }

    if ($normalized -match '^https?://github\.com/(?<owner>[^/]+)/(?<repo>[^/]+)/tree/(?<branch>[^/]+)/(?<filePath>.+)$') {
        $owner = $Matches['owner']
        $repo = $Matches['repo']
        $branch = $Matches['branch']
        $filePath = $Matches['filePath']
        return "https://raw.githubusercontent.com/$owner/$repo/$branch/$filePath"
    }

    if ($normalized -match '^https?://github\.com/(?<owner>[^/]+)/(?<repo>[^/]+)/(?<filePath>.+)$') {
        $owner = $Matches['owner']
        $repo = $Matches['repo']
        $filePath = $Matches['filePath']
        return "https://raw.githubusercontent.com/$owner/$repo/main/$filePath"
    }

    return $null
}

function Resolve-ArchivePath {
    param(
        [string]$ArchivePath,
        [string]$Proxy
    )

    if (-not $ArchivePath) {
        return @{ Path = $null; IsTemp = $false }
    }

    if (-not (Test-IsHttpUrl $ArchivePath) -and -not (Test-IsGitHubUrl $ArchivePath)) {
        return @{ Path = $ArchivePath; IsTemp = $false }
    }

    if (-not (Test-IsGitHubUrl $ArchivePath)) {
        throw "Only GitHub archive URLs are supported. Received: $ArchivePath"
    }

    $downloadUrl = Convert-ToGitHubRawUrl -Url $ArchivePath
    if (-not $downloadUrl -or -not ($downloadUrl -match '^https?://raw\.githubusercontent\.com/[^/]+/[^/]+/[^/]+/.+')) {
        throw "Invalid GitHub archive path. Expected a file path inside a repository: $ArchivePath"
    }

    $lower = $ArchivePath.ToLowerInvariant()
    $extension = '.bin'
    if ($lower -match '\.tar\.gz($|\?)') {
        $extension = '.tar.gz'
    } elseif ($lower -match '\.zip($|\?)') {
        $extension = '.zip'
    }

    $slotFile = "${script:ArchiveSlotBase}$extension"
    if ($script:CurrentArchiveKey -eq $ArchivePath -and $script:CurrentTempArchivePath -eq $slotFile -and (Test-Path $slotFile)) {
        Write-Output "  Reusing downloaded archive slot for: $ArchivePath"
        return @{ Path = $slotFile; IsTemp = $true }
    }

    if ($script:CurrentTempArchivePath -and (Test-Path $script:CurrentTempArchivePath)) {
        Write-Output "  Replacing archive slot with: $ArchivePath"
        Remove-Item -Path $script:CurrentTempArchivePath -Force -ErrorAction SilentlyContinue
    }

    if (Test-Path $slotFile) {
        Remove-Item -Path $slotFile -Force -ErrorAction SilentlyContinue
    }

    $tempPart = "${slotFile}.part"
    if (Test-Path $tempPart) {
        Remove-Item -Path $tempPart -Force -ErrorAction SilentlyContinue
    }

    $ghToken = Get-GitHubToken

    $curlArgs = @('--fail', '--location', '--progress-bar', '--connect-timeout', '10', '--max-time', '300')
    if ($ghToken) {
        $curlArgs += @('-H', "Authorization: Bearer $ghToken")
    }
    if ($Proxy) {
        $curlArgs += @('--proxy', $Proxy)
    }
    $curlArgs += @('-o', $tempPart, $downloadUrl)

    try {
        Write-Output "  Downloading archive to slot: $ArchivePath"
        & curl.exe @curlArgs
        if ($LASTEXITCODE -ne 0) {
            throw "curl.exe failed with exit code $LASTEXITCODE"
        }
        Move-Item -Path $tempPart -Destination $slotFile -Force
        $script:CurrentArchiveKey = $ArchivePath
        $script:CurrentTempArchivePath = $slotFile
        return @{ Path = $slotFile; IsTemp = $true }
    } catch {
        if (Test-Path $tempPart) {
            Remove-Item -Path $tempPart -Force -ErrorAction SilentlyContinue
        }
        $script:CurrentArchiveKey = $null
        $script:CurrentTempArchivePath = $null
        throw
    }
}

# Clean up any stale single-slot temp archive left by interrupted prior runs.
Clear-ArchiveSlot -IncludeStale

try {

# Determine config file path
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrEmpty($ConfigFile)) {
    $ConfigFile = Join-Path $scriptDir "config.json"
}

if (-not (Test-Path $ConfigFile)) {
    Write-Error "Configuration file not found at $ConfigFile"
    exit 1
}

# Load config
$config = Get-Content $ConfigFile -Raw | ConvertFrom-Json

$destRoot = Resolve-ConfigPath -EnvValue $env:SKILLS_HUB_DESTROOT -ConfigValue $config.general.destRoot -Default '.claude/skills'
if ($env:SKILLS_HUB_PYTHON_ENV_HOME) {
    Write-Output "Using SKILLS_HUB_PYTHON_ENV_HOME=$($env:SKILLS_HUB_PYTHON_ENV_HOME) for Python environment paths"
}
if ([string]::IsNullOrEmpty($SrcRoot)) {
    $srcRoot = $config.srcRoot.windows
} else {
    $srcRoot = $SrcRoot
    Write-Output "Using override source root: $srcRoot"
}

# Read active environment name and get type from within the environment config
$envName = if ($config.activeEnvironment) { $config.activeEnvironment } else { "miniPython" }
$envConfig = $null
if ($config.environments -and $config.environments.$envName) {
    $envConfig = $config.environments.$envName
}
$envType = if ($envConfig -and $envConfig.type) { $envConfig.type } else { "sourced" }

# Use envConfig from above for reading environment-specific settings

$miniPythonArchive = if ($envConfig -and $envConfig.archiveFile) { $envConfig.archiveFile.windows } else { $null }
$miniPythonDest = if ($envConfig -and $envConfig.dest) { Expand-EnvTilde $envConfig.dest.windows } else { $null }
$httpProxy = $config.proxy.http
$httpsProxy = $config.proxy.https

# Helper: Merge two PSObjects (second overrides first)
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

# Helper: Compare semver versions (returns $true if v1 > v2)
# Missing version treated as "0.0.0"
function Test-VersionGreater {
    param(
        [string]$Version1,
        [string]$Version2
    )
    
    if ([string]::IsNullOrEmpty($Version1)) { $Version1 = "0.0.0" }
    if ([string]::IsNullOrEmpty($Version2)) { $Version2 = "0.0.0" }
    
    $v1Parts = $Version1.Split('.') | ForEach-Object { [int]($_ -replace '[^0-9].*', '') }
    $v2Parts = $Version2.Split('.') | ForEach-Object { [int]($_ -replace '[^0-9].*', '') }
    
    # Pad to 3 parts
    while ($v1Parts.Count -lt 3) { $v1Parts += 0 }
    while ($v2Parts.Count -lt 3) { $v2Parts += 0 }
    
    for ($i = 0; $i -lt 3; $i++) {
        if ($v1Parts[$i] -gt $v2Parts[$i]) { return $true }
        if ($v1Parts[$i] -lt $v2Parts[$i]) { return $false }
    }
    return $false  # Equal, not greater
}

# Handle PrepareEnv
if ($PrepareEnv) {
    if ((Test-Path $miniPythonDest) -and (Get-ChildItem $miniPythonDest | Select-Object -First 1)) {
        Write-Output "$miniPythonDest already exists and is not empty -- skipping."
    } else {
        if (Test-Path $miniPythonDest) {
            Write-Output "$miniPythonDest exists but is empty -- will re-extract."
        } else {
            Write-Output "$miniPythonDest does not exist -- will extract."
        }
        $resolvedArchive = $null
            $archiveInfo = Resolve-ArchivePath -ArchivePath $miniPythonArchive -Proxy $httpsProxy
            $resolvedArchive = $archiveInfo.Path

            if (-not $resolvedArchive -or -not (Test-Path $resolvedArchive)) {
                Write-Error "Archive not found at $miniPythonArchive"
                exit 1
            }
            Write-Output "Preparing MiniPython from $miniPythonArchive..."
            Expand-ArchiveToDest -Archive $resolvedArchive -Destination $miniPythonDest
            Write-Output "$miniPythonDest has been prepared."
    }
    return
}

# Identify Skills
$targetSkills = @()

# Helper: Check if skills-hub is explicitly requested
$skillsHubExplicitlyRequested = ($Skills | Where-Object { "skills-hub" -like "*$_*" }).Count -gt 0

if ($Update) {
    Write-Output "Checking for installed skills in $destRoot..."
    if (Test-Path $destRoot) {
        # Exclude skills-hub unless explicitly requested
        $installed = Get-ChildItem -Path $destRoot -Directory | Where-Object { 
            $_.Name -notlike "_*" -and ($_.Name -ne "skills-hub" -or $skillsHubExplicitlyRequested)
        }
        
        # If specific skills are requested, filter to only those
        if ($Skills.Count -gt 0) {
            $installed = $installed | Where-Object {
                $skillName = $_.Name
                if ($Exact) {
                    ($Skills | Where-Object { $skillName -eq $_ }).Count -gt 0
                } else {
                    ($Skills | Where-Object { $skillName -like "*$_*" }).Count -gt 0
                }
            }
        }
        
        foreach ($skill in $installed) {
            $srcPath = Join-Path $srcRoot $skill.Name
            if (Test-Path $srcPath) {
                $targetSkills += Get-Item $srcPath
                Write-Output " - Found: $($skill.Name)"
            }
        }
    }
} elseif ($Skills.Count -eq 0) {
    if (Test-Path $srcRoot) {
        # No filter provided: exclude skills-hub
        $targetSkills = Get-ChildItem -Path $srcRoot -Directory | Where-Object { $_.Name -notlike "_*" -and $_.Name -ne "skills-hub" }
    }
} else {
    foreach ($pattern in $Skills) {
        # Exclude skills-hub unless explicitly requested
        $filter = if ($Exact) { $pattern } else { "*$pattern*" }
        $matches = Get-ChildItem -Path $srcRoot -Directory -Filter $filter | Where-Object { 
            $_.Name -notlike "_*" -and ($_.Name -ne "skills-hub" -or $skillsHubExplicitlyRequested)
        }
        $targetSkills += $matches
    }
}

if ($targetSkills.Count -eq 0) {
    Write-Output "No skills identified."
    return
}

# List only
if ($ListOnly) {
    Write-Output "`nAvailable skills:"
    foreach ($s in $targetSkills) { Write-Output " - $($s.Name)" }
    return
}

# Confirm
Write-Output "`nSkills to download/update:"
foreach ($s in $targetSkills) { Write-Output " - $($s.Name)" }
Write-Output ""
if (-not $ConfirmAll) {
    $confirm = Read-Host "Proceed? (y/n)"
    if ($confirm -notmatch "^y$") {
        Write-Output "Cancelled."
        return
    }
}

# Download/Update Skills
$successCount = 0
$failedInstalls = @()
$createdEnvs = @{}
foreach ($skill in $targetSkills) {
    $skillName = $skill.Name
    $dest = Join-Path $destRoot $skillName
    
    # Version check for update mode only (skip if force is enabled)
    if ($Update -and (Test-Path $dest)) {
        if ($Force) {
            Write-Output "Force updating: $skillName..."
        } else {
            $installedVersion = $null
            $sourceVersion = $null
            
            # Get installed version (missing = treat as lower)
            $installedConfigPath = Join-Path $dest "config.json"
            if (Test-Path $installedConfigPath) {
                try {
                    $installedConfig = Get-Content $installedConfigPath -Raw | ConvertFrom-Json
                    $installedVersion = $installedConfig.metadata.version
                } catch { }
            }
            
            # Get source version
            $sourceConfigPath = Join-Path $skill.FullName "config.json"
            if (Test-Path $sourceConfigPath) {
                try {
                    $sourceConfig = Get-Content $sourceConfigPath -Raw | ConvertFrom-Json
                    $sourceVersion = $sourceConfig.metadata.version
                } catch { }
            }
            
            # If both versions exist, compare them
            if ($installedVersion -and $sourceVersion) {
                if (-not (Test-VersionGreater $sourceVersion $installedVersion)) {
                    Write-Output "Skipping: $skillName (installed: $installedVersion, source: $sourceVersion)"
                    continue
                }
                Write-Output "Updating: $skillName ($installedVersion -> $sourceVersion)"
            } else {
                # Missing version = treat local as lower, proceed with update
                Write-Output "Updating: $skillName (version missing, forcing update)"
            }
        }
    } else {
        Write-Output "Downloading: $skillName..."
    }
    
    if (Test-Path $dest) { Remove-Item -Path $dest -Recurse -Force }
    
    if (-not (Test-Path $destRoot)) {
        New-Item -ItemType Directory -Path $destRoot -Force | Out-Null
    }
    
    try {

    $robocopyArgs = @($skill.FullName, $dest, "/E", "/R:3", "/W:1", "/NP", "/NFL", "/NDL", "/NJH", "/NJS")
    & robocopy @robocopyArgs | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "File copy failed for skill '$skillName' (robocopy exit code $LASTEXITCODE)"
    }

    # Load skill config and merge with hub config
    $skillConfigPath = Join-Path $dest "config.json"
    $skillConfigData = $null
    $skillHasConfig = Test-Path $skillConfigPath
    if ($skillHasConfig) {
        $skillConfigData = Get-Content $skillConfigPath -Raw | ConvertFrom-Json
    }
    
    # Merge configs: hub as base, skill overrides (deep merge)
    $mergedConfig = Merge-Objects $config $skillConfigData
    
    # Determine active environment:
    # - If skill has config.json with activeEnvironment -> use it
    # - If skill has config.json without activeEnvironment -> default to "none" (no Python needed)
    # - If skill has no config.json -> use hub's activeEnvironment (backward compatible)
    $envName = $null
    $skillHasActiveEnv = $skillHasConfig -and $skillConfigData -and $skillConfigData.PSObject.Properties['activeEnvironment']
    if ($skillHasActiveEnv) {
        $envName = $skillConfigData.activeEnvironment
    } elseif ($skillHasConfig) {
        $envName = "none"  # Skill has config but didn't specify env = no Python needed
    } else {
        $envName = $mergedConfig.activeEnvironment  # No skill config = use hub default
        if (-not $envName) { $envName = "miniPython" }
    }
    
    $envType = "sourced"
    if ($mergedConfig.environments -and $mergedConfig.environments.$envName -and $mergedConfig.environments.$envName.type) {
        $envType = $mergedConfig.environments.$envName.type
    }
    Write-Output "  Environment: $envName (type: $envType)"
    
    # Handle 'none' type - skip environment preparation entirely
    if ($envType -eq "none") {
        Write-Output "  No Python environment required"
        Copy-EntityProxies -SkillDest $dest -SkillName $skillName -ProxyTypes $EntityProxyTypes -Config $config
        Write-Output "  Done: $skillName"
        $successCount++
        continue
    }
    
    # Skip Python environment setup if SKILLS_HUB_SKIP_PYTHON_ENV=1
    if ($env:SKILLS_HUB_SKIP_PYTHON_ENV -eq "1") {
        Write-Output "  [SKIP_PYTHON_ENV] Skipping Python environment setup and pip install for '$skillName'"
    } else {

    # Get environment-specific config from environments.<name>
    $envConfig = $null
    if ($mergedConfig.environments -and $mergedConfig.environments.$envName) {
        $envConfig = $mergedConfig.environments.$envName
    }
    
    $pythonExe = $null
    $reqFile = Join-Path $dest "requirements.txt"
    $hasRequirements = Test-Path $reqFile
    
    if ($envType -eq "venv") {
            # venv mode: use existing venv from environments.<name>
            $venvPath = $null
            $venvPythonExe = $null
            
            if ($envConfig) {
                $venvPath = Expand-EnvTilde $envConfig.path.windows
                $venvPythonExe = Expand-Tilde $envConfig.pythonExecutable.windows
            }
            
            if (-not $venvPath) {
                throw "environments.$envName.path.windows is not configured for skill '$skillName'"
            }
            
            # Resolve venv path (relative to skill dir or absolute)
            if (-not [System.IO.Path]::IsPathRooted($venvPath)) {
                $venvPath = Join-Path $dest $venvPath
            }
            
            $pythonExe = Join-Path $venvPath "Scripts\python.exe"
            Write-Output "  Using venv: $venvPath"
            
            if (-not (Test-Path $pythonExe)) {
                if ($venvPythonExe) {
                    Write-Output "  Create it with: $venvPythonExe -m venv $venvPath"
                }
                throw "venv not found at $venvPath for skill '$skillName'"
            }
        } else {
            # sourced mode (default): use portable Python from environments.<name>
            $skillPythonDest = if ($envConfig -and $envConfig.dest) { Expand-EnvTilde $envConfig.dest.windows } else { $null }
            $skillArchive = if ($envConfig -and $envConfig.archiveFile) { $envConfig.archiveFile.windows } else { $null }
            
            # Prepare sourced environment if needed
            if (-not $skillPythonDest) {
                throw "No dest.windows configured for environment '$envName' (skill '$skillName')"
            } elseif ((Test-Path $skillPythonDest) -and (Get-ChildItem $skillPythonDest | Select-Object -First 1)) {
                Write-Output "  Environment exists at $skillPythonDest"
            } else {
                $resolvedSkillArchive = $null
                    $skillArchiveInfo = Resolve-ArchivePath -ArchivePath $skillArchive -Proxy $httpsProxy
                    $resolvedSkillArchive = $skillArchiveInfo.Path

                    if (-not $resolvedSkillArchive -or -not (Test-Path $resolvedSkillArchive)) {
                        throw "Environment archive not found at '$skillArchive' for skill '$skillName'"
                    } else {
                        if (Test-Path $skillPythonDest) {
                            Write-Output "  Preparing environment at $skillPythonDest (exists but empty)..."
                        } else {
                            Write-Output "  Preparing environment at $skillPythonDest..."
                        }
                        Expand-ArchiveToDest -Archive $resolvedSkillArchive -Destination $skillPythonDest
                        $createdEnvs[$skillPythonDest] = @{ Name = $envName; Type = $envType; Path = $skillPythonDest; Archive = $skillArchive }
                    }
            }
            
            $pythonExe = if ($skillPythonDest) { Join-Path $skillPythonDest "python.exe" } else { $null }
            if (-not $pythonExe -or -not (Test-Path $pythonExe)) {
                throw "Python executable not found at '$pythonExe' for environment '$envName' (skill '$skillName')"
            }
            Write-Output "  Using sourced environment: $skillPythonDest"
        }
        
        # Install dependencies only if requirements.txt exists
        if ($hasRequirements) {
            Write-Output "  Installing dependencies..."
            $env:HTTP_PROXY = $httpProxy
            $env:HTTPS_PROXY = $httpsProxy
            $env:PYTHONNOUSERSITE = "1"
            & $pythonExe -m pip install -r $reqFile --disable-pip-version-check --no-warn-script-location
            if ($LASTEXITCODE -ne 0) {
                throw "pip install failed for skill '$skillName'"
            }
        } else {
            Write-Output "  No requirements.txt found, skipping dependency installation"
        }

    } # end SKILLS_HUB_SKIP_PYTHON_ENV gate

    Copy-EntityProxies -SkillDest $dest -SkillName $skillName -ProxyTypes $EntityProxyTypes -Config $config

    Write-Output "  Done: $skillName"
    $successCount++

    } catch {
        Write-Output "  FAILED: $skillName - $($_.Exception.Message)"
        Remove-FailedSkill -SkillDest $dest -SkillName $skillName -ProxyTypes $EntityProxyTypes -Config $config
        $failedInstalls += @{ Name = $skillName; Reason = $_.Exception.Message }
    }
}

Write-Output "`nSuccessfully installed: $successCount"

if ($failedInstalls.Count -gt 0) {
    Write-Output "`nFailed installs ($($failedInstalls.Count)):"
    foreach ($f in $failedInstalls) {
        Write-Output "  - $($f.Name): $($f.Reason)"
    }
    Write-Output ""
}

if ($createdEnvs.Count -gt 0) {
    Write-Output "Environments created ($($createdEnvs.Count)):"
    foreach ($env in $createdEnvs.Values) {
        Write-Output "  - $($env.Name) ($($env.Type)): $($env.Path)"
        Write-Output "    Archive: $($env.Archive)"
    }
    Write-Output ""
}

if ($failedInstalls.Count -eq 0) {
    Write-Output "Operation completed."
}

} finally {
    Clear-ArchiveSlot
}

