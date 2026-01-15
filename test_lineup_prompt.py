"""Test script to generate lineup and script prompt with transition cues."""

import asyncio
import json
from src.services.lineup_agent import LineupAgent
from src.services.retrieval import GameFetcher, DataEnricher
from src.models import ContentMode, GameStatus

async def main():
    game_id = 4643040
    
    print(f"Fetching game {game_id}...")
    
    # Fetch game data
    game_fetcher = GameFetcher()
    games = await game_fetcher.fetch_games([game_id])
    
    if not games:
        print(f"Game {game_id} not found!")
        return
    
    game = games[0]
    print(f"Found game: {game.home_team.name if game.home_team else 'Home'} vs {game.away_team.name if game.away_team else 'Away'}")
    
    # Enrich game data
    print("Enriching game data...")
    data_enricher = DataEnricher(game_fetcher)
    
    # Determine mode based on game status
    if GameStatus.is_finished(game.gt):
        mode = ContentMode.GAME_SPOTLIGHT_POSTGAME
    else:
        mode = ContentMode.GAME_SPOTLIGHT_PREGAME
    
    context = await data_enricher.enrich_games([game], mode)
    
    # Create lineup
    print("Creating lineup with refined LineupAgent...")
    lineup_agent = LineupAgent()
    lineup = await lineup_agent.create_lineup(context, total_duration_minutes=5)
    
    # Generate script prompt with transition cues
    print("Generating enhanced script prompt with transition cues...")
    script_prompt = lineup_agent.generate_script_prompt(lineup, context)
    
    # Save to file
    filename = f"script_prompt_with_transitions_game_{game_id}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(script_prompt)
    
    print(f"\n✓ Enhanced script prompt saved to {filename}")
    print(f"\n{'='*80}")
    print("SCRIPT PROMPT PREVIEW (first 1000 chars):")
    print(f"{'='*80}\n")
    print(script_prompt[:1000])
    print("\n... (see full file for complete prompt)")

if __name__ == "__main__":
    asyncio.run(main())
