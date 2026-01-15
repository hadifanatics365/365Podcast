# Audio Merger Service

## Overview
The `AudioMerger` service automatically merges the intro music with the generated podcast content and adds it at the end as an outro.

## How It Works

### Flow
1. **Podcast Generation**: ElevenLabs generates the podcast MP3 from the script
2. **Audio Merging**: `AudioMerger` combines:
   - `intro.mp3` (from `src/assets/`) at the **start**
   - Generated podcast content in the **middle**
   - `intro.mp3` again at the **end** (as outro, or uses `outro.mp3` if it exists)
3. **Final Output**: Single merged MP3 file with intro + content + outro

### Integration
The merger is automatically integrated into `PodcastOrchestrator`:
- After audio synthesis (Step 6)
- Before audio storage (Step 7)
- If merging fails, the original audio is used (with a warning)

## Files

### Service File
- `src/services/audio_manager/audio_merger.py` - Main merger service

### Audio Assets
- `src/assets/intro.mp3` - Intro music (required)
- `src/assets/outro.mp3` - Outro music (optional, uses intro if not found)

## Requirements

### Python Package
- `pydub` - Installed via `pip install pydub`

### System Dependency
- **ffmpeg** - Required for MP3 processing
  - macOS: `brew install ffmpeg`
  - Linux: `apt-get install ffmpeg` or `yum install ffmpeg`
  - Windows: Download from https://ffmpeg.org/download.html

## Usage

The merger is **automatically used** when generating podcasts. No manual configuration needed.

### Manual Testing
```python
from src.services.audio_manager.audio_merger import AudioMerger

merger = AudioMerger()
merged_audio = merger.merge_audio(
    content_audio_bytes=podcast_mp3_bytes,
    include_intro=True,
    include_outro=True,
)
```

## Audio Format
- **Format**: MP3
- **Sample Rate**: 44100 Hz
- **Channels**: Stereo (2 channels)
- **Bitrate**: 128 kbps

All audio segments are normalized to these settings for consistent output.

## Error Handling
- If `intro.mp3` is missing: Skips intro, continues with content + outro
- If `outro.mp3` is missing: Uses `intro.mp3` for outro
- If ffmpeg is not installed: Raises `AudioSynthesisError` with helpful message
- If merging fails: Falls back to original audio (logs warning)

## Logging
The service logs:
- Loading of intro/outro files
- Duration of each segment
- Total merged duration
- Any warnings or errors

## Example Output
```
INFO: Loading intro from /path/to/src/assets/intro.mp3
INFO: Added intro: 5000ms
INFO: Added content: 300000ms
INFO: Loading outro from /path/to/src/assets/intro.mp3
INFO: Added outro: 5000ms
INFO: Merging audio segments...
INFO: Merged audio complete: 12345678 bytes, 310.0 seconds
```
