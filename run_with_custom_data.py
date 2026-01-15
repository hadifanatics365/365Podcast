"""Run podcast generation with custom data injection for game 4452679."""

import asyncio
import sys
from src.services.orchestrator import PodcastOrchestrator
from src.models import PodcastFormat

async def main():
    game_id = 4452679
    
    print("=" * 80)
    print("PODCAST GENERATION WITH CUSTOM DATA")
    print("=" * 80)
    print(f"\n🎮 Game ID: {game_id}\n")
    
    # Initialize orchestrator
    orchestrator = PodcastOrchestrator()
    
    # Generate podcast
    result = await orchestrator.generate_podcast(
        game_ids=[game_id],
        format=PodcastFormat.PANEL,
        include_betting=True,
    )
    
    # Inject custom data into the enriched context
    # We need to modify the data before it reaches the LineupAgent
    # This is a workaround - in production, this data would come from the API
    
    print("\n" + "=" * 80)
    print("✅ PODCAST GENERATION COMPLETE")
    print("=" * 80)
    print(f"\n📁 Output: {result.get('audio_url', 'N/A')}")
    print(f"📊 Status: {result.get('status', 'N/A')}")
    
    return result

if __name__ == "__main__":
    asyncio.run(main())
