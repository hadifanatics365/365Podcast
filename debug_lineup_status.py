"""Debug script to check lineup status detection."""

import asyncio
from src.services.lineup_agent import LineupAgent
from src.services.retrieval import GameFetcher, DataEnricher
from src.models import ContentMode, GameStatus

async def main():
    game_id = 4452688
    
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
        print("Game status: POST-MATCH")
    else:
        mode = ContentMode.GAME_SPOTLIGHT_PREGAME
        print("Game status: PRE-MATCH")
    
    context = await data_enricher.enrich_games([game], mode)
    
    print(f"\n=== CONTEXT STRUCTURE ===")
    print(f"Context keys: {list(context.keys())}")
    print(f"Has 'game' key: {'game' in context}")
    if 'game' in context:
        print(f"Game type: {type(context['game'])}")
        if isinstance(context['game'], type(game)):
            print(f"Game object found in context!")
            print(f"Game.gt: {context['game'].gt}")
            print(f"Game.scrs: {context['game'].scrs}")
            print(f"Game.winner: {context['game'].winner}")
    
    # Create lineup
    print("\n=== LINEUP AGENT STATUS DETECTION ===")
    lineup_agent = LineupAgent()
    
    # Test detect_status directly
    if 'game' in context and isinstance(context['game'], type(game)):
        detected = lineup_agent.detect_status(context['game'])
        print(f"Direct detect_status result: {detected.value}")
    
    lineup = await lineup_agent.create_lineup(context, total_duration_minutes=5)
    
    print(f"\n=== LINEUP RESULT ===")
    print(f"Lineup status: {lineup.status.value}")
    print(f"Lineup match_status: {lineup.match_status}")

if __name__ == "__main__":
    asyncio.run(main())
