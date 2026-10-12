# Multi-Modal Processing Skills

> **6 skills** for video, audio, and speech — transcribe, convert, extract, narrate, and podcast.

These skills form a complete multimedia pipeline: ingest video or audio, transcribe it, convert it to documents, extract clips, synthesize speech, and generate podcasts — all invokable via natural language through GitHub Copilot.

---

## Skills at a Glance

| Skill | What It Does | Input → Output |
|-------|-------------|----------------|
| **Video2Md-convert** | Converts video + SRT transcript to structured Markdown | `.mp4` + `.srt` → `.md` + images |
| **Video2PDF-convert** | Full pipeline: Whisper transcription + VLM frame analysis → PDF report | `.mp4` → `.pdf` |
| **Video-clip-extractor** | Extracts video clips by timestamp using ffmpeg | `.mp4` + timestamps → clip `.mp4` |
| **Audio2Md-convert** | Dual-engine Whisper speech-to-text transcription | `.mp4` / `.wav` → `.srt` / `.txt` |
| **Text2Speech** | Tri-engine text-to-speech synthesis (904 neural voices) | `.txt` / `.md` / `.srt` → `.wav` |
| **Text2Podcast** | Agentic two-host podcast generator with quality evaluation | `.txt` / `.md` / `.srt` → `.wav` / `.mp3` + HTML player |

---

## How to Invoke via Natural Language

Just tell GitHub Copilot what you need. It reads each skill's `SKILL.md` and picks the right one automatically.

### Transcribe Audio / Video

> "Transcribe `meeting.mp4` to SRT"

> "Transcribe this video in Hebrew and translate to English"

> "Generate a plain-text transcript from `interview.wav`"

> "Transcribe all videos in the `recordings/` folder"

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

### Text to Speech

> "Convert this text to speech: Hello world, this is a test"

> "Read `document.txt` aloud and save as `speech.wav`"

> "Narrate `notes.md` using the female voice (speaker 140)"

> "Read this document with the male voice (speaker 500)"

> "Use Piper TTS with speaker ID 204 for the narration"

> "Generate speech using OpenVINO with GPU acceleration"

> "Convert these SRT subtitles to narrated audio"

> "List all available TTS voices"

> "Slow down the speech — use a length scale of 1.2"

### Generate a Podcast

> "Generate a podcast from `AI_Wins_Story_Template.md`"

> "Convert this document into a two-host discussion podcast"

> "Create an audio podcast from `notes.txt` with an HTML player"

> "Generate a podcast using speaker 10 for Host A and speaker 204 for Host B"

> "Generate just the podcast script — don't synthesize audio yet"

> "Evaluate the audio quality of `podcast.wav`"

> "Create a podcast with a minimum script quality score of 80"

---

## 1. Audio2Md-convert — Speech-to-Text Transcription

Dual-engine Whisper: OpenVINO GenAI (fast, English) + native OpenAI Whisper (Hebrew & multilingual).

### Engine Selection

| Scenario | Engine | Model | Why |
|----------|--------|-------|-----|
| English / default | OpenVINO | whisper-base | Fastest on Intel HW |
| Hebrew (`--language he`) | Native | medium | Best Hebrew quality |
| Translation (`--translate`) | Native | medium | Only native supports it |
| Explicit (`--engine native`) | Native | medium | User override |

### Model Sizes

| Model | Speed | Accuracy | Size | Best For |
|-------|-------|----------|------|----------|
| `whisper-base` | Fast | Good | ~150 MB | English, quick transcription |
| `whisper-small` | Medium | Better | ~500 MB | General purpose |
| `whisper-medium` | Slow | Best | ~1.5 GB | Hebrew, multilingual |

### CLI

```bash
# English (fast, OpenVINO)
python audio_transcriber.py --input video.mp4 --output transcript.srt

# Hebrew → SRT
python audio_transcriber.py --input video.mp4 --output transcript.srt --language he

# Hebrew → English translation
python audio_transcriber.py --input video.mp4 --output transcript.srt --language he --translate

# Plain text output
python audio_transcriber.py --input audio.wav --format text

# GPU-accelerated
python audio_transcriber.py --input video.mp4 --device GPU --model whisper-medium
```

### Dependencies

`openvino-genai`, `openai-whisper` (optional, for Hebrew), `torch` (optional)

---

## 2. Video2Md-convert — Video to Markdown

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

## 3. Video2PDF-convert — Video to PDF Report

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

## 4. Video-clip-extractor — Extract Video Clips

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

## 5. Text2Speech — Tri-Engine Text-to-Speech

Convert text to speech using three interchangeable TTS engines with automatic quality-based selection.

### Engine Architecture

| Priority | Engine | Sample Rate | Speakers | Condition |
|----------|--------|-------------|----------|-----------|
| 1st | **Piper VITS** | 22,050 Hz | 904 voices | `piper-tts` installed + ONNX model found |
| 2nd | **OpenVINO SpeechT5** | 16,000 Hz | Custom embeddings | `openvino-genai` installed |
| 3rd | **pyttsx3** | System | OS voices | `pyttsx3` installed (fallback) |

### Processing Pipeline

1. **Input Loading** — Direct text, `.txt`, `.md`, or `.srt` file
2. **SRT Parsing** — Strips timestamps, sequence numbers, HTML tags
3. **Markdown Stripping** — Removes headers, bold/italic, code blocks, links
4. **Text Sanitization** — Expands abbreviations, improves intonation
5. **Chunking** — Splits text on sentence boundaries (max 400 chars)
6. **Synthesis** — Engine-specific generation with inter-chunk silence
7. **WAV Output** — Mono 16-bit PCM at engine-native sample rate

### Popular Piper Speaker IDs

| ID | Gender | Notes |
|----|--------|-------|
| 140 | Female | Clear, conversational (Text2Podcast Host A) |
| 500 | Male | Warm, conversational (Text2Podcast Host B) |
| 10 | Female | Alternative female voice |
| 204 | Male | Alternative male voice |

### CLI

```bash
# Auto-select best engine
python text2speech.py --text "Hello, this is a test." --output hello.wav

# From a text file
python text2speech.py --input document.txt --output speech.wav

# From SRT subtitles
python text2speech.py --input subtitles.srt --output narration.wav --srt

# Piper with specific speaker
python text2speech.py --text "Neural voice" -o piper.wav --engine piper --speaker-id 140

# OpenVINO with GPU
python text2speech.py --input long_doc.txt -o speech.wav --engine openvino --device GPU

# pyttsx3 fallback
python text2speech.py --text "Fallback" -o test.wav --engine pyttsx3 --voice Zira --rate 150

# List voices
python text2speech.py --list-voices
```

### Key Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--text` / `-t` | — | Direct text input string |
| `--input` / `-i` | — | Input file (.txt, .md, .srt) |
| `--output` / `-o` | `output.wav` | Output WAV file path |
| `--engine` / `-e` | `auto` | `piper`, `openvino`, `pyttsx3`, `auto` |
| `--speaker-id` | `140` | Piper speaker ID (0–903) |
| `--length-scale` | `1.05` | Speed (>1.0 slower, <1.0 faster) |
| `--device` | `CPU` | OpenVINO device: CPU/GPU/NPU |
| `--voice` | system default | pyttsx3 voice name |
| `--rate` | `175` | pyttsx3 speech rate (WPM) |

### Dependencies

`piper-tts`, `onnxruntime`, `openvino-genai`, `pyttsx3`, `numpy`, `huggingface-hub`

---

## 6. Text2Podcast — Agentic Two-Host Podcast Generator

Generate NotebookLM-style two-host discussion podcasts with a 6-stage agentic pipeline featuring quality evaluation and self-correction.

### Agentic Pipeline

| Stage | Name | What It Does | Quality Gate |
|-------|------|-------------|--------------|
| 1 | Script Generation | Converts source text to two-host dialogue | Retry on failure |
| 2 | Script Evaluation | Scores script on 10 criteria (100 pts) | Fails if < min score (default 70) |
| 3 | TTS Synthesis | Piper multi-speaker VITS rendering | Retry on failure |
| 4 | Audio Evaluation | Analyzes WAV on 8 criteria (100 pts) | Fails if < min score (default 60) |
| 5 | MP3 Export | ffmpeg WAV → MP3 conversion | Optional (`--mp3`) |
| 6 | Player Generation | Self-contained HTML with embedded audio | Optional (`--player`) |

### Quality Rubrics

**Script (100 pts):** Line count (15), speaker balance (20), starts with Host A (5), ends with Host B (5), opening/welcome (10), closing/sign-off (10), no empty lines (5), no too-short lines (10), no too-long lines (10), avg line length (10).

**Audio (100 pts):** File exists (10), valid WAV header (10), duration 30s–1800s (15), peak amplitude > 0.05 (15), RMS level 0.01–0.9 (15), silence ratio < 50% (15), clipping < 1% (10), file size proportional (10).

### TTS Engine

Piper VITS with LibriTTS-R Medium model — 904 speakers, 22,050 Hz, ONNX inference. Default: Host A = speaker 140 (female), Host B = speaker 500 (male).

### CLI

```bash
# Full pipeline: text → podcast with player
python podcast_generator.py --input document.txt --output podcast.wav --mp3 --player

# From a pre-built script
python podcast_generator.py --script script.json --output podcast.wav --mp3

# Script-only (no audio)
python podcast_generator.py --input doc.txt --script-only --output script.json

# Custom speakers and thresholds
python podcast_generator.py --input doc.txt -o podcast.wav \
    --host-a 10 --host-b 500 --min-script-score 80 --min-audio-score 75

# Evaluate existing audio
python podcast_evaluator.py --audio podcast.wav

# Evaluate script + audio as JSON
python podcast_evaluator.py --script script.json --audio podcast.wav --json
```

### Key Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--input` / `-i` | — | Source text file (.txt, .md, .srt) |
| `--script` / `-s` | — | Pre-built script JSON file |
| `--output` / `-o` | `podcast.wav` | Output WAV path |
| `--host-a` | `140` | Speaker ID for Host A (female) |
| `--host-b` | `500` | Speaker ID for Host B (male) |
| `--mp3` | off | Also convert to MP3 |
| `--player` | off | Generate HTML player (implies --mp3) |
| `--min-script-score` | `70` | Minimum script quality (0–100) |
| `--min-audio-score` | `60` | Minimum audio quality (0–100) |
| `--max-retries` | `2` | Max retries per stage |
| `--report` | — | Save pipeline report as JSON |

### Dependencies

`piper-tts`, `onnxruntime`, `ffmpeg` (on PATH), `pytest`

---

## Skill Integration Map

These skills work together in common workflows:

```
                    ┌──────────────────────┐
                    │    Input Video/Audio  │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ Audio2Md     │  │ Video2Md     │  │ Video2PDF    │
    │ (transcribe) │  │ (→ Markdown) │  │ (→ PDF)      │
    └──────┬───────┘  └──────────────┘  └──────────────┘
           │
           │ .srt / .txt / .md
           ▼
    ┌──────────────┐       ┌───────────────┐
    │ Text2Speech  │       │ Video-clip    │
    │ (narrate)    │       │ -extractor    │
    └──────────────┘       └───────────────┘
           │
           ▼
    ┌──────────────┐
    │ Text2Podcast │
    │ (podcast)    │
    └──────────────┘
```

### Example Workflows

| Workflow | Skills Chain |
|----------|-------------|
| **Meeting notes** | Audio2Md → Video2Md (SRT-only) |
| **Training documentation** | Audio2Md → Video2Md (with frames) → Video-clip-extractor |
| **Video PDF report** | Video2PDF (end-to-end) |
| **Document narration** | Text2Speech (read `.md` aloud) |
| **Podcast from notes** | Audio2Md → Text2Podcast |
| **Clip highlights** | Video-clip-extractor (timestamps from transcript) |

---

## Environment & Authentication

### Python Environments

| Skill | Environment Path |
|-------|-----------------|
| Audio2Md-convert | `c:\audio2mdPython` / `~/audio2mdPython` |
| Video2Md-convert | `c:\video2mdPython` / `~/video2mdPython` |
| Video2PDF-convert | `c:\video2pdfPython` / `~/video2pdfPython` |
| Video-clip-extractor | (stdlib only — no venv needed) |
| Text2Speech | `c:\text2speechPython` / `~/text2speechPython` |
| Text2Podcast | `c:\text2podcastPython` / `~/text2podcastPython` |

### Authentication

`CHAI_SDK_CLIENT_SECRET` is required only for:
- Video2Md-convert `--dedupe` mode
- Video2PDF-convert SRT fusion

All other operations work fully offline.

### System Dependencies

- **ffmpeg** — Required by Video2Md, Video2PDF, Video-clip-extractor, Text2Podcast (MP3 export)
- **Piper ONNX model** — Auto-discovered by Text2Speech and Text2Podcast
- **Phi-3.5 VLM model** — Required by Video2PDF for frame analysis
- **Whisper model** — Required by Audio2Md and Video2PDF for transcription
