"""Test script for LineupAgent."""

import asyncio
import json
from src.services.lineup_agent import LineupAgent
from src.services.retrieval import GameFetcher, DataEnricher
from src.models import ContentMode

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
    from src.models import GameStatus
    if GameStatus.is_finished(game.gt):
        mode = ContentMode.GAME_SPOTLIGHT_POSTGAME
    else:
        mode = ContentMode.GAME_SPOTLIGHT_PREGAME
    
    context = await data_enricher.enrich_games([game], mode)
    
    # Create lineup
    print("Creating lineup with LineupAgent...")
    lineup_agent = LineupAgent()
    lineup = await lineup_agent.create_lineup(context, total_duration_minutes=5)
    
    # Format output
    output_lines = []
    output_lines.append("=" * 80)
    output_lines.append("PODCAST LINEUP")
    output_lines.append("=" * 80)
    output_lines.append("")
    output_lines.append(f"Episode Title: {lineup.episode_title}")
    output_lines.append(f"Status: {lineup.status.value.upper()}")
    output_lines.append(f"Total Duration: {lineup.total_duration_minutes} minutes")
    output_lines.append(f"Priority Score: {lineup.priority_score}/100")
    output_lines.append("")
    output_lines.append("-" * 80)
    output_lines.append("SEGMENTS")
    output_lines.append("-" * 80)
    output_lines.append("")
    
    total_time = 0
    for i, segment in enumerate(lineup.segments, 1):
        output_lines.append(f"Segment {i}: {segment.topic}")
        output_lines.append(f"  Duration: {segment.allocated_time} seconds (~{segment.estimated_word_count} words)")
        output_lines.append(f"  Tone: {segment.tone.value.upper()}")
        if segment.key_data_points:
            output_lines.append(f"  Key Data Points:")
            for point in segment.key_data_points:
                output_lines.append(f"    • {point}")
        output_lines.append("")
        total_time += segment.allocated_time
    
    output_lines.append("-" * 80)
    output_lines.append(f"Total Allocated Time: {total_time} seconds ({total_time/60:.1f} minutes)")
    output_lines.append("=" * 80)
    
    # Save to file
    output_text = "\n".join(output_lines)
    filename = f"lineup_game_{game_id}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(output_text)
    
    print(f"\n✓ Lineup saved to {filename}")
    print(f"\n{output_text}")
    
    # Also generate script prompt
    print("\n" + "=" * 80)
    print("GENERATING SCRIPT PROMPT...")
    print("=" * 80)
    script_prompt = lineup_agent.generate_script_prompt(lineup, context)
    
    prompt_filename = f"script_prompt_game_{game_id}.txt"
    with open(prompt_filename, "w", encoding="utf-8") as f:
        f.write(script_prompt)
    
    print(f"✓ Script prompt saved to {prompt_filename}")
    print(f"\nPrompt preview (first 500 chars):\n{script_prompt[:500]}...")

if __name__ == "__main__":
    asyncio.run(main())
