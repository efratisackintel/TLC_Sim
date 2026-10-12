---
name: Jira-WPLS-PA
description: Jira WPLS Program Automation — fetch, search, update, comment, transition, and duplicate issue hierarchies with label/field overrides. Use when the user asks to fetch, search, duplicate, transition, comment on, or update Jira issues for WPLS program work.
---

# Jira WPLS-PA Skill

Unified CLI for Jira WPLS Program Automation.  All operations go through a single entrypoint (`jira_wpls_pa.py`) with subcommands.

## When to use this skill

- User asks to **fetch** a Jira issue by key
- User asks to **search** issues via JQL
- User asks to **add a comment** to an issue
- User asks to **transition** an issue to a new status
- User asks to **update** issue fields from a JSON file
- User asks to **duplicate** an issue hierarchy (parent → children → grandchildren) with label swaps, custom field overrides, and reporter assignment

## Prerequisites

Set these environment variables (or put them in a `.env` file in the skill directory):

| Variable | Description |
|----------|-------------|
| `JIRA_URL` | Base URL of the Jira server |
| `JIRA_PAT_TOKEN` | Personal Access Token for authentication |

## How to Run

**Path Variables:**
- `<SKILL_DIR>` — The directory containing this skill
- `<RUN_SKILL_DIR>` — The skills-hub directory: `<SKILL_DIR>/../skills-hub`

---

### Subcommand 1: fetch — Retrieve a single issue

#### Linux/macOS
```bash
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "jira_wpls_pa.py" "fetch" "<ISSUE_KEY>"
```

#### Windows (PowerShell)
```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" -Entrypoint "jira_wpls_pa.py" -UserArgs "fetch", "<ISSUE_KEY>"
```

| Argument | Required | Description |
|----------|----------|-------------|
| `ISSUE_KEY` | Yes | Jira issue key (e.g. `PLC-978`) |

---

### Subcommand 2: search — Search issues via JQL

#### Linux/macOS
```bash
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "jira_wpls_pa.py" "search" "<JQL>" "--max-results" "50"
```

#### Windows (PowerShell)
```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" -Entrypoint "jira_wpls_pa.py" -UserArgs "search", "<JQL>", "--max-results", "50"
```

| Argument | Required | Description |
|----------|----------|-------------|
| `JQL` | Yes | JQL query string |
| `--max-results` | No | Maximum results (default: 50) |

---

### Subcommand 3: comment — Add a comment

#### Linux/macOS
```bash
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "jira_wpls_pa.py" "comment" "<ISSUE_KEY>" "<COMMENT_TEXT>"
```

#### Windows (PowerShell)
```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" -Entrypoint "jira_wpls_pa.py" -UserArgs "comment", "<ISSUE_KEY>", "<COMMENT_TEXT>"
```

| Argument | Required | Description |
|----------|----------|-------------|
| `ISSUE_KEY` | Yes | Issue key |
| `COMMENT_TEXT` | Yes | Comment body text |

---

### Subcommand 4: transition — Change issue status

#### Linux/macOS
```bash
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "jira_wpls_pa.py" "transition" "<ISSUE_KEY>" "<STATUS>"
```

#### Windows (PowerShell)
```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" -Entrypoint "jira_wpls_pa.py" -UserArgs "transition", "<ISSUE_KEY>", "<STATUS>"
```

| Argument | Required | Description |
|----------|----------|-------------|
| `ISSUE_KEY` | Yes | Issue key |
| `STATUS` | Yes | Target status name (e.g. `In Progress`, `Done`) |

---

### Subcommand 5: update — Update fields from JSON

#### Linux/macOS
```bash
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "jira_wpls_pa.py" "update" "<ISSUE_KEY>" "<JSON_FILE>"
```

#### Windows (PowerShell)
```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" -Entrypoint "jira_wpls_pa.py" -UserArgs "update", "<ISSUE_KEY>", "<JSON_FILE>"
```

| Argument | Required | Description |
|----------|----------|-------------|
| `ISSUE_KEY` | Yes | Issue key |
| `JSON_FILE` | Yes | Path to JSON with field updates |

---

### Subcommand 6: duplicate — Duplicate issue hierarchy

Clones parent issues (found via JQL), their linked children, and grandchildren (subtasks).  Applies label swaps, custom field overrides, and optional reporter assignment.

#### Linux/macOS
```bash
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "jira_wpls_pa.py" \
  "duplicate" "<JQL>" \
  "--new-label" "<LABEL>" \
  "--remove-label" "<OLD_LABEL>" \
  "--program-field" "customfield_23600" "--program-value" '{"value":"2025"}' \
  "--silicon-field" "customfield_10238" "--silicon-value" '[{"value":"Whale Peak 2"}]' \
  "--reporter" "omelnik"
```

#### Windows (PowerShell)
```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" -Entrypoint "jira_wpls_pa.py" -UserArgs "duplicate", "<JQL>", "--new-label", "<LABEL>", "--remove-label", "<OLD_LABEL>", "--program-field", "customfield_23600", "--program-value", '{"value":"2025"}', "--silicon-field", "customfield_10238", "--silicon-value", '[{"value":"Whale Peak 2"}]', "--reporter", "omelnik"
```

| Argument | Required | Description |
|----------|----------|-------------|
| `JQL` | Yes | JQL to find parent issues (e.g. `key in (PLC-978)`) |
| `--new-label` | Yes | Label to add to duplicated issues |
| `--remove-label` | No | Label to remove from source issues |
| `--project` | No | Override target project key |
| `--link-type` | No | Link type name (default: `Inclussion`) |
| `--program-field` | No | Custom field ID for Program |
| `--program-value` | No | Program value as JSON string |
| `--silicon-field` | No | Custom field ID for Silicon |
| `--silicon-value` | No | Silicon value as JSON string |
| `--reporter` | No | Reporter username |
