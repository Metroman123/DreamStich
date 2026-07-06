# DreamStitch

DreamStitch is an experimental desktop video-dream generator. It builds atmospheric video sequences from a local video vault or live web searches, using mood text, voice input, FFmpeg stitching, VLC playback, and an optional local GGUF AI model.
Works Best with Python-3.12
## Current Features

- CustomTkinter desktop interface
- Local video vault scanning
- YouTube crawling with `yt-dlp`
- Mood presets and mood-word expansion
- Whisper voice transcription
- FFmpeg-based video stitching and crossfades
- VLC playback
- Optional local GGUF AI Director through `llama-cpp-python`
- Safe fallback to Python rule-based dream generation
- Early structure for a manual GitHub updater

## Project Status

DreamStitch is still a prototype. The current goal is to keep the working rule-based system intact while adding an optional AI Director layer.

The AI Director does not generate video. It interprets a mood or experience and returns dream tags, a visual category arc, and a short direction summary.

If the AI model is missing, fails to load, or returns invalid output, DreamStitch falls back to the built-in Python rules.

## Recommended Folder Structure

```text
DreamStitch/
├── Player.py
├── crawler_core.py
├── ai_director.py
├── updater.py
├── requirements.txt
├── README.md
├── version.txt
├── dreamstitch_settings.json
├── dream_index.json
├── Videos/
├── models/
├── dream_renders/
└── audio/
```

The AI Director searches for GGUF models in this order:

```text
ai/
models/
model/
.
```

So if your folder is named `models`, that is fine.

## Setup

### 1. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install FFmpeg

DreamStitch uses FFmpeg and FFprobe for stitched dream rendering.

Recommended Windows install:

```powershell
winget install Gyan.FFmpeg
```

Verify:

```powershell
ffmpeg -version
ffprobe -version
```

### 4. Install VLC

DreamStitch uses VLC through `python-vlc`.

Install VLC from:

```text
https://www.videolan.org/vlc/
```

Normal Windows install path:

```text
C:\Program Files\VideoLAN\VLC
```

### 5. Add a local AI model

Place your GGUF model in:

```text
DreamStitch/
└── models/
    └── your-model.gguf
```

Example:

```text
models/vikhr-gemma-2b-instruct-q4_k_m.gguf
```

The model file does not need to be committed to GitHub.

## Running DreamStitch

```bash
python Player.py
```

## Local Vault Mode

Local Vault mode uses video files from the `Videos/` folder.

Supported extensions:

```text
.mp4
.mkv
.webm
.mov
```

Click `SCAN VAULT` to refresh the local video list.

DreamStitch builds `dream_index.json` with file path, name, category, dream tags, energy level, and weirdness score.

## Web Crawler

Click `CRAWL WEB` to download videos into the local vault.

The crawler uses `yt-dlp` and the keyword bank inside `crawler_core.py`.

Crawler categories include liminal empty spaces, dreamcore/weirdcore, vaporwave/nostalgia, public access weirdness, corporate VHS, old educational films, smooth jazz, strange technology, weather warnings, transportation, and retail/service spaces.

Downloaded videos go into `Videos/`.

## Mood Input

You can type phrases such as:

```text
parallel universe old disconnected
lonely night rain
chaotic funny weird
```

DreamStitch expands these words into internal tags, then chooses clips based on category and score.

## Voice Input

DreamStitch uses Whisper to transcribe short voice input.

Click `CAPTURE VOICE`. The app records a short audio clip, transcribes it, and places the text into the mood input box.

Default capture length: 6 seconds.

## FFmpeg Dream Stitching

DreamStitch can render selected clips into one stitched dream video. It creates short normalized fragments, then crossfades them together using FFmpeg.

Generated renders go into `dream_renders/`.

If FFmpeg fails or is missing, DreamStitch falls back to live segment playback.

## AI Director

The AI Director lives in `ai_director.py`.

Its job is to interpret mood text and return a structured dream plan.

Example input:

```text
everything feels old but not nostalgic, like a parallel version of the same room
```

Example AI output:

```json
{
  "tags": ["liminal", "surreal", "vhs", "uncanny", "night"],
  "arc": ["liminal", "vhs", "night", "surreal", "jazz", "unknown"],
  "summary": "A quiet uncanny dream arc built around displaced familiarity."
}
```

DreamStitch then uses this result to pick and order clips.

If the AI is unavailable, the result source is `python_rules`.

If the local GGUF model is used successfully, the result source is `local_ai`.

## Confirming the AI Is Working

Add debug output in `generate_dream()` after the AI result is created:

```python
print("=" * 60)
print("DreamStitch AI Director")
print("Source :", ai_result["source"])
print("Summary:", ai_result["summary"])
print("Tags   :", ai_result["tags"])
print("Arc    :", ai_result["arc"])
print("=" * 60)
```

If you see `Source : local_ai`, the GGUF model is being used.

If you see `Source : python_rules`, DreamStitch is falling back to the built-in Python rules.

## Manual GitHub Updater

The updater should be manual, not automatic.

Recommended flow:

```text
Settings
└── Check for Updates
```

The updater should check the latest GitHub release, compare it to `version.txt`, download the latest release ZIP, back up existing app files, replace only program files, and preserve local user data.

Protected folders/files should include:

```text
Videos/
audio/
dream_renders/
models/
model/
ai/
dreamstitch_settings.json
dream_index.json
.venv/
venv/
.git/
```

In `updater.py`, set your repo like this:

```python
GITHUB_REPO = "Metroman123/DreamStich"
```

Note: the repo name currently appears to be `DreamStich` without the second `t`. If the project name is meant to be `DreamStitch`, consider renaming the GitHub repo later for consistency.

## Git and Git LFS

Large AI model files should usually not be committed directly to Git.

Recommended: keep real GGUF model files local and add this to `.gitignore`:

```gitignore
models/*.gguf
ai/*.gguf
model/*.gguf
```

If you do want to track GGUF files with Git LFS:

```bash
git lfs install
git lfs track "*.gguf"
git add .gitattributes
git add models/*.gguf
git commit -m "chore: track GGUF models with Git LFS"
```

## Suggested .gitignore

```gitignore
__pycache__/
*.pyc
.venv/
venv/

Videos/
audio/
dream_renders/
_dreamstitch_update/
DreamStitch_backup_before_update_*/

models/*.gguf
ai/*.gguf
model/*.gguf

.DS_Store
.idea/
.vscode/
```

## Suggested Commit Message

```text
feat: add initial local AI Director integration for DreamStitch
```

Suggested body:

```text
- Added DreamAIDirector for local GGUF model support
- Integrated optional AI mood analysis into DreamStitch
- Added fallback to Python rule-based dream generation
- Preserved existing crawler and dream index workflow
- Prepared architecture for future AI-driven dream sequencing
```

## Troubleshooting

### ModuleNotFoundError

```bash
pip install -r requirements.txt
```

### Git LFS not found

```powershell
winget install GitHub.GitLFS
git lfs install
```

### .git/index.lock exists

```powershell
dir -Force
dir -Force .git
Remove-Item .git\index.lock -Force
```

Only remove `index.lock`. Do not delete `.git`.

### AI model not loading

Check that `llama-cpp-python` is installed, the model file is `.gguf`, and the file is inside `models/`, `ai/`, `model/`, or the project root.

### FFmpeg not found

```bash
ffmpeg -version
ffprobe -version
```

### VLC playback issues

Make sure VLC is installed in the normal Windows location.

## Roadmap

### v0.2.0
- Visible AI status label
- AI debug panel
- Model reload button
- Browse button for selecting GGUF model

### v0.3.0
- Stronger voice-to-dream pipeline
- Whisper transcript history
- AI-generated dream recipe display

### v0.4.0
- Manual GitHub update checker
- Release ZIP support
- Safer backup/restore flow

### v0.5.0
- Better vault indexing
- Improved category detection
- Clip usage history
- Avoid repeating recently used clips

### v1.0.0
- Stable desktop release
- Installer
- Full setup guide
- Public demo build

## Long-Term Concept

DreamStitch is meant to feel like a signal machine rather than a normal video player.

```text
Voice / mood / context
        ↓
Whisper transcription
        ↓
Local AI Director
        ↓
Dream recipe
        ↓
Video vault / live search
        ↓
FFmpeg stitching
        ↓
VLC playback
```
