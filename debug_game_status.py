"""Debug script to check game status detection."""

import asyncio
from src.services.retrieval import GameFetcher
from src.models import GameStatus
from src.services.lineup_agent import LineupAgent
from datetime import datetime

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
    
    print(f"\n=== GAME DATA ===")
    print(f"Game ID: {game.gid}")
    print(f"Home Team: {game.home_team.name if game.home_team else 'N/A'}")
    print(f"Away Team: {game.away_team.name if game.away_team else 'N/A'}")
    print(f"Game Status (gt): {game.gt}")
    print(f"Start Time: {game.stime}")
    print(f"Scores (scrs): {game.scrs}")
    print(f"Winner: {game.winner}")
    print(f"Is Started: {game.is_started}")
    print(f"Is Active: {game.is_active}")
    
    print(f"\n=== STATUS CHECKS ===")
    print(f"GameStatus.is_finished({game.gt}): {GameStatus.is_finished(game.gt)}")
    print(f"GameStatus.is_upcoming({game.gt}): {GameStatus.is_upcoming(game.gt)}")
    print(f"GameStatus.is_live({game.gt}): {GameStatus.is_live(game.gt)}")
    
    # Check date comparison
    if game.stime:
        try:
            from datetime import timezone
            match_time = datetime.fromisoformat(game.stime.replace("Z", "+00:00"))
            current_time = datetime.now(timezone.utc)
            print(f"\n=== DATE COMPARISON ===")
            print(f"Match Time: {match_time}")
            print(f"Current Time: {current_time}")
            print(f"Match is in past: {match_time < current_time}")
            print(f"Time difference: {current_time - match_time}")
        except Exception as e:
            print(f"Error parsing date: {e}")
    
    # Check LineupAgent detection
    print(f"\n=== LINEUP AGENT DETECTION ===")
    lineup_agent = LineupAgent()
    detected_status = lineup_agent.detect_status(game)
    print(f"Detected Status: {detected_status.value}")
    
    # Check if scores indicate finished game
    if game.scrs and len(game.scrs) >= 2:
        print(f"\n=== SCORE ANALYSIS ===")
        print(f"Has scores: True")
        print(f"Score values: {game.scrs}")
        print(f"Any non-zero scores: {any(score > 0 for score in game.scrs)}")
        print(f"Winner set: {game.winner is not None}")

if __name__ == "__main__":
    asyncio.run(main())
