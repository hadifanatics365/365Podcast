"""
Master script for complete podcast generation workflow.

This script follows the exact process defined in PODCAST_GENERATION_SYSTEM_PROMPT.md.
Run this script with a game ID to generate a complete podcast episode.

Usage:
    python3 run_podcast_generation.py [game_id]

Example:
    python3 run_podcast_generation.py 4452876
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from src.models.requests import PodcastFormat, PodcastRequest
from src.services import PodcastOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_complete_workflow(game_id: str) -> str:
    """
    Execute the complete podcast generation workflow.
    
    Follows the exact process defined in PODCAST_GENERATION_SYSTEM_PROMPT.md.
    
    Args:
        game_id: Game ID to generate podcast for
        
    Returns:
        Path to final MP3 file
        
    Raises:
        Exception: If any critical step fails
    """
    print("=" * 80)
    print("PODCAST GENERATION - COMPLETE WORKFLOW")
    print("=" * 80)
    print(f"\n🎮 Game ID: {game_id}")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # STEP 1: Initialize & Validate
    print("✅ STEP 1: Initialize & Validate")
    skip_audio = os.getenv("SKIP_AUDIO_SYNTHESIS", "false").lower() == "true"
    if skip_audio:
        print("   ⚠️  WARNING: SKIP_AUDIO_SYNTHESIS is set to True!")
        print("   Setting it to False for this run...\n")
        os.environ["SKIP_AUDIO_SYNTHESIS"] = "false"
    else:
        print("   ✓ Audio synthesis enabled\n")
    
    # STEP 2-10: Execute via Orchestrator
    print("🚀 STEP 2-10: Executing complete pipeline via PodcastOrchestrator...\n")
    
    # Create request (follows system prompt configuration)
    request = PodcastRequest(
        game_ids=[game_id],
        format=PodcastFormat.PANEL,  # Always panel format
        include_betting=True,  # Default: include betting
        language="en",  # Default: English
    )
    
    print("📋 Request Configuration:")
    print(f"   - Game IDs: {request.game_ids}")
    print(f"   - Format: {request.format.value}")
    print(f"   - Include Betting: {request.include_betting}")
    print(f"   - Language: {request.language}\n")
    
    # Initialize orchestrator (handles Steps 2-10 internally)
    orchestrator = PodcastOrchestrator()
    
    try:
        # Execute workflow (Steps 2-10 are handled by orchestrator)
        result = await orchestrator.generate_podcast(request)
        
        # STEP 11: Copy to Project Directory
        print("\n📁 STEP 11: Copy to Project Directory")
        
        if not result.audio_url:
            raise Exception("No audio URL returned from orchestrator")
        
        # Extract file path
        if result.audio_url.startswith("file://"):
            source_path = result.audio_url.replace("file://", "")
        else:
            raise Exception(f"Audio stored remotely (S3/CDN): {result.audio_url}")
        
        # Copy to project directory
        project_root = Path(__file__).parent
        final_filename = f"podcast_game_{game_id}_complete.mp3"
        final_path = project_root / final_filename
        
        import shutil
        shutil.copy2(source_path, final_path)
        
        print(f"   ✓ Copied to: {final_path}")
        
        # Verify file
        if final_path.exists():
            file_size = final_path.stat().st_size
            print(f"   ✓ File exists: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
        else:
            raise Exception(f"File not found after copy: {final_path}")
        
        # Display summary
        print("\n" + "=" * 80)
        print("✅ PODCAST GENERATION COMPLETE")
        print("=" * 80)
        print(f"\n📊 Results:")
        print(f"   - Job ID: {result.job_id}")
        print(f"   - Status: {result.status}")
        print(f"   - Duration: {result.duration_seconds:.1f} seconds")
        print(f"   - Format: {result.format}")
        print(f"   - Games: {result.games_count}")
        print(f"\n📁 Final File:")
        print(f"   - Location: {final_path}")
        print(f"   - Size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
        
        if result.script:
            script_length = len(result.script)
            print(f"\n📝 Script Generated: {script_length:,} characters")
            print(f"   Preview: {result.script[:200]}...")
        
        print("\n🎧 To listen:")
        print(f"   open '{final_path}'")
        print(f"   # Or")
        print(f"   afplay '{final_path}'")
        print("\n" + "=" * 80)
        
        return str(final_path)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


def main():
    """Main entry point."""
    # Get game ID from command line or use default
    if len(sys.argv) > 1:
        game_id = sys.argv[1]
    else:
        # Default game ID for testing
        game_id = "4452876"
        print(f"⚠️  No game ID provided, using default: {game_id}\n")
        print("   Usage: python3 run_podcast_generation.py [game_id]\n")
    
    # Run workflow
    try:
        final_path = asyncio.run(run_complete_workflow(game_id))
        print(f"\n✅ Success! Podcast saved to: {final_path}")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
