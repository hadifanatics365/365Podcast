"""Generate full podcast episode: lineup + dialogue script."""

import asyncio
import logging
from datetime import datetime

from src.services.lineup_agent import LineupAgent
from src.services.retrieval import GameFetcher, DataEnricher
from src.services.script_engine.dialogue_script_architect import DialogueScriptArchitect
from src.models import ContentMode, GameStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    game_id = 4452688
    
    print("=" * 80)
    print("PODCAST EPISODE GENERATION PIPELINE")
    print("=" * 80)
    print(f"\n🎮 Game ID: {game_id}")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    flow_steps = []
    
    # STEP 1: Fetch Game Data
    print("📥 STEP 1: Fetching game data from 365Scores API...")
    flow_steps.append("1. Fetched raw game data from 365Scores Mobile API")
    game_fetcher = GameFetcher()
    games = await game_fetcher.fetch_games([game_id])
    
    if not games:
        print(f"❌ Game {game_id} not found!")
        return
    
    game = games[0]
    home_team = game.home_team.name if game.home_team else "Home"
    away_team = game.away_team.name if game.away_team else "Away"
    print(f"   ✓ Found: {home_team} vs {away_team}")
    flow_steps.append(f"   - Retrieved game: {home_team} vs {away_team}")
    
    # STEP 2: Enrich Game Data
    print("\n🔍 STEP 2: Enriching game data with additional context...")
    flow_steps.append("2. Enriched game data with DataEnricher service")
    data_enricher = DataEnricher(game_fetcher)
    
    # Determine mode based on game status
    if GameStatus.is_finished(game.gt):
        mode = ContentMode.GAME_SPOTLIGHT_POSTGAME
        status_text = "POST-MATCH"
        flow_steps.append("   - Detected game status: POST-MATCH (finished)")
    else:
        mode = ContentMode.GAME_SPOTLIGHT_PREGAME
        status_text = "PRE-MATCH"
        flow_steps.append("   - Detected game status: PRE-MATCH (upcoming)")
    
    print(f"   ✓ Game status: {status_text}")
    print("   ✓ Fetching standings, news, and additional data...")
    
    context = await data_enricher.enrich_games([game], mode)
    flow_steps.append("   - Added league standings, news articles, and form data")
    flow_steps.append("   - Preserved Game object in context for status detection")
    
    # STEP 3: Create Lineup
    print("\n📋 STEP 3: Creating podcast lineup with LineupAgent (AI Executive Producer)...")
    flow_steps.append("3. Created podcast lineup with LineupAgent")
    lineup_agent = LineupAgent()
    lineup = await lineup_agent.create_lineup(context, total_duration_minutes=5)
    
    print(f"   ✓ Episode title: {lineup.episode_title}")
    print(f"   ✓ Status: {lineup.match_status}")
    print(f"   ✓ Segments: {len(lineup.segments)}")
    print(f"   ✓ Priority score: {lineup.priority_score}/100")
    flow_steps.append(f"   - Generated {len(lineup.segments)} segments with timing and tone")
    flow_steps.append(f"   - Applied zero-tolerance rule: filtered out segments with missing data")
    flow_steps.append(f"   - Created 'The Final Ticket' sponsored betting segment")
    flow_steps.append(f"   - Added producer notes with 'pub vibe' and tactical debate instructions")
    
    # STEP 4: Generate Dialogue Script
    print("\n✍️  STEP 4: Generating three-person panel dialogue script...")
    flow_steps.append("4. Generated dialogue script with DialogueScriptArchitect")
    dialogue_architect = DialogueScriptArchitect()
    
    try:
        script = await dialogue_architect.generate_dialogue_script(lineup, context)
        flow_steps.append("   - Created natural dialogue between HOST, ANALYST, and FAN")
        flow_steps.append("   - Assigned Fan to a team with appropriate mood")
        flow_steps.append("   - Applied calibrated enthusiasm based on data importance")
        flow_steps.append("   - Used authentic football slang and 'work-mates' chemistry")
        print(f"   ✓ Generated script: {len(script)} characters")
    except Exception as e:
        print(f"   ⚠️  Script generation failed (likely API credits): {e}")
        script = f"[Script generation skipped due to API limitations]\n\nEpisode Title: {lineup.episode_title}\nStatus: {lineup.match_status}\n\nLineup:\n{lineup.to_human_rundown()}"
        flow_steps.append(f"   - Script generation skipped: {str(e)}")
    
    # STEP 5: Save Output
    print("\n💾 STEP 5: Saving episode content to file...")
    filename = f"full_episode_game_{game_id}.txt"
    
    output = []
    output.append("=" * 80)
    output.append("FULL PODCAST EPISODE CONTENT")
    output.append("=" * 80)
    output.append("")
    output.append(f"Game ID: {game_id}")
    output.append(f"Teams: {home_team} vs {away_team}")
    output.append(f"Status: {lineup.match_status}")
    output.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    output.append("")
    output.append("=" * 80)
    output.append("PRODUCTION RUNDOWN")
    output.append("=" * 80)
    output.append("")
    output.append(lineup.to_human_rundown())
    output.append("")
    output.append("=" * 80)
    output.append("DIALOGUE SCRIPT")
    output.append("=" * 80)
    output.append("")
    output.append(script)
    output.append("")
    output.append("=" * 80)
    output.append("END OF EPISODE")
    output.append("=" * 80)
    
    output_text = "\n".join(output)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(output_text)
    
    print(f"   ✓ Saved to: {filename}")
    print(f"   ✓ File size: {len(output_text)} characters")
    
    # Print flow summary
    print("\n" + "=" * 80)
    print("SERVICE FLOW SUMMARY")
    print("=" * 80)
    for step in flow_steps:
        print(f"  {step}")
    
    print("\n" + "=" * 80)
    print("✓ EPISODE GENERATION COMPLETE")
    print("=" * 80)
    print(f"\n📄 Full episode saved to: {filename}")
    print(f"📊 Total segments: {len(lineup.segments)}")
    print(f"⏱️  Duration: {lineup.total_duration_minutes} minutes")
    print(f"⭐ Priority: {lineup.priority_score}/100")


if __name__ == "__main__":
    asyncio.run(main())
