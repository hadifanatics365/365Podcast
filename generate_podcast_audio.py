"""Generate full podcast with audio for a specific game."""

import asyncio
import logging
import os
from pathlib import Path

from src.models.requests import PodcastFormat, PodcastRequest
from src.services import PodcastOrchestrator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def main():
    game_id = "4452876"
    
    print("=" * 80)
    print("PODCAST GENERATION - FULL PIPELINE")
    print("=" * 80)
    print(f"\n🎮 Game ID: {game_id}\n")
    
    # Check if skip_audio_synthesis is set
    skip_audio = os.getenv("SKIP_AUDIO_SYNTHESIS", "false").lower() == "true"
    if skip_audio:
        print("⚠️  WARNING: SKIP_AUDIO_SYNTHESIS is set to True!")
        print("   Setting it to False for this run...\n")
        os.environ["SKIP_AUDIO_SYNTHESIS"] = "false"
    
    # Create request
    request = PodcastRequest(
        game_ids=[game_id],
        format=PodcastFormat.PANEL,  # Three-person panel
        include_betting=True,
        language="en",
    )
    
    print("📋 Request Configuration:")
    print(f"   - Game IDs: {request.game_ids}")
    print(f"   - Format: {request.format.value}")
    print(f"   - Include Betting: {request.include_betting}")
    print(f"   - Language: {request.language}\n")
    
    # Initialize orchestrator
    orchestrator = PodcastOrchestrator()
    
    try:
        print("🚀 Starting podcast generation...\n")
        result = await orchestrator.generate_podcast(request)
        
        print("\n" + "=" * 80)
        print("✅ PODCAST GENERATION COMPLETE")
        print("=" * 80)
        print(f"\n📊 Results:")
        print(f"   - Job ID: {result.job_id}")
        print(f"   - Status: {result.status}")
        print(f"   - Duration: {result.duration_seconds:.1f} seconds")
        print(f"   - Format: {result.format}")
        print(f"   - Games: {result.games_count}")
        
        if result.audio_url:
            print(f"\n🎵 Audio URL: {result.audio_url}")
            
            # Extract file path if local storage
            if result.audio_url.startswith("file://"):
                file_path = result.audio_url.replace("file://", "")
                abs_path = Path(file_path).absolute()
                print(f"\n📁 Audio File Location:")
                print(f"   {abs_path}")
                print(f"\n💡 To listen:")
                print(f"   open '{abs_path}'")
                print(f"   # Or")
                print(f"   afplay '{abs_path}'")
                
                # Check if file exists
                if Path(file_path).exists():
                    file_size = Path(file_path).stat().st_size
                    print(f"\n✓ File exists: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
                else:
                    print(f"\n⚠️  Warning: File not found at expected location")
            else:
                print(f"\n🌐 Audio is stored remotely (S3/CDN)")
                print(f"   Download URL: {result.audio_url}")
        else:
            print("\n⚠️  No audio URL returned (check logs for errors)")
        
        if result.script:
            script_length = len(result.script)
            print(f"\n📝 Script Generated: {script_length:,} characters")
            print(f"   Preview: {result.script[:200]}...")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
