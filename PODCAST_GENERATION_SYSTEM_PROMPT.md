# Podcast Generation System Prompt
## Complete Workflow Definition

This document defines the EXACT process for generating a complete podcast episode from a game ID to a final MP3 file. This is the authoritative reference for the podcast generation workflow.

---

## Workflow Overview

**Input:** Game ID (string)  
**Output:** Complete MP3 file with intro, content, and outro  
**Format:** Three-person panel discussion (HOST, ANALYST, FAN)  
**Duration:** ~5 minutes (configurable)

---

## Step-by-Step Process

### **STEP 1: Initialize & Validate** ✅
**Action:** Set up environment and validate inputs

1. Check environment variables:
   - `SKIP_AUDIO_SYNTHESIS` - If set to "true", skip audio synthesis (testing mode)
   - For production runs, ensure it's "false" or unset

2. Validate game ID:
   - Must be a valid string/number
   - Log the game ID being processed

3. Initialize services:
   - `PodcastOrchestrator` - Main orchestrator
   - All services are auto-initialized by orchestrator

**Output:** Ready to proceed with validated game ID

---

### **STEP 2: Fetch Game Data** 📥
**Service:** `GameFetcher`  
**Action:** Retrieve raw game data from 365Scores API

1. Make API call:
   - Endpoint: `/data/games`
   - Parameters: `Games={game_id}`, `withmainodds=true`, `WithOddsPreviews=true`
   - Language: English (langId=1)
   - Timezone: UTC (tz=0)

2. Parse response:
   - Extract `Game` object(s)
   - Validate that game exists
   - Log game details (teams, date, status)

3. Error handling:
   - If game not found, raise `DataFetchError`
   - Log error and stop process

**Output:** `Game` object with basic information (teams, date, status, scores)

---

### **STEP 3: Determine Content Mode** 🎯
**Service:** `ContentRouter` (via Orchestrator)  
**Action:** Determine podcast mode based on game status

1. Check game status:
   - Use `GameStatus.is_finished(game.gt)` to check if game is finished
   - If finished → `GAME_SPOTLIGHT_POSTGAME`
   - If not finished → `GAME_SPOTLIGHT_PREGAME`

2. Set format:
   - Always use `PANEL` format (three-person discussion)
   - This is the default and only format

**Output:** Content mode (`GAME_SPOTLIGHT_PREGAME` or `GAME_SPOTLIGHT_POSTGAME`)

---

### **STEP 4: Enrich Game Data** 🔍
**Service:** `DataEnricher`  
**Action:** Add additional context to game data

**Sub-steps (in order):**

1. **Fetch Game Center Data (PRIMARY SOURCE - CRITICAL):**
   - **Endpoint:** `/Data/Games/GameCenter/` (capital D, G, C - critical for correct API call)
   - **Parameters (all required):**
     - `apptype=1`, `appversion=6.3.6`, `games={game_id}`, `lang={language_id}`
     - `oddsformat=1`, `shownaodds=true`, `storeversion=6.3.6`, `theme=dark`
     - `topbm=174`, `tz={timezone}`, `uc=21`, `usertestgroup=44`
     - `withexpanded=true`, `withexpandedstats=true`, `withnews=true`, `withstats=false`
   - **Returns:** Comprehensive game data including:
     - **Lineups:** In `Lineups` or `lineups` field (array of lineup objects)
     - **Betting Odds:** In `MainOdds`, `BetLine` fields (with options and rates)
     - **News:** In `News` or `news` field (each item has `URL` for article link)
     - **Standings:** In `Competitions` array (find by competition ID, extract `Standings` or `Tables[0].Standings`)
     - **Statistics:** Expanded stats in response
     - **Form/Trends:** Team trends and recent form data
   - **Extraction:** Parse response to extract all data categories from GameCenter response structure

2. **Fetch Pre-Game Statistics (for PRE-MATCH only):**
   - **Endpoint:** `/Data/Games/GameCenter/Statistics/PreGame`
   - **Parameters:** `apptype=1`, `appversion=6.3.9`, `gameid={game_id}`, `lang={language_id}`, `storeversion=6.3.9`, `theme=dark`, `topbm=174`, `tz={timezone}`, `uc=21`, `usertestgroup=44`
   - **Returns:** Pre-game statistics (head-to-head records, form data, etc.)

3. **Extract Data from GameCenter Response:**
   - **Lineups:** Extract from `Lineups` array, format as home/away with players, formation
   - **Betting Odds:** Extract from `MainOdds` or `BetLine`, include all options with current/original/old rates
   - **News:** Extract from `News` array or `_gamecenter_metadata.news`, each item has `URL` for article
   - **Standings:** Extract from `Competitions` array, find competition by ID, extract `Standings` or `Tables[0].Standings`
   - **Statistics:** Extract from expanded stats in GameCenter response

4. **Fallback: Fetch Standings (if not found in GameCenter):**
   - **Endpoint:** `/data/competitions/standings`
   - **Parameters:** `competitionid`, `seasonid` (optional)
   - **Use only if:** Standings not found in GameCenter `Competitions` array

5. **Fallback: Fetch News (if not found in GameCenter):**
   - **Endpoints:** `/data/games/news` and `/data/teams/news`
   - **PRE-MATCH:** News from last 24 hours before match
   - **POST-MATCH:** News from match end time onwards
   - **Filter by:** Relevance score and time window
   - **Use only if:** News not found in GameCenter `News` field

6. **Extract Intelligence:**
   - Form data (recent matches, win/loss streaks) - from GameCenter
   - Head-to-head records - from GameCenter or PreGame stats
   - Injury and suspension data - from GameCenter
   - Lineup information - from GameCenter `Lineups` field
   - Betting odds and trends - from GameCenter `MainOdds`/`BetLine` fields

7. **CRITICAL: Preserve Original Game Object:**
   - Store `context["original_game_obj"] = game`
   - This is essential for accurate status detection in LineupAgent

**Output:** Enriched context dictionary with:
- Game data (from GameCenter)
- **Lineups** (extracted from GameCenter `Lineups` field)
- **Betting odds** (extracted from GameCenter `MainOdds`/`BetLine` fields)
- **News articles** (extracted from GameCenter `News` field, with URLs)
- **Standings** (extracted from GameCenter `Competitions` array)
- Pre-game statistics (from PreGame Statistics endpoint)
- Statistics (from GameCenter expanded stats)
- Form, H2H, trends (from GameCenter)
- Original Game object

**⚠️ CRITICAL API ENDPOINT NOTES:**
- **Use `/Data/Games/GameCenter/` (capital D, G, C)** - NOT `/data/games/gamecenter`
- **Include ALL required parameters** for successful API calls
- **GameCenter response contains most data** (lineups, odds, news, standings) - extract from there first
- **Use fallback endpoints only if data not found in GameCenter response**

**This enriched context becomes PILLAR 1 (The WHAT) for the Holy Triangle.**

---

### **STEP 5: Extract Content Intelligence** 🧠
**Service:** `ContentIntelligence`  
**Action:** Analyze data and extract talking points

1. Analyze enriched context:
   - Extract top stories
   - Identify key talking points
   - Score data importance

2. Include betting insights:
   - Extract betting trends
   - Identify odds movements
   - Highlight prediction data

**Output:** `Intelligence` object with:
- Top stories
- Talking points
- Betting insights

---

### **STEP 6: Create Podcast Lineup** 📋
**Service:** `LineupAgent`  
**Action:** Plan episode structure using AI reasoning

**Sub-steps:**

1. **Detect Match Status:**
   - Prioritize `context["original_game_obj"]` for status detection
   - Check scores (`game.scrs`), winner (`game.winner`), game status (`game.gt`)
   - Compare match date to current time
   - Return `EpisodeStatus.PRE_MATCH` or `EpisodeStatus.POST_MATCH`

2. **Analyze with Claude:**
   - Call Claude API with game context and status
   - Prompt emphasizes:
     - Strict data grounding (only use facts in JSON)
     - Status-specific filtering
     - Narrative contextualization
     - Priority scoring
     - **CRITICAL: Data Extraction Requirement**
       - For PRE-MATCH: Extract specific data from: Game info, Recent form, H2H, Trends, Probable lineups, Betting oriented, News, Stats, Key players, Standings position, Odds movements, Predictions results
       - For POST-MATCH: Extract specific data from: Match events (MOTM, important subs, injuries, important events), Actual play time, Post game stats, Standings position, After game news, Prediction results, Post match info, Player ratings, Key players, Shots map, Box scores, Next matches mini recap
       - For EACH segment: Extract SPECIFIC data points and list them in `key_data_points`
       - Reference exact JSON paths in `source_data_refs` for each data point
       - Example: "Won last 3 matches: 2-1 vs Arsenal, 3-0 vs Chelsea" (not generic "good form")
       - Example: "Man United: 3rd place, 45 points, +12 goal difference" (not generic "high in table")
   - Claude suggests segments, priorities, key data points with specific values

3. **Allocate Time:**
   - Default: 5 minutes (300 seconds)
   - Divide into segments:
     - Intro: 15 seconds
     - Content segments: Remaining time
     - "The Final Ticket": 30 seconds (reserved)
     - Outro: 15 seconds
   - Ensure sum matches total duration

4. **Enforce Narrative Flow:**
   - PRE-MATCH: Hook → Context → Personnel → X-Factor → Smart Money → Final Ticket → Outro
   - POST-MATCH: Hook → Result → Events → Performance → Aftermath → Final Ticket → Outro

5. **Apply Tone Transitions:**
   - Tone scale (1-5): Cold/Analytical → High Octane/Excited
   - Max 2-level jumps between segments
   - Insert bridge segments if needed

6. **Filter Missing Data:**
   - Remove segments with "N/A" or "NOT_AVAILABLE"
   - Only keep segments with rich, factual data

7. **Create "The Final Ticket" Segment (ENHANCED):**
   - **Placement:** Always penultimate (before outro)
   - **PRE-MATCH Logic:**
     - Focus: Predict the outcome of the **current game**
     - Use current odds from the game data
     - Extract bookmaker name from betting data (default: "365Scores" if not available)
     - Extract specific market (e.g., "Full-time Result", "Over/Under 2.5")
     - Use real odds data points (current, original, trend)
     - Panel must name-drop the bookmaker explicitly
     - Panel must mention the specific market explicitly
   - **POST-MATCH Logic:**
     - Focus: Predict the outcome of the **NEXT game** for the **winning team**
     - Extract next match data from "next matches mini-recap" if available
     - If next match data unavailable, use general prediction context
     - Extract bookmaker name and market from available betting data
     - Use real odds data points for the next match
     - Panel must name-drop the bookmaker explicitly
     - Panel must mention the specific market explicitly
   - **Data Requirements:**
     - Must use real bookmaker name (from betting data or default)
     - Must use real market name (from betting data)
     - Must use real odds values (current, original, trend)
     - If betting data is missing, create placeholder but clearly indicate it's unavailable
   - **Producer Note:**
     - Instructs panel to explicitly mention bookmaker name
     - Instructs panel to explicitly mention market name
     - Instructs panel to detail odds (current, original, moving rates)
     - Creates friendly debate: one "safe" pick vs one "wildcard" pick
     - Each prediction must be supported by at least one data point from context

8. **Generate Producer Notes:**
   - Each segment gets conversational instructions
   - Emphasize "pub vibe" and tactical debate
   - Include specific guidance for personas

**Output:** `PodcastLineup` object with:
- Episode title
- Match status
- Segments (with timing, tone, **key_data_points**, **source_data_refs**, producer notes)
  - **key_data_points**: Specific facts extracted from GameContext (e.g., "Man United won last 3: 2-1 vs Arsenal, 3-0 vs Chelsea")
  - **source_data_refs**: JSON paths where data comes from (e.g., "game.home_team.name", "standings.home_team.position")
- Betting corner config (bookmaker name, market, odds, prediction context)
- Priority score

**CRITICAL: Data Extraction for Segments**
- PRE-MATCH segments must extract from: Game info, Recent form, H2H, Trends, Probable lineups, Betting, News, Stats, Key players, Standings, Odds movements, Predictions
- POST-MATCH segments must extract from: Match events, Actual play time, Post game stats, Standings, After game news, Predictions, Post match info, Player ratings, Key players, Shots map, Box scores, Next matches
- Each segment's `key_data_points` must contain SPECIFIC, extractable facts (not generic descriptions)
- Each segment's `source_data_refs` must reference exact JSON paths for verification

**This lineup becomes PILLAR 2 (The HOW) for the Holy Triangle.**

---

### **STEP 7: Generate Dialogue Script** ✍️
**Service:** `DialogueScriptArchitect`  
**Action:** Create natural three-person panel dialogue

**⚠️ CRITICAL: THE "HOLY TRIANGLE" PREREQUISITE**

This is a **Synthesis Step**. It MUST NOT begin until all three pillars are verified:

**PILLAR 1 (The WHAT):** Enriched Data Context from Step 4
- Verify: `context` dictionary exists and contains game data
- Verify: At minimum, basic game info (teams, date, status) is present
- If missing: Stop process and raise error

**PILLAR 2 (The HOW):** Structured Lineup & Timing from Step 6
- Verify: `PodcastLineup` object exists
- Verify: Lineup contains at least one segment
- Verify: Episode title is present
- Verify: Match status is determined (PRE_MATCH or POST_MATCH)
- If missing: Stop process and raise error

**PILLAR 3 (The WHO):** Personality & Vibe Profiles
- Verify: Three personas are defined:
  - HOST: The "Anchor" (defined in system prompt)
  - ANALYST: The "Brain" (defined in system prompt)
  - FAN: The "Heart" (defined in system prompt)
- These are hardcoded in the DialogueScriptArchitect system prompt
- If personas not defined: Stop process and raise error

**Only proceed to script generation once all three pillars are verified.**

**Sub-steps:**

1. **Verify Holy Triangle:**
   - Check PILLAR 1: Enriched context exists
   - Check PILLAR 2: Lineup exists with segments
   - Check PILLAR 3: Personas are defined
   - Log verification of all three pillars

2. **Verify Status:**
   - Double-check match status from game data
   - Ensure script reflects correct timeline (past = review, future = preview)

3. **Filter Data:**
   - Remove "NOT_AVAILABLE" and "N/A" markers
   - Only pass available data to Claude

4. **Panel Dynamics (ENHANCED):**
   - **HOST (The "Anchor"):**
     - Keeps time and pacing
     - Introduces segments and transitions
     - Mediates between Analyst and Fan
     - Maintains professional energy
     - Calibrated enthusiasm based on data importance
   - **ANALYST (The "Brain") - ANTI-ROBOTIC:**
     - Uses stats, xG, tactical terms
     - Skeptical of "luck" - prefers data-driven arguments
     - Explains numbers as "insider secrets" to friends
     - Uses football slang when passionate
     - Challenges emotional arguments with facts
     - **CRITICAL: He's "one of the guys" - casual, relatable, natural**
     - Avoid formal or robotic phrasing
     - Sound conversational, like chatting with mates at a pub, not presenting data in a boardroom
     - Keep lines SHORT unless explaining something important or telling a story
   - **FAN (The "Heart"):**
     - Passionate and biased towards one team (assigned dynamically at start)
     - Uses emotional arguments
     - Reacts with gut feeling, not just stats
     - Uses street-wise slang naturally
     - Mood matches situation (buzzing if won, gutted if lost)
   - **Conflict Rule (CRITICAL):**
     - At least once per episode, especially in "The Final Ticket" segment
     - Fan and Analyst MUST have a friendly disagreement
     - Based on their different perspectives: Data vs. Emotion
     - Example: Analyst says "The numbers don't lie" while Fan says "But you can't measure heart!"
     - Must be respectful and conversational, not argumentative
     - Host mediates the disagreement naturally

5. **Call Claude API:**
   - System prompt defines three personas with Panel Dynamics above
   - User prompt includes:
     - Episode title and status
     - Segment structure from lineup (PILLAR 2) with **KEY DATA POINTS for each segment**
     - **CRITICAL**: Each segment's KEY DATA POINTS are explicitly listed - these MUST be used in dialogue
     - **CRITICAL**: SOURCE DATA REFS show JSON paths - verify data exists before using
     - Filtered game data (PILLAR 1) - the actual enriched context
     - Betting information (especially for "The Final Ticket")
     - Critical dialogue instructions emphasizing:
       - **MANDATORY**: Use KEY DATA POINTS from each segment in the dialogue
       - **MANDATORY**: Reference specific values (team names, scores, stats, player names, odds)
       - **FORBIDDEN**: Generic dialogue without specific data references
       - Analyst must provide numbers/tactics from KEY DATA POINTS
       - Host must react to specific facts from KEY DATA POINTS
       - Fan must give emotional perspective about specific events from KEY DATA POINTS
     - Conflict rule requirement

6. **Enforce Dialogue Rules:**
   - "Work-mates" vibe
   - Use names, finish sentences, banter
   - No robotic scripting
   - Global football slang
   - N/A filter (ignore missing data)
   - Fan assignment (mandatory)
   - Calibrated enthusiasm
   - **SHORT LINES RULE (CRITICAL - ANTI-ROBOTIC):**
     - Keep dialogue lines SHORT (1-2 sentences max) by default
     - Only use longer lines when:
       * Explaining something important (tactical insight, key stat, crucial context)
       * Telling a story or anecdote
       * Providing context that requires more detail for clarity
     - Most lines should be brief and punchy - this creates natural flow and prevents robotic monologues
     - Break longer thoughts into multiple short exchanges between characters
     - Example SHORT (preferred): "[HOST]: Mental result! [ANALYST]: Yeah, the xG was wild. [FAN]: Seriously? [ANALYST]: 2.3 to 0.8. They bottled it."
     - Example LONG (only when explaining important context): "[ANALYST]: Look, here's the thing - when you look at the pressing triggers, they were actually winning the ball back in dangerous areas, but the final pass was just off. The xG model shows 2.3 expected goals, but they only converted once. That's the difference between a good performance and a great one."
   - Dynamic sentence flow (break monologues)
   - Conversational tennis (quick back-and-forth)
   - Trance kick-off energy (acknowledge intro music)

7. **Grounding & Anti-Hallucination (CRITICAL):**
   - **Strict Grounding Guardrail:**
     - If a specific data point (player name, score, odd, stat) is missing from Enriched Context (PILLAR 1), the script MUST:
       - Option 1: Pivot to a different available data point
       - Option 2: Generalize without specific numbers (e.g., "high odds" instead of "3.57")
       - Option 3: Skip the topic entirely
     - **NEVER fabricate:**
       - Specific player names not in context
       - Specific scores not in context
       - Specific odds not in context
       - Specific stats not in context
     - **Fabrication is a critical failure** - the script must be regenerated if hallucination is detected
   - **Verification:**
     - Cross-reference all specific data points in script against Enriched Context
     - Log any missing data points that were referenced
     - Flag for review if hallucination detected

**⚠️ CRITICAL: EXACT DURATION REQUIREMENT (MANDATORY)**

The generated dialogue script MUST match the exact duration specified in the PodcastLineup:
- **Total Duration:** The script must generate exactly `{total_duration_minutes} minutes` of dialogue
- **Default:** 5 minutes (300 seconds) - **NEITHER LESS NOR MORE**
- **Per-Segment Timing:** Each segment has a specific `allocated_time` (in seconds) and `estimated_word_count`
- **Speaking Rate:** 150 words per minute = 2.5 words per second
- **Calculation:** For each segment:
  - `estimated_word_count = allocated_time * 2.5`
  - Example: 60 seconds = 150 words, 90 seconds = 225 words

**Timing Enforcement Rules:**
1. **Word Count Targets (MANDATORY):**
   - Each segment MUST generate approximately the `estimated_word_count` specified
   - The total script MUST generate approximately `total_duration_minutes * 150` words
   - Example: 5 minutes = 750 words total (300 seconds * 2.5 words/second)

2. **Segment-Level Precision:**
   - Each segment's dialogue must match its `allocated_time` and `estimated_word_count`
   - If a segment is allocated 60 seconds (150 words), the dialogue for that segment must be approximately 150 words
   - Do NOT exceed or fall short of the segment's word count target

3. **Total Duration Validation:**
   - The complete script (all segments combined) must total exactly `{total_duration_minutes} minutes`
   - If the lineup specifies 5 minutes, the script must generate exactly 5 minutes of dialogue
   - **NEITHER LESS NOR MORE** - this is a hard requirement

4. **Timing Instructions in Prompt:**
   - The user prompt will include:
     - Total duration: `{total_duration_minutes} minutes`
     - Per-segment timing: Each segment's `allocated_time` and `estimated_word_count`
     - Word count targets for each segment
   - Claude MUST follow these timing constraints strictly

5. **Post-Generation Validation:**
   - After script generation, validate:
     - Total word count matches target (within ±5% tolerance)
     - Each segment's word count matches its target (within ±10% tolerance)
     - If validation fails, regenerate the script with stricter timing instructions

**Output:** Complete dialogue script with:
- Three-person panel conversation
- Natural flow following lineup (PILLAR 2)
- Authentic chemistry and slang
- Appropriate mood
- **EXACT DURATION MATCHING (CRITICAL):**
  - Total duration: Exactly `{total_duration_minutes} minutes` (default: 5 minutes)
  - Per-segment timing: Each segment matches its `allocated_time` and `estimated_word_count`
  - Word count targets: Total script = `{total_duration_minutes * 150}` words (default: 750 words)
  - **NEITHER LESS NOR MORE** than the specified duration
- **Data-backed discussions (from PILLAR 1) - CRITICAL:**
  - Each segment's KEY DATA POINTS are incorporated into the dialogue
  - Specific values are used (team names, scores, stats, player names, odds, standings)
  - No generic dialogue - all facts reference actual data from enriched context
  - Characters discuss, debate, and react to the specific KEY DATA POINTS
- At least one friendly disagreement between Fan and Analyst
- No fabricated data points
- **Verification:** All KEY DATA POINTS from segments appear in the dialogue

---

### **STEP 8: Synthesize Audio** 🎙️
**Service:** `MultiVoiceSynthesizer`  
**Action:** Convert script to audio using ElevenLabs

**⚠️ CRITICAL: VOICE ASSIGNMENTS (MUST BE ENFORCED)**

The script MUST use the following character labels, which map to distinct voices:
- **[HOST]:** Female voice (SARAH - Rachel voice: `21m00Tcm4TlvDq8ikWAM`)
- **[ANALYST]:** Male voice (MARCUS - Adam voice: `pNInz6obpgDQGcFmaJgB`)
- **[FAN]:** Male voice (RIO - Arnold voice: `VR6AewLTigWG4xSOukaG`)

**Voice Mapping Rules:**
1. The `MultiVoiceSynthesizer` maps character labels to voice IDs:
   - `[HOST]` → SARAH (Female voice)
   - `[ANALYST]` → MARCUS (Male voice)
   - `[FAN]` → RIO (Male voice)
2. The script from `DialogueScriptArchitect` MUST use these exact labels: `[HOST]:`, `[ANALYST]:`, `[FAN]:`
3. Each character MUST have a distinct voice - no two characters can share the same voice ID
4. The voice mapping is verified during initialization and logged

**Sub-steps:**

1. **Parse Script:**
   - Extract dialogue lines by character using regex pattern: `\[([A-Z]+)\]:`
   - Map character labels to voice IDs:
     - `[HOST]` → SARAH (Female voice: `21m00Tcm4TlvDq8ikWAM`)
     - `[ANALYST]` → MARCUS (Male voice: `pNInz6obpgDQGcFmaJgB`)
     - `[FAN]` → RIO (Male voice: `VR6AewLTigWG4xSOukaG`)
   - Verify each character has a unique voice ID
   - Log voice mapping for verification

2. **Synthesize Each Line:**
   - Call ElevenLabs API for each dialogue line
   - Use appropriate voice ID and settings for each character
   - **CRITICAL: ANALYST Voice Settings (Anti-Robotic):**
     - Stability: 0.35 (lower = more expressive, less robotic)
     - Similarity Boost: 0.8 (maintains voice quality while allowing expression)
     - Style: 0.4 (adds natural variation and conversational tone)
     - Use Speaker Boost: True (enhances clarity and naturalness)
     - These settings make ANALYST sound like "one of the guys" - casual, relatable, natural - NOT robotic or formal
   - Apply character-specific voice settings (stability, similarity_boost, style)
   - Format: MP3, 44100 Hz, 128 kbps

3. **Combine Audio:**
   - Add silence between speakers (500ms)
   - Concatenate all audio segments
   - Normalize format (44100 Hz, stereo)
   - Verify no voice duplication (each character has distinct voice)

**Output:** MP3 audio bytes (content only, no intro/outro)

**Validation:**
- Before synthesis, verify all three characters (HOST, ANALYST, FAN) are present in script
- Verify each character maps to a different voice ID
- Log voice assignments for debugging
- If any character is missing or voice mapping fails, raise `AudioSynthesisError`

---

### **STEP 9: Merge with Intro and Outro** 🎵
**Service:** `AudioMerger`  
**Action:** Combine intro, content, and outro with proper audio mastering

**Sub-steps:**

1. **Load Intro:**
   - File: `src/assets/intro.mp3`
   - **Audio Mastering:**
     - Detect sample rate of intro file
     - Normalize to 44100 Hz (standard podcast rate)
     - Convert to stereo (2 channels) if mono
     - Ensure consistent bitrate (128 kbps)
   - Add to beginning

2. **Add Content:**
   - Use synthesized audio from Step 8
   - Already normalized to 44100 Hz, stereo
   - Verify format consistency

3. **Load Outro:**
   - File: `src/assets/outro.mp3`
   - **Audio Mastering:**
     - Detect sample rate of outro file
     - Normalize to 44100 Hz (match intro and content)
     - Convert to stereo (2 channels) if mono
     - Ensure consistent bitrate (128 kbps)
   - Add to end

4. **Merge All Segments:**
   - **Critical: Sample Rate Normalization**
     - All three segments (intro, content, outro) MUST be at 44100 Hz
     - This ensures seamless blending without audio artifacts
     - If sample rates differ, resample to 44100 Hz before merging
   - Concatenate: intro + content + outro
   - Export as MP3 (128 kbps, 44100 Hz, stereo)
   - Verify no audio gaps or pops between segments

**Output:** Complete merged MP3 audio bytes with seamless transitions

---

### **STEP 10: Store Audio File** 💾
**Service:** `AudioStorage`  
**Action:** Save final MP3 file

1. **Generate Filename:**
   - Format: `YYYY/MM/DD/{job_id}_{game_hash}.mp3`
   - Date prefix for organization
   - Hash of game IDs for uniqueness

2. **Store File:**
   - Local storage: `/tmp/podcasts/`
   - Create directories if needed
   - Write MP3 bytes to file

3. **Generate URL:**
   - Local: `file:///tmp/podcasts/...`
   - S3: CDN URL (if configured)

**Output:** File path/URL to final MP3

---

### **STEP 11: Copy to Project Directory** 📁
**Action:** Copy final file to accessible location

1. **Extract File Path:**
   - From audio URL (remove `file://` prefix)

2. **Copy File:**
   - Destination: Project root
   - Filename: `podcast_game_{game_id}_complete.mp3`

3. **Verify:**
   - Check file exists
   - Check file size
   - Display file info

**Output:** Final MP3 file in project directory

---

## Error Handling

### At Each Step:
1. **Log the step** being executed
2. **Catch exceptions** and log detailed error
3. **Raise appropriate error** if step is critical
4. **Continue to next step** if step is optional (with warning)

### Critical Steps (must succeed):
- Step 2: Fetch Game Data
- Step 4: Enrich Game Data (minimum: basic game info must exist)
- Step 6: Create Podcast Lineup (must have segments)
- Step 7: Generate Dialogue Script (Holy Triangle must be verified)
- Step 8: Synthesize Audio
- Step 9: Merge Audio (sample rate normalization critical)
- Step 10: Store Audio

### Optional Steps (can fail with warning):
- Step 4: Enrich Data (some parts may fail, continue with available data)
- Step 5: Extract Intelligence (may have limited data)

---

## Configuration

### Default Settings:
- **Format:** PANEL (three-person discussion)
- **Duration:** 5 minutes
- **Include Betting:** True
- **Language:** English
- **Skip Audio Synthesis:** False (for production)

### Override Settings:
- Set `SKIP_AUDIO_SYNTHESIS=true` to skip audio synthesis (testing mode)
- Pass different `total_duration_minutes` to LineupAgent (default: 5)

---

## Output Summary

After completion, display:
- ✅ Job ID
- ✅ Status (completed)
- ✅ Duration (seconds)
- ✅ Format (panel)
- ✅ File location
- ✅ File size
- ✅ Script preview (first 200 chars)
- ✅ Holy Triangle verification status

---

## Validation Checklist

Before considering process complete:
- [ ] Game data fetched successfully
- [ ] Enriched context created (PILLAR 1 verified)
- [ ] Lineup created with segments (PILLAR 2 verified)
- [ ] Personas defined (PILLAR 3 verified)
- [ ] Holy Triangle verified before script generation
- [ ] Dialogue script generated
- [ ] Script contains at least one Fan-Analyst disagreement
- [ ] No fabricated data points in script
- [ ] Audio synthesized (if not skipped)
- [ ] Intro merged with proper sample rate normalization
- [ ] Outro merged with proper sample rate normalization
- [ ] Final MP3 file exists
- [ ] File size > 0
- [ ] File is valid MP3 format
- [ ] Audio has no gaps or artifacts between segments

---

## Notes

1. **API Credits:** Ensure Anthropic and ElevenLabs API keys have sufficient credits
2. **ffmpeg:** Required for audio merging (install via `brew install ffmpeg`)
3. **File Paths:** Intro and outro must exist in `src/assets/`
4. **Error Recovery:** If audio merging fails, original audio is used (with warning)
5. **Holy Triangle:** Never skip verification - it's the foundation of quality output
6. **Anti-Hallucination:** Always verify data points against enriched context
7. **Audio Mastering:** Sample rate normalization is critical for professional output

---

**This is the authoritative workflow definition. Any script implementing this process must follow these steps exactly in this order, with all enhancements and guardrails enforced.**
