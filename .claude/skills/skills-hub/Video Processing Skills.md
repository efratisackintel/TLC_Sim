# Video Processing Skills

> **3 skills** for video — convert to Markdown, generate PDF reports, and extract clips.

---

## Skills at a Glance

| Skill | What It Does | Input → Output |
|-------|-------------|----------------|
| **Video2Md-convert** | Converts video + SRT transcript to structured Markdown | `.mp4` + `.srt` → `.md` + images |
| **Video2PDF-convert** | Full pipeline: Whisper transcription + VLM frame analysis → PDF report | `.mp4` → `.pdf` |
| **Video-clip-extractor** | Extracts video clips by timestamp using ffmpeg | `.mp4` + timestamps → clip `.mp4` |

---

## How to Invoke via Natural Language

Just tell GitHub Copilot what you need. It reads each skill's `SKILL.md` and picks the right one automatically.

### Convert Video to Markdown

> "Convert `training.mp4` to Markdown — transcript only, no frames"

> "Convert this video to Markdown with frame extraction every 30 seconds"

> "Batch-convert all videos in `Data/BM_Educational_Videos/` to Markdown"

> "Convert this video to Markdown with frame deduplication"

### Generate Video PDF Report

> "Generate a PDF report from `demo.mp4`"

> "Create a PDF from this Hebrew video with English translation"

> "Generate an audio-only PDF from `lecture.mp4` — skip the visual analysis"

> "Create a PDF report using the existing `transcript.srt`"

### Extract Video Clips

> "Extract a clip from `video.mp4` between 1:30 and 2:45"

> "Cut a 30-second clip starting at 5:00"

> "Extract multiple segments: 1:00–2:00 and 5:30–6:15"

> "Extract clips from this JSON batch file"

> "Re-encode the clip for frame-accurate cuts"

---

## 1. Video2Md-convert — Video to Markdown

Converts video files with SRT transcripts to structured Markdown documents with optional frame extraction.

### Modes

| Mode | Flag | Speed | Description |
|------|------|-------|-------------|
| SRT-only | `--srt-only` | Fast | Transcript only, no frames |
| Standard | *(default)* | Medium | Frames + transcript |
| Dedupe | `--dedupe` | Slower | Frames + transcript, skip similar frames |
| Batch | `--batch` | Varies | Process entire folder tree |

### Output Structure

Each video produces a `<video_name>_md/` directory:
- `<video_name>.md` — Structured Markdown with timestamps, transcript, and embedded frames
- `images/` — Extracted frame images (if not using `--srt-only`)

### CLI

```bash
# SRT-only (fast)
python video2md.py "meeting.mp4" --srt-only

# With frame extraction
python video2md.py "training.mp4" --capture-frequency 30

# Batch process folder
python video2md.py --batch "Data/BM_Educational_Videos/" --srt-only

# With frame deduplication (requires ChAI API)
python video2md.py "video.mp4" --dedupe
```

### Dependencies

Python 3.10+, `ffmpeg` (for frames), `CHAI_SDK_CLIENT_SECRET` (for `--dedupe` only)

---

## 2. Video2PDF-convert — Video to PDF Report

Full pipeline: Whisper audio transcription + Phi-3.5 Vision VLM frame analysis → timeline PDF.

### Pipeline

```
Input Video
    ├── Audio Transcription (Whisper dual-engine) → audio.srt
    ├── Frame Extraction (ffmpeg) → frames/
    ├── Visual Analysis (Phi-3.5 VLM) → descriptions
    └── PDF Generation (fpdf2) → report.pdf
```

### CLI

```bash
# Full pipeline (English)
python generate_video_pdf.py --input video.mp4

# Hebrew → English PDF
python generate_video_pdf.py --input video.mp4 --language he --translate

# Audio-only PDF (skip VLM)
python generate_video_pdf.py --input video.mp4 --skip-vlm

# Use existing SRT
python generate_video_pdf.py --input video.mp4 --srt existing.srt
```

### Key Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--input` | (required) | Input video file |
| `--output` | auto | Output PDF path |
| `--language` | `en` | Audio language code |
| `--translate` | off | Translate to English |
| `--frame-interval` | `10` | Seconds between frames |
| `--vlm-device` | `GPU` | VLM device (GPU/CPU/NPU) |
| `--skip-vlm` | off | Audio-only PDF |
| `--srt` | — | Use existing SRT file |

### Dependencies

`fpdf2`, `ffmpeg`, Phi-3.5 VLM model, Whisper model, `CHAI_SDK_CLIENT_SECRET` (for SRT fusion)

---

## 3. Video-clip-extractor — Extract Video Clips

Extract video clips by timestamp using ffmpeg. Fast stream-copy or frame-accurate re-encoding.

### Modes

| Mode | Flag | Description |
|------|------|-------------|
| Single clip | `--start` + `--end` or `--duration` | Extract one segment |
| Multi-segment | `--segments "s1-e1,s2-e2"` | Multiple ranges in one command |
| Batch JSON | `--batch file.json` | Segments defined in JSON file |

### CLI

```bash
# Single clip
python video_clip_extractor.py --input video.mp4 --start 00:01:30 --end 00:02:45

# Duration-based
python video_clip_extractor.py --input video.mp4 --start 00:05:00 --duration 30

# Multiple segments
python video_clip_extractor.py --input video.mp4 --segments "00:01:00-00:02:00,00:05:30-00:06:15"

# Batch from JSON
python video_clip_extractor.py --input video.mp4 --batch segments.json

# Frame-accurate (re-encode)
python video_clip_extractor.py --input video.mp4 --start 00:01:30 --end 00:02:45 --reencode
```

### Batch JSON Format

```json
[
  {"start": "00:01:00", "end": "00:02:00", "label": "intro"},
  {"start": "00:05:30", "end": "00:06:15", "label": "demo"}
]
```

### Dependencies

`ffmpeg` on PATH (no Python package dependencies)

---

## Skill Integration Map

```
                    ┌──────────────────────┐
                    │    Input Video (.mp4) │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌───────────────┐
    │ Video2Md     │  │ Video2PDF    │  │ Video-clip    │
    │ (→ Markdown) │  │ (→ PDF)      │  │ -extractor    │
    └──────────────┘  └──────────────┘  └───────────────┘
```

### Example Workflows

| Workflow | Skills Chain |
|----------|-------------|
| **Meeting notes** | Audio2Md → Video2Md (SRT-only) |
| **Training documentation** | Audio2Md → Video2Md (with frames) → Video-clip-extractor |
| **Video PDF report** | Video2PDF (end-to-end) |
| **Clip highlights** | Video-clip-extractor (timestamps from transcript) |

---

## Environment & Authentication

### Python Environments

| Skill | Environment Path |
|-------|-----------------|
| Video2Md-convert | `c:\video2mdPython` / `~/video2mdPython` |
| Video2PDF-convert | `c:\video2pdfPython` / `~/video2pdfPython` |
| Video-clip-extractor | (stdlib only — no venv needed) |

### Authentication

`CHAI_SDK_CLIENT_SECRET` is required only for:
- Video2Md-convert `--dedupe` mode
- Video2PDF-convert SRT fusion

All other operations work fully offline.

### System Dependencies

- **ffmpeg** — Required by all three skills (frames, PDF, clip extraction)
- **Phi-3.5 VLM model** — Required by Video2PDF for frame analysis
- **Whisper model** — Required by Video2PDF for transcription (Audio2Md handles transcription for Video2Md)
