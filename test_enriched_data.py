"""Test script to output the complete enriched data JSON after all API requests."""

import asyncio
import json
from src.models import ContentMode, GameStatus
from src.services.retrieval import GameFetcher, DataEnricher
from src.services.intelligence import ContentIntelligence

async def main():
    game_id = 4452679
    
    print("=" * 80)
    print("TESTING ENRICHED DATA CONTEXT")
    print("=" * 80)
    print(f"\n🎮 Game ID: {game_id}\n")
    
    # STEP 2: Fetch Game Data
    print("📥 STEP 2: Fetching game data...")
    game_fetcher = GameFetcher()
    games = await game_fetcher.fetch_games([game_id], with_main_odds=True, with_odds_previews=True)
    
    if not games:
        print(f"❌ Game {game_id} not found!")
        return
    
    game = games[0]
    print(f"✓ Found game: {game.home_team.name if game.home_team else 'Home'} vs {game.away_team.name if game.away_team else 'Away'}")
    
    # STEP 3: Determine Content Mode
    print("\n🎯 STEP 3: Determining content mode...")
    if GameStatus.is_finished(game.gt):
        mode = ContentMode.GAME_SPOTLIGHT_POSTGAME
        print("✓ Status: POST-MATCH")
    else:
        mode = ContentMode.GAME_SPOTLIGHT_PREGAME
        print("✓ Status: PRE-MATCH")
    
    # STEP 4: Enrich Game Data
    print("\n🔍 STEP 4: Enriching game data (making all API requests)...")
    print("  - Fetching game center data...")
    print("  - Fetching statistics...")
    print("  - Fetching standings...")
    print("  - Fetching news...")
    print("  - Extracting intelligence...")
    
    data_enricher = DataEnricher(game_fetcher)
    context = await data_enricher.enrich_games([game], mode)
    
    print("✓ Enrichment complete")
    
    # STEP 5: Extract Content Intelligence
    print("\n🧠 STEP 5: Extracting content intelligence...")
    content_intelligence = ContentIntelligence()
    intelligence = await content_intelligence.analyze(
        enriched_context=context,
        mode=mode,
        include_betting=True,
    )
    
    print(f"✓ Extracted {len(intelligence.top_stories)} top stories")
    
    # Add intelligence to context
    def serialize_talking_point(point):
        """Serialize a TalkingPoint to dict."""
        return {
            "id": point.id,
            "story_type": point.story_type.value if hasattr(point.story_type, 'value') else str(point.story_type),
            "priority": point.priority.value if hasattr(point.priority, 'value') else str(point.priority),
            "headline": point.headline,
            "narrative": point.narrative,
            "team_id": point.team_id,
            "team_name": point.team_name,
            "player_id": point.player_id,
            "player_name": point.player_name,
            "competition": point.competition,
            "game_id": point.game_id,
            "data_points": point.data_points,
            "source": point.source,
            "provider_name": point.provider_name,
            "relevance_score": point.relevance_score,
        }
    
    def serialize_game_intelligence(game_intel):
        """Serialize a GameIntelligence to dict."""
        return {
            "game_id": game_intel.game_id,
            "home_team": game_intel.home_team,
            "away_team": game_intel.away_team,
            "competition": game_intel.competition,
            "talking_points": [serialize_talking_point(p) for p in game_intel.talking_points],
            "injury_points": [serialize_talking_point(p) for p in game_intel.injury_points],
            "form_points": [serialize_talking_point(p) for p in game_intel.form_points],
            "betting_points": [serialize_talking_point(p) for p in game_intel.betting_points],
            "lineup_points": [serialize_talking_point(p) for p in game_intel.lineup_points],
            "total_points": game_intel.total_points,
            "high_priority_count": game_intel.high_priority_count,
        }
    
    context["intelligence"] = {
        "mode": intelligence.mode,
        "top_stories": [serialize_talking_point(story) for story in intelligence.top_stories],
        "games": [serialize_game_intelligence(game) for game in intelligence.games],
        "raw_context": intelligence.raw_context,
    }
    
    # Output complete enriched context
    print("\n" + "=" * 80)
    print("COMPLETE ENRICHED DATA CONTEXT (JSON)")
    print("=" * 80)
    print("\nThis is the data that will be used by:")
    print("  - STEP 6: LineupAgent (to create segments with KEY DATA POINTS)")
    print("  - STEP 7: DialogueScriptArchitect (to generate dialogue using this data)")
    print("\n" + "=" * 80 + "\n")
    
    # Convert to JSON with proper formatting
    def json_serializer(obj):
        """Custom JSON serializer for objects not serializable by default json code"""
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        elif hasattr(obj, 'to_dict'):
            return obj.to_dict()
        else:
            return str(obj)
    
    # Create a clean JSON representation
    context_json = json.dumps(context, indent=2, default=json_serializer, ensure_ascii=False)
    
    # Save to file
    output_file = f"enriched_data_game_{game_id}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(context_json)
    
    print(f"📄 Complete enriched data saved to: {output_file}")
    print(f"📊 File size: {len(context_json):,} characters")
    
    # Print summary
    print("\n" + "=" * 80)
    print("DATA SUMMARY")
    print("=" * 80)
    
    # Helper function to check if data exists and is not empty
    def has_data(key_path, context_dict=context):
        """Check if a nested key exists and has non-empty data."""
        keys = key_path.split(".")
        current = context_dict
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return False
        # Check if it's not None, not empty list, not empty dict
        if current is None:
            return False
        if isinstance(current, list) and len(current) == 0:
            return False
        if isinstance(current, dict) and len(current) == 0:
            return False
        return True
    
    def get_data_count(key_path, context_dict=context):
        """Get count of items in a data structure."""
        keys = key_path.split(".")
        current = context_dict
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return 0
        if isinstance(current, list):
            return len(current)
        if isinstance(current, dict):
            return len(current)
        return 1 if current else 0
    
    print("\n📋 Data Categories Status:")
    print()
    
    # Game info
    game_available = has_data("game") or has_data("game_data")
    print(f"  {'✓' if game_available else '✗'} Game info: {'Available' if game_available else 'Missing'}")
    if game_available:
        game_obj = context.get("game") or context.get("game_data", {})
        if isinstance(game_obj, dict):
            home = game_obj.get("home_team", {}).get("name") or (game_obj.get("comps", [{}])[0].get("name") if game_obj.get("comps") else None)
            away = game_obj.get("away_team", {}).get("name") or (game_obj.get("comps", [{}])[1].get("name") if game_obj.get("comps") and len(game_obj.get("comps", [])) > 1 else None)
            if home and away:
                print(f"    → {home} vs {away}")
    
    # Intelligence
    intel_available = has_data("intelligence")
    print(f"  {'✓' if intel_available else '✗'} Content intelligence: {'Available' if intel_available else 'Missing'}")
    if intel_available:
        top_stories_count = get_data_count("intelligence.top_stories")
        games_count = get_data_count("intelligence.games")
        if games_count > 0:
            talking_points_count = 0
            for game_intel in context["intelligence"].get("games", []):
                talking_points_count += len(game_intel.get("talking_points", []))
            print(f"    → Top stories: {top_stories_count}")
            print(f"    → Total talking points: {talking_points_count}")
            print(f"    → Games analyzed: {games_count}")
    
    # Check game_data structure for specific fields
    game_data = context.get("game_data") or context.get("games", [{}])[0] if context.get("games") else {}
    
    # Form
    form_available = has_data("game_data.form") or any("form" in str(point.get("story_type", "")).lower() for point in context.get("intelligence", {}).get("top_stories", []))
    print(f"  {'✓' if form_available else '✗'} Recent form: {'Available' if form_available else 'Missing'}")
    if form_available and not has_data("game_data.form"):
        form_points = [p for p in context.get("intelligence", {}).get("top_stories", []) if "form" in str(p.get("story_type", "")).lower()]
        print(f"    → {len(form_points)} form-related talking points")
    
    # Trends
    trends_available = has_data("game_data.trends") or any("trend" in str(point.get("source", "")).lower() for point in context.get("intelligence", {}).get("top_stories", []))
    print(f"  {'✓' if trends_available else '✗'} Trends: {'Available' if trends_available else 'Missing'}")
    if trends_available and not has_data("game_data.trends"):
        trend_points = [p for p in context.get("intelligence", {}).get("top_stories", []) if "trend" in str(p.get("source", "")).lower()]
        print(f"    → {len(trend_points)} trend-related talking points")
    
    # Lineups
    lineups_available = has_data("game_data.lineups") or has_data("game.lineups")
    print(f"  {'✓' if lineups_available else '✗'} Lineups: {'Available' if lineups_available else 'Missing'}")
    
    # Betting
    betting_available = has_data("game_data.betting") or has_data("game.main_odds") or has_data("game.best_odds")
    print(f"  {'✓' if betting_available else '✗'} Betting odds: {'Available' if betting_available else 'Missing'}")
    
    # Standings
    standings_available = has_data("game_data.standings")
    print(f"  {'✓' if standings_available else '✗'} Standings: {'Available' if standings_available else 'Missing'}")
    
    # News
    news_available = has_data("game_data.news")
    news_count = get_data_count("game_data.news")
    print(f"  {'✓' if news_available else '✗'} News: {'Available' if news_available else 'Missing'}")
    if news_available:
        print(f"    → {news_count} news items")
    
    # Statistics
    stats_available = has_data("game_data.pre_game_stats") or has_data("game.statistics") or has_data("game.pre_game_statistics")
    print(f"  {'✓' if stats_available else '✗'} Statistics: {'Available' if stats_available else 'Missing'}")
    
    # Injuries
    injuries_available = any("injury" in str(point.get("story_type", "")).lower() for point in context.get("intelligence", {}).get("top_stories", []))
    if not injuries_available and has_data("intelligence.games"):
        for game_intel in context["intelligence"].get("games", []):
            if len(game_intel.get("injury_points", [])) > 0:
                injuries_available = True
                break
    print(f"  {'✓' if injuries_available else '✗'} Injuries & suspensions: {'Available' if injuries_available else 'Missing'}")
    if injuries_available:
        injury_count = sum(len(g.get("injury_points", [])) for g in context.get("intelligence", {}).get("games", []))
        print(f"    → {injury_count} injury-related talking points")
    
    print("\n" + "=" * 80)
    print(f"✅ Complete enriched data context ready for STEP 6 & STEP 7")
    print(f"📁 Output file: {output_file}")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
