"""Test script to generate dialogue-based podcast script."""

import asyncio
from src.services.lineup_agent import LineupAgent
from src.services.retrieval import GameFetcher, DataEnricher
from src.services.script_engine.dialogue_script_architect import DialogueScriptArchitect
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
    
    # Create lineup
    print("Creating lineup with LineupAgent...")
    lineup_agent = LineupAgent()
    lineup = await lineup_agent.create_lineup(context, total_duration_minutes=5)
    
    # Generate dialogue script
    print("Generating dialogue script...")
    dialogue_architect = DialogueScriptArchitect()
    script = await dialogue_architect.generate_dialogue_script(lineup, context)
    
    # Save to file
    filename = f"dialogue_script_game_{game_id}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(script)
    
    print(f"\n✓ Dialogue script saved to {filename}")
    print(f"\nPreview:\n{script[:500]}...")

if __name__ == "__main__":
    asyncio.run(main())
