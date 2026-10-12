# WCS AI CoE — Skills Hub for GitHub Copilot & AI Agents

> **SharePoint Home:** [CCG WCS AI CoE](https://intel.sharepoint.com/sites/ccgwcsaicoe)
>
> **GitHub Repository:** [intel-sandbox/wcs-skills-hub](https://github.com/intel-sandbox/wcs-skills-hub)

The **Skills Hub** is a curated library of plug-and-play skills that extend GitHub Copilot (GHCP) and other AI agents with Intel-specific capabilities. Skills run cross-platform (Windows / Linux / macOS) via shared runner scripts and can be installed into any workspace with a single command.

---

## Quick Start

```powershell
# Install skills into your workspace (PowerShell)
& .claude\skills\skills-hub\skills_hub.ps1 -Skills ChAI-Assistant, Doc2Md-convert, Pdf2Md-convert

# Or install ALL skills
& .claude\skills\skills-hub\skills_hub.ps1 -All
```

Once installed, simply tell Copilot what you need — it reads each skill's `SKILL.md` and invokes the right one automatically.

---

## SharePoint Walkthroughs

Detailed SharePoint pages with screenshots, video walkthroughs, and step-by-step guides:

| Skill Area | SharePoint Page |
|-----------|-----------------|
| **ChAI Skills** (Assistant, Vector Store, Jira SQL) | [ChAI Skills Overview](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/ChAI-Skills%281%29.aspx) |
| **JIRA Content Access** (SQL queries, document retrieval) | [JIRA Up-to-date Content Access via Skills SDK](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/JIRA-Up-to-date-Content-Access-via-Skills-SDK-%28WalkThru%29.aspx?ga=1) |
| **Doc2Md** (Word → Markdown + Mermaid) | [Doc2Md Skills](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/Doc2Md-Skills.aspx) |
| **Visio2Md** (Visio → Mermaid diagrams) | [Visio 2 Md](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/Visio-2-Md.aspx) |
| **Pdf2Md** (PDF → Markdown + watermark removal) | [PDF2MD](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/PDF2MD.aspx) |
| **Spec2JIRA** (Spec generation → JIRA upload) | [Spec 2 JIRA](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/Spec-2-JIRA.aspx) |

---

## Skills Catalog

### 1. WCS Knowledge & AI Assistants

Skills that give the AI agent direct access to Intel's knowledge bases, AI assistants, and JIRA data.

| Skill | v | What It Does | How the Agent Uses It |
|-------|---|-------------|----------------------|
| **[ChAI-Assistant](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/ChAI-Skills%281%29.aspx)** | 1.0.0 | Queries Intel AI Assistants for natural-language answers about WiFi, Bluetooth, TOP, and ICA products | Agent asks a question → gets an expert answer. Supports 8 domain assistants (`WiFi_QnA`, `BT_QnA`, `TOP_QnA`, etc.) and custom marketplace bots. Multi-turn conversations via `chat_id`. |
| **[ChAI-Vector-Store](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/ChAI-Skills%281%29.aspx)** | 1.0.0 | Searches Intel document embeddings and returns relevant context chunks with metadata | Agent retrieves source evidence for RAG workflows. Filterable by domain, doc type, status, sub-category (WREQ, HAS, SAS, DCR). Returns up to N chunks with doc URLs. |
| **[ChAI-Jira-SQL](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/JIRA-Up-to-date-Content-Access-via-Skills-SDK-%28WalkThru%29.aspx?ga=1)** | 1.0.0 | Executes SQL queries against the JIRA database (PostgreSQL) | Agent looks up WREQs, DCRs, HASBUs by key, filters by assignee/status/platform, searches descriptions. Key normalization built-in (`dcr123` → `DCR-123`). |

**Combined usage guide:** [ChAI Skills Overview (SharePoint)](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/ChAI-Skills%281%29.aspx)

---

### 2. Document Conversion Pipeline

Convert documents from any source format into structured Markdown with extracted images and interactive Mermaid diagrams.

| Skill | v | What It Does | How the Agent Uses It |
|-------|---|-------------|----------------------|
| **[Doc2Md-convert](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/Doc2Md-Skills.aspx)** | 1.1.0 | Converts a single Word document (.docx/.docm) to Markdown with image extraction and Mermaid diagrams | Agent converts one doc at a time. Extracts all images, generates AI descriptions, converts diagrams to Mermaid. Adds TOC on request. |
| **[Doc2Md-batch-convert](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/Doc2Md-Skills.aspx)** | 1.1.1 | Recursively batch-converts an entire directory tree of Word documents | Agent processes folders of docs in parallel using subagent workers. Preserves directory structure. Ideal for large doc sets (e.g., HAS specifications). |
| **[Doc2Md-image2mermaid](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/Doc2Md-Skills.aspx)** | 1.0.6 | Converts diagram images to Mermaid code using AI vision; generates descriptions for non-diagram images | Agent uses ChAI vision to analyze each extracted image. Diagrams → Mermaid code. Photos/logos → text description. |
| **[Doc2Md-refine-mermaid](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/Doc2Md-Skills.aspx)** | 1.0.0 | Iteratively refines Mermaid diagrams against source images until quality > 85% | Agent validates generated Mermaid against the original image, re-generates up to 3 times to improve accuracy. |
| **[Pdf2Md-convert](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/PDF2MD.aspx)** | 1.2.0 | Converts PDF files to Markdown using Docling with hardware acceleration, image extraction, and automatic watermark removal | Agent handles PDFs end-to-end. Auto-detects confidential watermarks and appends legal notices. GPU-accelerated via CUDA/MPS/OpenVINO when available. |
| **[Visio2Md-image2mermaid](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/Visio-2-Md.aspx)** | 1.0.0 | Converts Visio (.vsdx) diagrams to Mermaid code via XML extraction + LLM, or AI vision analysis | Agent parses Visio ZIP/XML to extract shapes and connections, then uses ChAI LLM to produce valid Mermaid. Supports page-selective conversion and batch image processing. |

---

### 3. Video & Audio Processing

Extract knowledge from multimedia — transcribe audio, extract key frames, and produce structured documentation.

| Skill | v | What It Does | How the Agent Uses It |
|-------|---|-------------|----------------------|
| **[Video2Md-convert](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/Doc2Md-Skills.aspx)** | 1.0.0 | Converts video files to Markdown by extracting key frames, transcribing audio, and structuring notes | Agent produces readable meeting/training notes. SRT-only mode for speed, or full frame extraction with LLM-powered deduplication. |
| **[Video2PDF-convert](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/Doc2Md-Skills.aspx)** | 1.0.0 | Converts videos into PDF reports combining Whisper transcription with Phi-3.5 Vision VLM frame analysis | Agent generates comprehensive PDF reports. Dual-engine Whisper (OpenVINO / native). Supports Hebrew, translation, and standalone SRT fusion. |
| **[Audio2Md-convert](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/Doc2Md-Skills.aspx)** | 1.0.0 | Dual-engine speech-to-text transcription using Whisper (OpenVINO GenAI + native) | Agent transcribes audio files. OpenVINO engine for fast English; native Whisper for Hebrew and multilingual. Outputs SRT, plain text, or JSON. |
| **[Video-clip-extractor](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/Doc2Md-Skills.aspx)** | 1.0.0 | Extracts video clips by timestamp using ffmpeg | Agent cuts clips from longer recordings. Supports single/multiple segments, batch JSON input, frame-accurate re-encoding. |

---

### 4. Architecture & Specification Generation

Automate the creation of specification documents with JIRA traceability and standards compliance.

| Skill | v | What It Does | How the Agent Uses It |
|-------|---|-------------|----------------------|
| *(Retired — replaced by Spec-create)* | — | — | — |

---

### 5. JIRA & Data Access

Direct programmatic access to Intel's JIRA, SharePoint, and Confluence systems.

| Skill | v | What It Does | How the Agent Uses It |
|-------|---|-------------|----------------------|
| **[Jira-Skills](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/JIRA-Up-to-date-Content-Access-via-Skills-SDK-%28WalkThru%29.aspx?ga=1)** | 1.0.0 | Downloads, searches, and updates JIRA issues by ID, folder path, or natural language query | Agent reads/writes JIRA issues directly. Search by key, filter by folder, or natural language. |
| **[Access-SharePoint](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/ChAI-Skills%281%29.aspx)** | 1.0.0 | Access Intel SharePoint sites — list files, search documents, download and read content | Agent browses SharePoint libraries, searches by keyword, downloads files for processing. |
| **[Access-Wiki](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/ChAI-Skills%281%29.aspx)** | 1.2.0 | Access Intel Confluence wiki — read pages, search content, list spaces and pages | Agent reads Confluence pages, searches across spaces, retrieves page content for context. |

---

### 6. Design Workflow (Archflow)

End-to-end design verification workflow from DCR download through test gap analysis.

| Skill | v | What It Does | How the Agent Uses It |
|-------|---|-------------|----------------------|
| **[Archflow-Download-DCR](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/Spec-2-JIRA.aspx)** | 1.0.0 | Downloads a JIRA DCR issue and its linked WREQ requirements as Markdown files | Agent pulls a DCR and all its linked WREQs into local Markdown for analysis. |
| **[Archflow-Gen-Gap-Tests](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/Spec-2-JIRA.aspx)** | 1.0.0 | Analyzes a downloaded DCR and its WREQs to identify test coverage gaps and generate new tests | Agent reviews requirements vs. existing tests, identifies gaps, and auto-generates missing test cases. |

---

### 7. Framework & Demos

The hub infrastructure and reference implementations for building new skills.

| Skill | v | What It Does |
|-------|---|-------------|
| **skills-hub** | 1.0.0 | Hub manager — downloads, updates, lists, and prepares Python environments for all skills |
| **Demo-echo-skill** | 1.0.0 | Reference implementation of a non-Python (prompt-only) skill. Echoes prompts with decorative formatting. |
| **Demo-hash-skill** | 1.0.0 | Reference implementation of a Python skill. Computes cryptographic hashes. |

---

## How Skills Boost the AI Agent

Skills transform a general-purpose AI agent into an Intel domain expert:

### Without Skills
- Agent can only work with files already in the workspace
- No access to Intel knowledge bases, JIRA, SharePoint, or Confluence
- Cannot convert proprietary formats (Word, PDF, Visio, video)
- Cannot generate specs or requirements with traceability

### With Skills
| Capability | Skills Used |
|-----------|-------------|
| **Answer Intel product questions** with sourced evidence | ChAI-Assistant + ChAI-Vector-Store |
| **Look up any JIRA item** (WREQ, DCR, HASBU) in real time | ChAI-Jira-SQL + Jira-Skills |
| **Convert entire doc libraries** to searchable Markdown | Doc2Md-batch-convert + Doc2Md-image2mermaid |
| **Convert PDFs** with watermark handling | Pdf2Md-convert |
| **Convert Visio diagrams** to interactive Mermaid | Visio2Md-image2mermaid + Doc2Md-refine-mermaid |
| **Transcribe meetings** into structured notes | Video2Md-convert + Audio2Md-convert |
| **Generate lean spec documents** from feature ideas | Spec-create |
| **Audit test coverage** against requirements | Archflow-Download-DCR + Archflow-Gen-Gap-Tests |
| **Access SharePoint & Confluence** directly | Access-SharePoint + Access-Wiki |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     GitHub Copilot / AI Agent                   │
│                        (reads SKILL.md)                         │
└───────────────┬─────────────────────────────────┬───────────────┘
                │                                 │
    ┌───────────▼───────────┐         ┌───────────▼───────────┐
    │   run-skill.ps1 (Win) │         │  run-skill.sh (Linux) │
    │   - merges config     │         │  - merges config      │
    │   - activates Python  │         │  - activates Python   │
    │   - runs entrypoint   │         │  - runs entrypoint    │
    └───────────┬───────────┘         └───────────┬───────────┘
                │                                 │
    ┌───────────▼─────────────────────────────────▼───────────┐
    │                    Skill Python Script                    │
    │            (e.g., ask_chai_tool.py, pdf2md.py)           │
    └───────────┬─────────────────────────────────┬───────────┘
                │                                 │
    ┌───────────▼───────────┐         ┌───────────▼───────────┐
    │     ChAI API          │         │   Local Processing    │
    │  (LLM, embeddings,    │         │  (Docling, ffmpeg,    │
    │   JIRA SQL, vision)   │         │   Whisper, OpenVINO)  │
    └───────────────────────┘         └───────────────────────┘
```

---

## Authentication

Most skills require the **ChAI SDK client secret** for Intel API access:

```powershell
# Set in environment (session)
$env:CHAI_SDK_CLIENT_SECRET = "your-secret-here"

# Or add to .env file in workspace root
# CHAI_SDK_CLIENT_SECRET=your-secret-here
```

Skills that need it: ChAI-Assistant, ChAI-Vector-Store, ChAI-Jira-SQL, Doc2Md-image2mermaid, Doc2Md-refine-mermaid, Visio2Md-image2mermaid, Spec-create.

---

## Further Reading

| Resource | Link |
|----------|------|
| Writing Cross-Platform Skills (full guide) | [ChAI Skills Training Portal](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/ChAI-Skills-Training-Portal.aspx) |
| ChAI Skills Usage Guide (detailed examples) | [ChAI Skills Overview](https://intel.sharepoint.com/sites/ccgwcsaicoe/SitePages/ChAI-Skills%281%29.aspx) |
| Skills Hub GitHub repo | [intel-sandbox/wcs-skills-hub](https://github.com/intel-sandbox/wcs-skills-hub) |
| SharePoint AI CoE site | [CCG WCS AI CoE](https://intel.sharepoint.com/sites/ccgwcsaicoe) |