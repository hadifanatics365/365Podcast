"""Character profiles for multi-voice podcast generation."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CharacterRole(str, Enum):
    """Character roles in the podcast."""
    HOST = "host"
    ANALYST = "analyst"
    LEGEND = "legend"


@dataclass
class VoiceSettings:
    """ElevenLabs voice settings for fine-tuned control."""
    stability: float = 0.5  # 0-1: Lower = more expressive, Higher = more stable
    similarity_boost: float = 0.75  # 0-1: How closely to match the original voice
    style: float = 0.0  # 0-1: Style exaggeration (for supported voices)
    use_speaker_boost: bool = True  # Enhance clarity


@dataclass
class Character:
    """A podcast character with voice and personality."""

    name: str
    role: CharacterRole
    voice_id: str
    description: str
    voice_style: str
    personality: str
    background: str
    speaking_style: str
    signature_phrases: list[str]
    voice_settings: VoiceSettings = field(default_factory=VoiceSettings)

    def get_voice_direction(self) -> str:
        """Get voice direction for script generation."""
        return f"{self.name} ({self.role.value}): {self.voice_style}"

    def get_persona_prompt(self) -> str:
        """Get full persona description for LLM prompt."""
        return f"""{self.name} ({self.role.value.upper()}) - "{self.description}"
   Background: {self.background}
   Personality: {self.personality}
   Speaking Style: {self.speaking_style}
   Signature Phrases: {', '.join(f'"{p}"' for p in self.signature_phrases[:4])}"""


# =============================================================================
# THE TRIO - Main Characters
# =============================================================================

SARAH_HOST = Character(
    name="Sarah",
    role=CharacterRole.HOST,
    voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel - warm, engaging, professional
    description="The Conductor",
    voice_style="Warm, engaging, authoritative yet approachable",
    personality="""Mid-40s veteran sports broadcaster who's interviewed legends and covered World Cups.
She has a gift for making complex tactics accessible and keeping big personalities in check.
Sharp wit, genuine laugh, and the kind of presence that makes guests open up.
Knows when to let a debate run and when to rein it in.""",
    background="""Former sports journalist who worked her way up from local radio to national TV.
Covered three World Cups, two Euros, and countless Champions League finals.
Known for her iconic post-match interviews that go viral for their authenticity.""",
    speaking_style="""Conversational but commanding. Asks the questions viewers are thinking.
Uses inclusive language ("Let's break this down", "Help me understand").
Excellent at playing devil's advocate to spark debate between Marcus and Rio.
Her laugh is warm and genuine - she enjoys the banter.""",
    signature_phrases=[
        "Break it down for me",
        "Help us understand",
        "What are you seeing that we're not?",
        "That's a big call!",
        "I love that take",
        "Welcome back to three six five Scores",
        "Let's get into it",
    ],
    voice_settings=VoiceSettings(stability=0.4, similarity_boost=0.8, style=0.2),
)

MARCUS_ANALYST = Character(
    name="Marcus",
    role=CharacterRole.ANALYST,
    voice_id="pNInz6obpgDQGcFmaJgB",  # Adam - calm, measured, authoritative
    description="The Human Algorithm",
    voice_style="Calm, measured, direct, occasionally dry humor",
    personality="""Early 30s data scientist who played semi-professionally before an injury ended his career.
Channeled his love of football into analytics. Worked at top clubs before becoming a pundit.
Not a stereotypical "nerdy stats guy" - he's confident, can banter, and knows when to drop a killer stat.
Gets genuinely excited when data reveals something counterintuitive.""",
    background="""PhD in Sports Analytics from Loughborough. Consulted for three Premier League clubs.
Published groundbreaking research on pressing triggers and xG models.
The kind of analyst who players actually listen to because he explains things in football terms.""",
    speaking_style="""Precise but not robotic. Uses analogies to make stats relatable.
Can be playfully smug when his predictions come true. Enjoys winding up Rio.
When challenged, backs up his claims with specific numbers delivered with quiet confidence.
Occasionally surprises everyone by agreeing with the emotional take over the data.""",
    signature_phrases=[
        "The data tells an interesting story here",
        "If you look at the numbers",
        "Statistically speaking",
        "This is where it gets fascinating",
        "Let me give you some context",
        "The xG model suggests",
        "Here's what the data doesn't show you",
    ],
    voice_settings=VoiceSettings(stability=0.6, similarity_boost=0.75, style=0.0),
)

RIO_LEGEND = Character(
    name="Rio",
    role=CharacterRole.LEGEND,
    voice_id="VR6AewLTigWG4xSOukaG",  # Arnold - deep, confident, passionate
    description="The Icon",
    voice_style="Deep, passionate, speaks from lived experience",
    personality="""Late 40s former Champions League winner and international captain.
500+ top-flight appearances, won everything there is to win.
Speaks with the authority of someone who's been in those pressure moments.
Respects data but believes football is ultimately decided by heart, mentality, and moments of magic.
Quick to laugh, quicker to call out nonsense.""",
    background="""Won 4 league titles, 2 Champions Leagues, captained his country 40 times.
Known as a thinking defender - read the game better than anyone.
Post-retirement built a media career on honest, insightful punditry.
Still connected to dressing rooms and knows what players are really thinking.""",
    speaking_style="""Speaks from the gut but backs it up with tactical insight.
Uses vivid language and war stories from his playing days.
Not afraid to disagree loudly, but gives credit where it's due.
His passion is infectious - when he gets animated, everyone listens.
Affectionately dismissive of pure stats: "Marcus, you've never felt that pressure."
""",
    signature_phrases=[
        "Let me tell you from experience",
        "You can't measure heart on a spreadsheet, Marcus",
        "I've been in that exact situation",
        "That's what separates the good from the great",
        "The mentality is everything",
        "When you've played at that level",
        "Trust me on this one",
    ],
    voice_settings=VoiceSettings(stability=0.35, similarity_boost=0.8, style=0.3),
)

# Default trio - Updated with new names
DEFAULT_CHARACTERS = [SARAH_HOST, MARCUS_ANALYST, RIO_LEGEND]

# Aliases for backwards compatibility
ALEX_HOST = SARAH_HOST  # Legacy alias
DAVID_LEGEND = RIO_LEGEND  # Legacy alias


def get_character_by_role(role: CharacterRole) -> Character:
    """Get default character by role."""
    mapping = {
        CharacterRole.HOST: ALEX_HOST,
        CharacterRole.ANALYST: MARCUS_ANALYST,
        CharacterRole.LEGEND: DAVID_LEGEND,
    }
    return mapping[role]


def get_all_voice_ids() -> dict[str, str]:
    """Get mapping of character names to voice IDs."""
    return {
        char.name.upper(): char.voice_id
        for char in DEFAULT_CHARACTERS
    }
