# Podcast Script Data Structure Summary

## Overview
This document summarizes how data is collected, enriched, and structured for podcast script generation, split by **Pre-Game** and **Post-Game** statuses.

---

## 🔄 Data Flow Architecture

```
GameFetcher → DataEnricher → ContentIntelligence → ScriptGenerator
     ↓              ↓                    ↓                ↓
  Raw Game    Enriched Data    Talking Points    Final Script
   Data         Context         (Optional)
```

---

## 📊 PRE-GAME DATA STRUCTURE

### 1. Core Game Information
**Source:** `Game` model from 365Scores API
- `game_id` - Unique game identifier
- `sport_type` - Sport type ID
- `competition` - Competition display name (e.g., "Premier League")
- `round` - Round name (e.g., "Round 15")
- `start_time` - Scheduled start time (`stime`)
- `venue` - Venue information:
  - `name` - Stadium name
  - `city` - City location

### 2. Team Information
**Source:** `Game.home_team` and `Game.away_team`
- `home_team`:
  - `id` - Team ID
  - `name` - Full team name
  - `short_name` - Abbreviated name
- `away_team`:
  - `id` - Team ID
  - `name` - Full team name
  - `short_name` - Abbreviated name

### 3. Lineups (if available)
**Source:** `Game.lineups` (when `has_lineups = True`)
- `lineups`:
  - `home`:
    - `formation` - Formation string (e.g., "4-3-3")
    - `players` - Array of player objects:
      - `name` - Player name
      - `position` - Position name
      - `number` - Shirt number
      - `is_captain` - Boolean
  - `away`:
    - Same structure as home
- `lineups_status` - Status text (e.g., "Confirmed", "Probable")

### 4. Pre-Game Statistics
**Source:** `Game.pre_game_statistics`
- `pre_game_stats` - Array of statistic objects:
  - `name` - Statistic name (e.g., "Goals per game", "Possession avg")
  - `values` - Array `[home_value, away_value]`

### 5. Betting Odds
**Source:** `Game.main_odds` (when `has_bets = True`)
- `betting`:
  - `type` - Bet type (e.g., "1X2", "Over/Under")
  - `options` - Array of betting options:
    - `name` - Option name (e.g., "Home Win", "Over 2.5")
    - `odds` - Decimal odds
    - `trend` - Trend indicator
  - `over_under_line` - Line value for over/under bets

### 6. Team Trends
**Source:** `Game.promoted_trends` (when `has_team_trends = True`)
- `trends` - Array of trend objects (structure depends on API)

### 7. Recent Form (Last Matches)
**Source:** `Game.last_matches`
- `form` - Array of recent match objects:
  - Team match history with results
  - Used to calculate form strings (e.g., "W-W-L-D-W")

### 8. League Standings
**Source:** `GameFetcher.fetch_standings()` - Separate API call to `/data/competitions/standings`
- `standings` - Standings object:
  - `competition_id` - Competition ID
  - `season_id` - Season ID
  - `table_name` - Table name/type (if multiple tables)
  - `total_teams` - Total number of teams in league
  - `home_team` - Home team standings:
    - `position` - Current league position
    - `points` - Total points
    - `played` - Matches played
    - `wins` - Wins
    - `draws` - Draws
    - `losses` - Losses
    - `goals_for` - Goals scored
    - `goals_against` - Goals conceded
    - `goal_difference` - Goal difference
    - `form` - Recent form string (if available)
  - `away_team` - Away team standings (same structure as home_team)
  - `position_difference` - Absolute difference in positions
  - `home_context` - Teams around home team position (above/below):
    - `above` - Teams above in standings
    - `current` - Current team data
    - `below` - Teams below in standings
  - `away_context` - Teams around away team position (same structure)
  - `top_three` - Top 3 teams in league
  - `bottom_three` - Bottom 3 teams in league

### 9. News Articles
**Source:** `NewsFetcher.fetch_relevant_news()` (last 24 hours)
- `news` - Array of news items (top 10 most relevant):
  - `id` - News ID
  - `title` - News headline
  - `text` - Full article text
  - `summary` - Article summary
  - `publish_date` - ISO format timestamp
  - `image_url` - News image URL
  - `source` - News source
  - `category` - News category
  - `relevance_score` - Calculated relevance (0.0-100.0)
- `news_count` - Total number of relevant news items found

### 10. Additional Enrichment (Optional)
**Source:** `GameFetcher.fetch_game_center()` - Fetches more detailed game data
- Merges additional pre-game data if available
- May include H2H records, deeper statistics, etc.

---

## 🏁 POST-GAME DATA STRUCTURE

### 1. Core Game Information
**Source:** `Game` model from 365Scores API
- `game_id` - Unique game identifier
- `sport_type` - Sport type ID
- `competition` - Competition display name
- `round` - Round name
- `start_time` - Actual start time

### 2. Team Information
**Source:** `Game.home_team` and `Game.away_team`
- Same structure as pre-game

### 3. Final Score & Result
**Source:** `Game` model
- `final_score`:
  - `home` - Home team final score
  - `away` - Away team final score
- `winner` - Winner indicator:
  - `0` = Draw
  - `1` = Home team won
  - `2` = Away team won

### 4. Match Events
**Source:** `Game.events`
- `events` - Array of event objects:
  - `time` - Event time (minute or timestamp)
  - `player` - Player name involved
  - `type` - Event type (goal, card, substitution, etc.)
  - `team` - Team indicator (0=home, 1=away)
  - `description` - Event description
  - `extra_player` - Additional player (for assists, etc.)

### 5. Match Statistics
**Source:** `Game.statistics` (when `has_statistics = True`)
- `statistics` - Array of statistic objects:
  - `name` - Statistic name (e.g., "Possession", "Shots on Target")
  - `values` - Array `[home_value, away_value]`
  - `percentages` - Array `[home_pct, away_pct]` (if available)

### 6. Detailed Statistics (Additional Fetch)
**Source:** `GameFetcher.fetch_game_statistics()` - Separate API call
- `detailed_statistics` - Extended statistics object
- May include more granular data (pass accuracy, duels won, etc.)

### 7. Top Performers
**Source:** `Game.top_performers_data` (when `has_top_performers = True`)
- `top_performers` - Array of player objects:
  - `name` - Player name
  - `rating` - Player rating/score
  - `team` - Team indicator (0=home, 1=away)

### 8. Actual Play Time
**Source:** `Game.actual_play_time`
- `actual_play_time`:
  - `first_half` - Minutes played in first half
  - `second_half` - Minutes played in second half
  - `extra_time` - Extra time minutes (if applicable)
  - `total` - Total minutes played

### 9. Betting Result
**Source:** `Game.main_odds` + `Game.winner`
- `betting_result`:
  - `type` - Bet type
  - `winning_options` - Array of option names that won
  - `match_winner` - Match winner (0/1/2)

### 9. League Standings
**Source:** `GameFetcher.fetch_standings()` - Separate API call to `/data/competitions/standings`
- `standings` - Standings object (updated after match):
  - Same structure as pre-game standings
  - Reflects updated positions after match result
  - Can show position changes and impact on league table

### 10. News Articles
**Source:** `NewsFetcher.fetch_relevant_news()` (from match end time onwards)
- `news` - Array of news items (top 10 most relevant):
  - Same structure as pre-game
  - Filtered to only include news published **after** match ended
  - Time window: Match end + 48 hours
- `news_count` - Total number of relevant news items

### 11. Additional Enrichment (Optional)
**Source:** `GameFetcher.fetch_game_center()` - Fetches full game center data
- Merges additional post-game data if available
- May include match highlights, extended analysis, etc.

---

## 🧠 INTELLIGENCE LAYER (Optional Enhancement)

**Source:** `ContentIntelligence.analyze()` - Processes enriched data to extract talking points

### Talking Points Generated:
1. **Injury Extractor** - Player injuries and suspensions
2. **Form Extractor** - Team form analysis and streaks
3. **Betting Extractor** - Betting insights and value picks
4. **Lineup Extractor** - Lineup changes and tactical notes

### Intelligence Context Structure:
- `top_stories` - Prioritized talking points (max 10-15)
- Each talking point includes:
  - `headline` - Short summary
  - `narrative` - Pre-composed natural language
  - `story_type` - Type (injury, form, betting, lineup)
  - `priority` - Priority level (HIGH, MEDIUM, LOW)
  - `relevance_score` - Relevance score (0.0-1.0)
  - `data_points` - Supporting data

---

## 📝 FINAL CONTEXT FOR SCRIPT GENERATOR

### Context Dictionary Structure:
```python
{
    "mode": "game_spotlight_pregame" | "game_spotlight_postgame" | "daily_recap",
    "games_count": int,
    "game": { ... },  # Single game data (for spotlight modes)
    "games": [ ... ],  # Array of game data (for daily recap)
    "ended_games": [ ... ],  # For daily recap
    "upcoming_games": [ ... ],  # For daily recap
    "live_games": [ ... ],  # For daily recap
}
```

### Script Generation Process:
1. **Enriched Context** (from `DataEnricher`) → JSON formatted
2. **Talking Points** (from `ContentIntelligence`) → Formatted as text section
3. **System Prompt** (from `PromptTemplates`) → Mode-specific instructions
4. **User Prompt** → Combines context JSON + talking points + instructions
5. **Claude API** → Generates script with SSML markers
6. **SSML Processor** → Validates and cleans SSML markers

---

## 🔍 POTENTIAL IMPROVEMENTS & MISSING DATA

### Pre-Game Enhancements:
- ✅ **Standings Position** - Team position in league table (NOW INCLUDED)
- ❌ **Head-to-Head Records** - Not explicitly extracted (may be in trends)
- ❌ **Key Player Stats** - Individual player season statistics
- ❌ **Weather Conditions** - Match day weather forecast
- ❌ **Referee Information** - Match official details
- ❌ **Historical Context** - Previous meetings, rivalries
- ⚠️ **Form Analysis** - Present but could be more detailed (win/loss streaks, goals scored/conceded)

### Post-Game Enhancements:
- ✅ **Standings Position** - Updated team positions after match (NOW INCLUDED)
- ❌ **Match Highlights** - Video highlights URLs or descriptions
- ❌ **Manager Quotes** - Post-match press conference quotes
- ❌ **Fan Reactions** - Social media sentiment or fan polls
- ❌ **Tactical Analysis** - Formation changes, tactical shifts
- ❌ **VAR Decisions** - VAR incidents and decisions
- ❌ **Substitution Impact** - Analysis of substitution effectiveness
- ⚠️ **Player Ratings** - Present but could include more detailed breakdowns
- ⚠️ **Expected Goals (xG)** - If available from API

### News Enhancements:
- ⚠️ **News Relevance** - Current logic is good, but could weight by:
  - Breaking news (higher priority)
  - Transfer rumors (for pre-game)
  - Injury updates (higher priority)
  - Manager statements (higher priority)

### General Enhancements:
- ❌ **Competition Context** - League standings, relegation battles, title races
- ❌ **Player Matchups** - Key player vs player statistics
- ❌ **Home/Away Form** - Separate home and away form analysis
- ❌ **Injury History** - Not just current injuries, but recent injury patterns

---

## 📌 NOTES

1. **Time Windows:**
   - Pre-game news: Last 24 hours
   - Post-game news: From match end + 48 hours

2. **Data Availability:**
   - Not all fields are always available (depends on API response)
   - Code handles missing data gracefully with `None` or empty arrays

3. **News Relevance Scoring:**
   - Direct game mention: +10 points
   - Team ID match: +8 points per team
   - Team name mention: +5 points per team
   - Player mention: +3 points per player
   - Competition match: +4 points
   - Recency bonus: +1 point per hour (last 6 hours)

4. **Intelligence Layer:**
   - Optional enhancement that adds structured talking points
   - Can be disabled if not needed
   - Extracts insights from the same enriched data
