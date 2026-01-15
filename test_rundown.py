"""Test script to generate human-readable production rundown."""

import asyncio
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
    print("Creating lineup with upgraded LineupAgent...")
    lineup_agent = LineupAgent()
    lineup = await lineup_agent.create_lineup(context, total_duration_minutes=5)
    
    # Generate human-readable rundown
    print("Generating human-readable production rundown...")
    rundown = lineup.to_human_rundown()
    
    # Save to file
    filename = f"production_rundown_game_{game_id}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(rundown)
    
    print(f"\n✓ Production rundown saved to {filename}")
    print(f"\n{rundown}")

if __name__ == "__main__":
    asyncio.run(main())
