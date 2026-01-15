# How to Run Podcast Generation

## Quick Start

To generate a complete podcast episode, simply run:

```bash
python3 run_podcast_generation.py [game_id]
```

**Example:**
```bash
python3 run_podcast_generation.py 4452876
```

## What It Does

The script follows the **exact workflow** defined in `PODCAST_GENERATION_SYSTEM_PROMPT.md`:

1. ✅ Validates game ID and environment
2. 📥 Fetches game data from 365Scores API
3. 🎯 Determines content mode (PRE-MATCH or POST-MATCH)
4. 🔍 Enriches data (standings, news, form, intelligence)
5. 📋 Creates podcast lineup with AI (LineupAgent)
6. ✍️ Generates dialogue script (DialogueScriptArchitect)
7. 🎙️ Synthesizes audio with ElevenLabs (multi-voice panel)
8. 🎵 Merges with intro and outro music
9. 💾 Stores final MP3 file
10. 📁 Copies to project directory

## Output

The script generates:
- **File:** `podcast_game_{game_id}_complete.mp3`
- **Location:** Project root directory
- **Format:** MP3 (128 kbps, 44.1 kHz, Stereo)
- **Content:** Intro music + Panel discussion + Outro music

## Requirements

1. **API Keys:**
   - Anthropic (Claude) API key with credits
   - ElevenLabs API key with credits

2. **System Dependencies:**
   - Python 3.9+
   - ffmpeg (for audio merging)
     ```bash
     brew install ffmpeg  # macOS
     ```

3. **Audio Files:**
   - `src/assets/intro.mp3` (must exist)
   - `src/assets/outro.mp3` (must exist)

## Configuration

### Environment Variables

- `SKIP_AUDIO_SYNTHESIS`: Set to `"true"` to skip audio synthesis (testing mode)
  - Default: `false` (audio synthesis enabled)

### Default Settings

- **Format:** Panel (three-person discussion)
- **Duration:** 5 minutes
- **Include Betting:** True
- **Language:** English

## Error Handling

The script will:
- ✅ Log each step as it executes
- ⚠️ Show warnings for optional steps that fail
- ❌ Stop and show error for critical steps that fail
- 📝 Display detailed error messages with stack traces

## Example Output

```
================================================================================
PODCAST GENERATION - COMPLETE WORKFLOW
================================================================================

🎮 Game ID: 4452876
⏰ Started at: 2026-01-15 07:00:00

✅ STEP 1: Initialize & Validate
   ✓ Audio synthesis enabled

🚀 STEP 2-10: Executing complete pipeline via PodcastOrchestrator...

📋 Request Configuration:
   - Game IDs: ['4452876']
   - Format: panel
   - Include Betting: True
   - Language: en

[... processing ...]

📁 STEP 11: Copy to Project Directory
   ✓ Copied to: /path/to/podcast_game_4452876_complete.mp3
   ✓ File exists: 3,734,508 bytes (3.56 MB)

================================================================================
✅ PODCAST GENERATION COMPLETE
================================================================================

📊 Results:
   - Job ID: pod_abc123def456
   - Status: completed
   - Duration: 233.3 seconds
   - Format: panel
   - Games: 1

📁 Final File:
   - Location: /path/to/podcast_game_4452876_complete.mp3
   - Size: 3,734,508 bytes (3.56 MB)

🎧 To listen:
   open '/path/to/podcast_game_4452876_complete.mp3'
```

## Troubleshooting

### "ffmpeg not found"
```bash
brew install ffmpeg
```

### "API credit balance too low"
- Check Anthropic API credits
- Check ElevenLabs API credits
- Update API keys in environment

### "Intro/outro file not found"
- Ensure `src/assets/intro.mp3` exists
- Ensure `src/assets/outro.mp3` exists

### "Game not found"
- Verify game ID is correct
- Check 365Scores API is accessible

## For AI Assistants

When asked to "run the podcast generation process", use this script:

```bash
python3 run_podcast_generation.py [game_id]
```

The script follows the exact workflow defined in `PODCAST_GENERATION_SYSTEM_PROMPT.md`. No deviations or shortcuts.
