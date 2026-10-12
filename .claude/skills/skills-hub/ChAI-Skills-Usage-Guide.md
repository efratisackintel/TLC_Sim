# ChAI Skills Usage Guide

A practical guide to the three core **ChAI** (Connectivity Hub AI) skills that provide access to Intel's knowledge bases, AI assistants, and JIRA database.

---

## Table of Contents

1. [Overview — Three Skills, Three Purposes](#overview)
2. [Prerequisites](#prerequisites)
3. [ChAI-Assistant — Ask Intel AI Assistants](#chai-assistant)
4. [ChAI-Vector-Store — Search Intel Knowledge Bases](#chai-vector-store)
5. [ChAI-Jira-SQL — Query the JIRA Database](#chai-jira-sql)
6. [Combining Skills — Real-World Workflows](#combining-skills)
7. [Troubleshooting](#troubleshooting)

---

## Overview

| Skill | What It Does | Best For |
|-------|-------------|----------|
| **ChAI-Assistant** | Sends a question to an Intel AI assistant and gets a natural-language answer | Getting explanations, generating requirements, Q&A |
| **ChAI-Vector-Store** | Searches Intel's document embeddings and returns raw context chunks | Finding source documents, gathering evidence, RAG pipelines |
| **ChAI-Jira-SQL** | Runs SQL queries against the JIRA database and returns structured results | Looking up WREQs, DCRs, HASBUs by key, filtering by status/assignee |

### When to Use Which

```
"What is MLD in WiFi 7?"          → ChAI-Assistant (natural-language answer)
"Find all documents about MLD"     → ChAI-Vector-Store (returns matching chunks)
"Get WREQ-34612 details"           → ChAI-Jira-SQL (structured JIRA data)
```

---

## Prerequisites

### Authentication

All three skills require a **ChAI SDK client secret**. Set it once and all skills pick it up:

```powershell
# Option 1: Environment variable (recommended)
$env:CHAI_SDK_CLIENT_SECRET = "your-secret-here"

# Option 2: .env file in the workspace root
# Create a .env file containing:
#   CHAI_SDK_CLIENT_SECRET=your-secret-here
```

### Path Variables

All examples below use these path variables:

| Variable | Meaning |
|----------|---------|
| `<SKILL_DIR>` | The directory containing the specific skill |
| `<RUN_SKILL_DIR>` | The `skills-hub` directory: `<SKILL_DIR>/../skills-hub` |

In a typical workspace, skills live at `.claude/skills/<Skill-Name>/`.

---

## ChAI-Assistant

**Purpose:** Ask a question, get an AI-generated answer from Intel's domain-specific assistants.

### Available Assistants

| Usecase | Domain | Description |
|---------|--------|-------------|
| `QnA` | All | General WiFi, Bluetooth, and TOP products |
| `WiFi_QnA` | WiFi | Intel WiFi products, acronyms, standards |
| `BT_QnA` | Bluetooth | Intel Bluetooth products and specs |
| `TOP_QnA` | TOP | Intel TOP products |
| `ICA_QnA` | ICA | Intel Connectivity Analytics |
| `WiFi_Requirements` | WiFi | Generate WiFi requirements |
| `BT_Requirements` | Bluetooth | Generate Bluetooth requirements |
| `Req_Gen` | All | Generate requirements across products |

### Basic Usage

#### Ask about WiFi

```powershell
# Windows
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" `
    -Entrypoint "ask_chai_tool.py" `
    -UserArgs "--query", "What is MLD in WiFi 7?", "--usecase", "WiFi_QnA"
```

```bash
# Linux/macOS
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "ask_chai_tool.py" \
    --query "What is MLD in WiFi 7?" --usecase "WiFi_QnA"
```

#### Ask about Bluetooth

```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" `
    -Entrypoint "ask_chai_tool.py" `
    -UserArgs "--query", "What is the maximum throughput for BT 5.4?", "--usecase", "BT_QnA"
```

#### Generate Requirements

```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" `
    -Entrypoint "ask_chai_tool.py" `
    -UserArgs "--query", "Generate power management requirements for WiFi 7 AP mode", `
              "--usecase", "WiFi_Requirements"
```

### Advanced: Choose a Model

```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" `
    -Entrypoint "ask_chai_tool.py" `
    -UserArgs "--query", "Explain OFDMA scheduling", `
              "--usecase", "WiFi_QnA", `
              "--model", "Claude Sonnet 4.5"
```

Available models: `GPT 4o Enterprise` (default), `GPT o4-mini`, `GPT 5`, `Claude Sonnet 4.5`, `Claude Haiku 4.5`, `Claude Opus 4.5`

### Advanced: Custom Marketplace Assistant

```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" `
    -Entrypoint "ask_chai_tool.py" `
    -UserArgs "--query", "How do I configure the TX power table?", `
              "--marketplace_name", "MyCustomBot", `
              "--marketplace_owner", "user@intel.com"
```

### Advanced: Multi-Turn Conversation

Use the `chat_id` returned from a previous call to maintain context:

```powershell
# First question
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" `
    -Entrypoint "ask_chai_tool.py" `
    -UserArgs "--query", "What is 802.11be?", "--usecase", "WiFi_QnA"
# Output includes: chat_id: abc-123-def

# Follow-up question (same conversation)
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" `
    -Entrypoint "ask_chai_tool.py" `
    -UserArgs "--query", "How does it differ from 802.11ax?", `
              "--usecase", "WiFi_QnA", `
              "--chat_id", "abc-123-def"
```

### Output Format

```
ChAI Answer: {'response': 'MLD (Multi-Link Device) is a key feature of WiFi 7...', 'chat_id': 'abc-123-def'}
```

---

## ChAI-Vector-Store

**Purpose:** Search Intel's document embeddings to find relevant source documents and knowledge chunks. Returns raw content with metadata — ideal for evidence gathering and RAG (Retrieval-Augmented Generation).

### Available Usecases

Same usecases as ChAI-Assistant:

| Usecase | Knowledge Base |
|---------|----------------|
| `QnA` | All Intel WiFi, BT, TOP documents |
| `WiFi_QnA` | WiFi specs, WREQs, acronyms |
| `BT_QnA` | Bluetooth specs and SIG docs |
| `TOP_QnA` | TOP product docs and WREQs |
| `ICA_QnA` | Connectivity Analytics docs |
| `WiFi_Requirements` / `BT_Requirements` / `Req_Gen` | Requirements knowledge bases |

### Basic Usage

#### Search for WiFi documents

```powershell
# Windows
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" `
    -Entrypoint "vector_store_context_tool.py" `
    -UserArgs "--query", "MLD multi-link operation", "--usecase", "WiFi_QnA"
```

```bash
# Linux/macOS
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "vector_store_context_tool.py" \
    --query "MLD multi-link operation" --usecase "WiFi_QnA"
```

#### Search for Bluetooth specs

```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" `
    -Entrypoint "vector_store_context_tool.py" `
    -UserArgs "--query", "LE Audio codec requirements", "--usecase", "BT_QnA"
```

### Advanced: Retrieve More Chunks

By default, 10 chunks are returned. Increase for broader coverage:

```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" `
    -Entrypoint "vector_store_context_tool.py" `
    -UserArgs "--query", "power management states", `
              "--usecase", "WiFi_QnA", `
              "--chunks", "20"
```

### Advanced: Filter by Document Properties

Use `--filters_dict` to narrow results by domain, document type, status, or category:

```powershell
# Only WiFi specs (not drafts) in PDF format
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" `
    -Entrypoint "vector_store_context_tool.py" `
    -UserArgs "--query", "OFDMA resource allocation", `
              "--usecase", "WiFi_QnA", `
              "--filters_dict", '{"domain": "wifi", "doc_status": "specs", "doc_type": "pdf"}'
```

```powershell
# Only WREQ documents
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" `
    -Entrypoint "vector_store_context_tool.py" `
    -UserArgs "--query", "antenna diversity requirements", `
              "--usecase", "WiFi_Requirements", `
              "--filters_dict", '{"sub_category": "wreq"}'
```

#### Available Filter Fields

| Field | Values | Example |
|-------|--------|---------|
| `domain` | `wifi`, `bt`, `top`, `ica` | `"domain": "wifi"` |
| `doc_category` | `docs`, `code` | `"doc_category": "docs"` |
| `sub_category` | `wreq`, `prd`, `dcr`, `val`, `has`, `sas`, `pytm` | `"sub_category": "has"` |
| `doc_status` | `drafts`, `specs` | `"doc_status": "specs"` |
| `doc_type` | `pdf`, `txt`, `csv`, `xlsx`, `md`, `docx`, `pptx`, `html` | `"doc_type": "docx"` |
| `doc_title` | Any string | `"doc_title": "Power Management"` |

### Output Format

Returns a JSON array of matching chunks:

```json
[
  {
    "content": "Multi-Link Device (MLD) is defined in IEEE 802.11be as...",
    "metadata": {
      "doc_title": "WiFi 7 Architecture HAS",
      "doc_url": "https://jira.devtools.intel.com/browse/WREQ-34612",
      "domain": "wifi"
    }
  },
  {
    "content": "The MLD shall support simultaneous TX/RX across...",
    "metadata": {
      "doc_title": "WiFi MLO Requirements",
      "doc_url": "https://...",
      "domain": "wifi"
    }
  }
]
```

---

## ChAI-Jira-SQL

**Purpose:** Execute SQL queries directly against the Intel JIRA database. Returns structured data for WREQs, DCRs, HASBUs, and other JIRA issue types.

### Key Concepts

- **Table:** `public.jira_documents` (read-only, PostgreSQL)
- **Key prefixes:** `WREQ`, `DCR`, `HASBU`, `WIFIVAL`, `BTVAL`, `SHVAL`
- **Key format:** `PREFIX-NUMBER` (e.g., `WREQ-34612`, `DCR-2603`)
- **All columns are strings** — cast to `::float` or `::integer` for numeric comparisons

### Basic Usage

#### Look up a document by key

```powershell
# Windows — note the backtick-quote escaping for double quotes in SQL
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" `
    -Entrypoint "sql_tool.py" `
    -UserArgs "--query", "SELECT * FROM public.jira_documents WHERE `"`"Key`"`" = 'WREQ-34612';"
```

```bash
# Linux/macOS
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "sql_tool.py" \
    --query "SELECT * FROM public.jira_documents WHERE \"Key\" = 'WREQ-34612';"
```

#### Look up multiple documents

```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" `
    -Entrypoint "sql_tool.py" `
    -UserArgs "--query", "SELECT * FROM public.jira_documents WHERE `"`"Key`"`" IN ('DCR-2603', 'WREQ-34612', 'HASBU-45321');"
```

### Common Queries

#### Find all documents assigned to a person

```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" `
    -Entrypoint "sql_tool.py" `
    -UserArgs "--query", "SELECT `"`"Key`"`", `"`"Summary`"`", `"`"Status`"`" FROM public.jira_documents WHERE `"`"assignee`"`" = 'K, Sukanya';"
```

#### Filter by status

```bash
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "sql_tool.py" \
    --query "SELECT \"Key\", \"Summary\", \"Status\" FROM public.jira_documents WHERE \"Status\" = 'Requested';"
```

#### Search by keyword in Summary

```powershell
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<SKILL_DIR>" `
    -Entrypoint "sql_tool.py" `
    -UserArgs "--query", "SELECT `"`"Key`"`", `"`"Summary`"`" FROM public.jira_documents WHERE `"`"Summary`"`"::text LIKE '%power management%';"
```

#### Find linked documents

```bash
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "sql_tool.py" \
    --query "SELECT * FROM public.jira_documents WHERE string_to_array(\"Links\", ',') @> ARRAY['DCR-2603'];"
```

#### Numeric comparison (with safe casting)

```bash
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "sql_tool.py" \
    --query "SELECT \"Key\", \"Summary\", \"Assumed Frequency\" FROM public.jira_documents WHERE \"Assumed Frequency\" IS NOT NULL AND \"Assumed Frequency\" <> '' AND \"Assumed Frequency\"::float BETWEEN 2.4 AND 2.5;"
```

#### Filter by platform

```bash
bash "<RUN_SKILL_DIR>/run-skill.sh" "<SKILL_DIR>" "sql_tool.py" \
    --query "SELECT \"Key\", \"Summary\", \"Platform/s\" FROM public.jira_documents WHERE \"Platform/s\"::text LIKE '%Lunar Lake%';"
```

### Key Normalization

The skill expects properly formatted keys. Normalize user input before querying:

| User Says | Normalized Key |
|-----------|---------------|
| `dcr123` | `DCR-123` |
| `wreq 34612` | `WREQ-34612` |
| `hasb45321` | `HASBU-45321` |
| `wifival45678` | `WIFIVAL-45678` |

### Important SQL Guidelines

1. **Column names are case-sensitive** — always quote them: `"Key"`, `"Summary"`, `"Status"`
2. **Read-only** — only `SELECT` statements are allowed
3. **All columns are strings** — use `::float` or `::integer` for numeric operations, but filter `NULL` and `''` first
4. **List columns** (Labels, Links, etc.) — use `string_to_array(column, ',')` for array operations
5. **Free text search** — cast to `::text` before using `LIKE`: `"Summary"::text LIKE '%keyword%'`

### Available Columns (Key Subset)

| Column | Type | Description |
|--------|------|-------------|
| `"Key"` | String | JIRA key (e.g., `WREQ-34612`) |
| `"Summary"` / `"summary"` | String | Issue title |
| `"Description"` | String | Full description text |
| `"Status"` / `"status"` | String | Current status |
| `"assignee"` | String | Assigned person |
| `"reporter"` | String | Reporter |
| `"Issue Type"` / `"issuetype"` | String | Issue type |
| `"Platform/s"` | List (String) | Target platforms |
| `"Operating System/s"` | List (String) | Target OSes |
| `"Silicon"` | List (String) | Silicon generations |
| `"Links"` | List (String) | Linked JIRA keys |
| `"Tree Path"` | String | Folder hierarchy |
| `"Assumed Frequency"` | String (castable to Float) | Frequency in GHz |
| `"doc_url"` | String | JIRA URL |

---

## Combining Skills — Real-World Workflows

The three ChAI skills are most powerful when combined. Here are common multi-step workflows.

### Workflow 1: Research a Feature

**Goal:** Understand a WiFi feature and find all related JIRA documents.

```
Step 1: Ask ChAI-Assistant for a high-level explanation
        → "What is TWT (Target Wake Time) in WiFi 6?"

Step 2: Search ChAI-Vector-Store for source documents
        → query: "TWT Target Wake Time power save", usecase: WiFi_QnA

Step 3: Look up specific WREQs found in the vector store results
        → ChAI-Jira-SQL: SELECT * FROM ... WHERE "Key" IN ('WREQ-xxxxx', 'WREQ-yyyyy')
```

**Example commands:**

```powershell
# Step 1: Get explanation
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<CHAI_ASSISTANT_DIR>" `
    -Entrypoint "ask_chai_tool.py" `
    -UserArgs "--query", "What is TWT in WiFi 6 and how does it save power?", `
              "--usecase", "WiFi_QnA"

# Step 2: Find related documents
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<CHAI_VECTOR_DIR>" `
    -Entrypoint "vector_store_context_tool.py" `
    -UserArgs "--query", "TWT Target Wake Time power save mechanism", `
              "--usecase", "WiFi_QnA", "--chunks", "15"

# Step 3: Get JIRA details for discovered WREQs
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<CHAI_JIRA_DIR>" `
    -Entrypoint "sql_tool.py" `
    -UserArgs "--query", "SELECT `"`"Key`"`", `"`"Summary`"`", `"`"Status`"`", `"`"assignee`"`" FROM public.jira_documents WHERE `"`"Summary`"`"::text LIKE '%TWT%' AND `"`"Key`"`" LIKE 'WREQ%';"
```

### Workflow 2: Audit Requirements Coverage

**Goal:** Find all requirements for a component and check their status.

```
Step 1: Vector-Store search for requirements
        → query: "antenna diversity", usecase: WiFi_Requirements, filter: sub_category=wreq

Step 2: Jira-SQL to get status of each WREQ
        → SELECT Key, Summary, Status WHERE Summary LIKE '%antenna diversity%'

Step 3: Assistant to summarize gaps
        → "Given these WREQs and their statuses, what coverage gaps exist?"
```

### Workflow 3: Cross-Domain Investigation

**Goal:** Find all documents linking Bluetooth and WiFi coexistence.

```powershell
# Find context about coexistence in both domains
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<CHAI_VECTOR_DIR>" `
    -Entrypoint "vector_store_context_tool.py" `
    -UserArgs "--query", "WiFi Bluetooth coexistence interference", `
              "--usecase", "QnA", "--chunks", "20"

# Find JIRA items about coexistence
& "<RUN_SKILL_DIR>\run-skill.ps1" -SkillDir "<CHAI_JIRA_DIR>" `
    -Entrypoint "sql_tool.py" `
    -UserArgs "--query", "SELECT `"`"Key`"`", `"`"Summary`"`", `"`"Status`"`" FROM public.jira_documents WHERE `"`"Summary`"`"::text LIKE '%coexist%' ORDER BY `"`"Key`"`";"
```

### Workflow 4: Requirement Generation with Evidence

**Goal:** Generate a new requirement backed by existing documentation.

```
Step 1: Vector-Store — gather context about the feature area
Step 2: Assistant (Req_Gen) — generate requirement with the context as background
Step 3: Jira-SQL — verify no duplicate requirement already exists
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Authentication failed` | Verify `CHAI_SDK_CLIENT_SECRET` is set in env or `.env` file |
| `No results from Vector Store` | Try a broader `--usecase` (`QnA` instead of `WiFi_QnA`) or rephrase the query |
| `SQL syntax error` | Ensure column names are double-quoted and match exactly (case-sensitive) |
| `Timeout / slow response` | ChAI-Assistant can take up to 60s; Vector-Store typically 1–20s; don't assume failure |
| `Empty JIRA results` | Check key format (`PREFIX-NUMBER`), verify the key exists, try `LIKE '%keyword%'` instead of exact match |
| `Numeric cast error in SQL` | Filter `NULL` and `''` before casting: `WHERE col IS NOT NULL AND col <> '' AND col::float > 5` |
| `PowerShell quote escaping` | Use `` `"`" `` (backtick-quote-backtick-quote) to embed double quotes inside SQL strings |

---

## Quick Reference

```
┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│   ChAI-Assistant    │     │  ChAI-Vector-Store   │     │   ChAI-Jira-SQL     │
│                     │     │                      │     │                     │
│  ask_chai_tool.py   │     │ vector_store_        │     │    sql_tool.py      │
│                     │     │   context_tool.py    │     │                     │
│  --query "..."      │     │  --query "..."       │     │  --query "SELECT    │
│  --usecase WiFi_QnA │     │  --usecase WiFi_QnA  │     │    ... FROM public. │
│  [--model "GPT 5"]  │     │  [--chunks 15]       │     │    jira_documents   │
│  [--chat_id "..."]  │     │  [--filters_dict {}] │     │    WHERE ...;"      │
│                     │     │                      │     │                     │
│  → Natural-language │     │  → JSON chunks with  │     │  → Structured JIRA  │
│    answer           │     │    doc metadata      │     │    records (JSON)   │
└─────────────────────┘     └──────────────────────┘     └─────────────────────┘
```
