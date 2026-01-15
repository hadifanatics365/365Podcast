# Podcast Episode Generation Flow Summary

## Overview
This document explains the complete flow of how the 365Podcast service generates a full podcast episode from a game ID to a complete dialogue script.

---

## Complete Pipeline Flow

### **STEP 1: Game Data Retrieval** 📥
**Service:** `GameFetcher`  
**Action:** Fetches raw game data from 365Scores Mobile API

- Makes API call to `/data/games` endpoint with game ID
- Retrieves basic game information (teams, date, status, scores)
- Returns `Game` object with all raw data

**Output:** Raw game object with teams, scores, status, and metadata

---

### **STEP 2: Data Enrichment** 🔍
**Service:** `DataEnricher`  
**Action:** Enriches raw game data with additional context

**Sub-steps:**
1. **Status Detection:** Determines if game is PRE-MATCH or POST-MATCH
   - Checks `GameStatus.is_finished(game.gt)` 
   - Sets mode: `GAME_SPOTLIGHT_PREGAME` or `GAME_SPOTLIGHT_POSTGAME`

2. **Standings Fetch:** Retrieves league standings
   - Calls `GameFetcher.fetch_standings(competition_id)`
   - Adds home/away team positions, league context

3. **News Fetch:** Retrieves relevant news articles
   - **PRE-MATCH:** News from last 24 hours before match
   - **POST-MATCH:** News from match end time onwards
   - Uses `NewsFetcher.fetch_relevant_news()` with relevance scoring
   - Filters by time window and game/team/player mentions

4. **Form Data:** Extracts recent form, H2H records, trends
   - Uses intelligence extractors (Form, Injury, Lineup, Betting)
   - Aggregates all data into structured context dictionary

5. **Critical:** Preserves original `Game` object
   - Stores `context["original_game_obj"] = game`
   - Ensures `LineupAgent` has access to all `Game` properties for accurate status detection

**Output:** Enriched context dictionary with:
- Game data
- Standings
- News articles
- Form, H2H, trends
- Lineups, injuries
- Betting odds
- Original Game object (for status detection)

---

### **STEP 3: Lineup Creation (AI Executive Producer)** 📋
**Service:** `LineupAgent`  
**Action:** Plans the podcast episode structure using AI reasoning

**Sub-steps:**

1. **Status Detection:**
   - Prioritizes `context["original_game_obj"]` (raw Game object)
   - Checks scores (`game.scrs`), winner (`game.winner`), game status (`game.gt`)
   - Compares match date to current time
   - Returns `EpisodeStatus.PRE_MATCH` or `EpisodeStatus.POST_MATCH`

2. **Data Analysis with Claude:**
   - Calls Claude API with game context and status
   - Prompt emphasizes:
     - **Strict Data Grounding:** Only use facts present in JSON
     - **Status-Specific Filtering:** PRE-MATCH vs POST-MATCH data pipelines
     - **Narrative Contextualization:** Generate segment titles from actual data
     - **Priority Scoring:** Major injuries, odds shifts = more air time
   - Claude suggests segments, priorities, and key data points

3. **Time Allocation:**
   - Divides `total_duration_minutes` (default: 5) into segments
   - Each segment gets `allocated_time` in seconds
   - Ensures sum matches total duration
   - Enforces minimum time for intro/outro

4. **Narrative Flow Enforcement:**
   - **PRE-MATCH Flow:**
     1. The Hook (Intro)
     2. Contextual Landscape (Standings, Form, H2H)
     3. The Personnel (Injuries, Lineups)
     4. The X-Factor (Tactical analysis)
     5. The Smart Money (Odds, Trends)
     6. The Final Ticket (Sponsored betting segment)
     7. Wrap-up (Outro)
   
   - **POST-MATCH Flow:**
     1. The Hook (Intro)
     2. The Result (Final score, winner)
     3. Key Events (Goals, MOTM, drama)
     4. Performance Analysis (Stats, xG, player ratings)
     5. Aftermath (Standings update, quotes)
     6. The Final Ticket (Next match prediction)
     7. Wrap-up (Outro)

5. **Tone Scale & Transitions:**
   - Uses Tone Scale (1-5): Cold/Analytical → High Octane/Excited
   - Enforces max 2-level jumps between consecutive segments
   - Inserts "Bridge" segments if needed for smooth transitions

6. **Zero-Tolerance Data Rule:**
   - Filters out segments with missing data ("N/A", "NOT_AVAILABLE")
   - Only creates segments with rich, factual data available
   - Skips topics naturally if data is missing

7. **"The Final Ticket" Segment:**
   - Always penultimate segment (before outro)
   - **PRE-MATCH:** Panel predicts current game outcome
   - **POST-MATCH:** Panel predicts next match for winning team
   - Includes bookmaker name, market, odds, prediction context
   - Producer note instructs panel debate (safe pick vs wildcard)

8. **Producer Notes Generation:**
   - Each segment gets a "Producer Note"
   - Instructions for "pub vibe" and tactical debate
   - Specific guidance for Moderator and Fan personas
   - Emphasizes conversational, friendly dialogue style

**Output:** `PodcastLineup` object containing:
- Episode title (data-driven, contextualized)
- Match status (PRE_MATCH or POST_MATCH)
- List of segments with:
  - Topic (narrative, not generic)
  - Key data points
  - Tone and tone level (1-5)
  - Allocated time (seconds)
  - Estimated word count
  - Source data references (JSON keys)
  - Transition cues
  - Producer notes
- Betting corner config (for "The Final Ticket")
- Priority score (0-100)

---

### **STEP 4: Dialogue Script Generation** ✍️
**Service:** `DialogueScriptArchitect`  
**Action:** Generates natural three-person panel dialogue script

**Sub-steps:**

1. **Status Verification:**
   - Double-checks match status from game data
   - Ensures script reflects correct timeline (past = review, future = preview)

2. **Data Filtering:**
   - Removes "NOT_AVAILABLE" and "N/A" markers from context
   - Only passes available data to Claude

3. **Claude API Call:**
   - System prompt defines three personas:
     - **HOST (The Calibrated Lead):** High-energy, professional, calibrated enthusiasm
     - **ANALYST (The Tactical Socialite):** Tactical expert, uses football slang
     - **FAN (The Terrace Soul):** Emotional, direct, assigned to one team
   - User prompt includes:
     - Episode title and status
     - Segment structure (from lineup)
     - Filtered game data
     - Betting information
     - Critical instructions for panel chemistry

4. **Dialogue Rules Enforced:**
   - **"Work-Mates" Vibe:** They work together at 365Scores
   - Use names, finish each other's sentences, light banter
   - **No Robotic Scripting:** Never mention "Segment 1", "Segment 2"
   - **Global Football Slang:** "Worldie", "Top bins", "Clinical finish", etc.
   - **N/A Filter:** Ignore missing data completely
   - **Fan Assignment:** Mandatory - assign Fan to one team at start
   - **Calibrated Enthusiasm:** Host's reaction scales with data importance
   - **Short, Punchy Sentences:** Avoid long monologues

5. **Output Format:**
   - Clear speaker labels: `HOST:`, `ANALYST:`, `FAN:`
   - Natural transitions between segments
   - [PAUSE:short/medium/long] markers for pacing
   - Follows lineup segment order but makes it conversational

**Output:** Complete dialogue script with:
- Three-person panel conversation
- Natural flow following lineup segments
- Authentic football slang and chemistry
- Appropriate mood based on match result
- Data-backed discussions

---

## Key Design Principles

### 1. **Data Grounding (Zero Hallucination)**
- Every fact must come from the provided `GameContext` JSON
- If data is missing, skip the topic - never invent
- Source data references tracked in each segment

### 2. **Status Awareness**
- PRE-MATCH: Focus on anticipation, tactics, predictions
- POST-MATCH: Focus on results, analysis, consequences
- Never treat a past game as a future event

### 3. **Narrative Contextualization**
- Segment titles generated from actual data
- Bad: "Tactical Preview" (generic)
- Good: "The Kanichowsky Factor: Can Hapoel Stop Maccabi's Engine?" (data-driven)

### 4. **Tonal Gradient**
- Smooth transitions between segments (max 2-level tone jumps)
- Bridge segments inserted when needed
- Calibrated enthusiasm based on data importance

### 5. **Human-Readable Output**
- Production rundown looks like professional radio script
- No raw JSON or technical metadata
- Beautiful formatting with headers, bullets, emojis

---

## Output Files

1. **`full_episode_game_{game_id}.txt`**
   - Complete episode content
   - Production rundown (segment breakdown)
   - Dialogue script (three-person panel)

2. **`production_rundown_game_{game_id}.txt`** (if generated separately)
   - Human-readable production rundown
   - Segment breakdown with timing and producer notes

---

## Current Status

✅ **Completed:**
- Game data retrieval
- Data enrichment (standings, news, form)
- Lineup creation with AI reasoning
- Status detection (PRE-MATCH vs POST-MATCH)
- Zero-tolerance data filtering
- "The Final Ticket" betting segment
- Producer notes with "pub vibe" instructions
- Three-person panel dialogue architecture

⚠️ **Note:** Dialogue script generation requires Anthropic API credits. When credits are available, the full dialogue script will be generated automatically.

---

## Example Flow for Game 4452688 (Arsenal vs Liverpool)

1. **Fetched:** Raw game data (Arsenal vs Liverpool, POST-MATCH, 0-0 draw)
2. **Enriched:** Added standings (404 - not available), news (0 items found), form data
3. **Lineup Created:** 5 segments, 5 minutes total, POST-MATCH status
   - Introduction (15s)
   - Arsenal 0-0 Liverpool: The Final Result (123s)
   - Key Match Events (117s)
   - The Final Ticket (30s)
   - Outro (15s)
4. **Script Generation:** Skipped due to API credits (would generate three-person panel dialogue)

---

## Next Steps

When API credits are available:
- Full dialogue script will be generated automatically
- Three-person panel conversation with HOST, ANALYST, and FAN
- Natural flow following the lineup structure
- Authentic chemistry and football slang
