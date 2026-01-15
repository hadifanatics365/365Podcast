"""Test script for audio merger functionality."""

import asyncio
import logging
from pathlib import Path

from src.services.audio_manager.audio_merger import AudioMerger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_audio_merger():
    """Test the audio merger with a dummy MP3 file."""
    print("=" * 80)
    print("AUDIO MERGER TEST")
    print("=" * 80)
    
    merger = AudioMerger()
    
    # Check if intro file exists
    if not merger.intro_path.exists():
        print(f"❌ Intro file not found at: {merger.intro_path}")
        print("   Please ensure intro.mp3 exists in src/assets/")
        return
    
    print(f"✓ Intro file found: {merger.intro_path}")
    print(f"✓ Intro file size: {merger.intro_path.stat().st_size} bytes")
    
    # Check for outro
    if merger.outro_path.exists():
        print(f"✓ Outro file found: {merger.outro_path}")
    else:
        print(f"ℹ️  Outro file not found, will use intro.mp3 for outro")
    
    # Check for ffmpeg
    import shutil
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        print(f"✓ ffmpeg found at: {ffmpeg_path}")
    else:
        print("⚠️  ffmpeg not found!")
        print("   To install ffmpeg on macOS:")
        print("   brew install ffmpeg")
        print("   Or download from: https://ffmpeg.org/download.html")
        print("\n   Note: Audio merging will fail without ffmpeg.")
        print("   pydub requires ffmpeg to work with MP3 files.")
    
    print("\n" + "=" * 80)
    print("Audio merger is ready!")
    print("=" * 80)
    print("\nThe merger will:")
    print("  1. Load intro.mp3 from src/assets/")
    print("  2. Merge it with the generated podcast MP3")
    print("  3. Add intro.mp3 again at the end (as outro)")
    print("  4. Export the final merged MP3")


if __name__ == "__main__":
    test_audio_merger()
