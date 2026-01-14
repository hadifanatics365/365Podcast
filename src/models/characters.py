"""Character profiles for multi-voice podcast generation."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CharacterRole(str, Enum):
    """Character roles in the podcast."""
    HOST = "host"
    ANALYST = "analyst"
    LEGEND = "legend"


@dataclass
class Character:
    """A podcast character with voice and personality."""

    name: str
    role: CharacterRole
    voice_id: str
    description: str
    voice_style: str
    signature_phrases: list[str]

    def get_voice_direction(self) -> str:
        """Get voice direction for script generation."""
        return f"{self.name} ({self.role.value}): {self.voice_style}"


# The Trio - Default Characters
ALEX_HOST = Character(
    name="Alex",
    role=CharacterRole.HOST,
    voice_id="TxGEqnHWrfWFTfGW9XjX",  # Josh - energetic, clear
    description="The Conductor - bridges the audience and experts",
    voice_style="High energy, clear articulation, charismatic, fast-talking",
    signature_phrases=[
        "Break it down for us",
        "Let's talk numbers for a second",
        "What do you make of that?",
        "Take us through it",
        "That's a bold claim!",
        "Welcome back to 365Scores",
    ]
)

MARCUS_ANALYST = Character(
    name="Marcus",
    role=CharacterRole.ANALYST,
    voice_id="pNInz6obpgDQGcFmaJgB",  # Adam - calm, measured, deep
    description="The Human Algorithm - provides objective truth through data",
    voice_style="Calm, measured, direct, logical, concise",
    signature_phrases=[
        "The data suggests",
        "If you look at the numbers",
        "Statistically speaking",
        "The xG tells us",
        "Looking at the heat map",
        "The pass completion rate shows",
        "From an analytical standpoint",
    ]
)

DAVID_LEGEND = Character(
    name="David",
    role=CharacterRole.LEGEND,
    voice_id="VR6AewLTigWG4xSOukaG",  # Arnold - deep, gravelly, confident
    description="The Icon - former world-class player, emotional and tactical heart",
    voice_style="Deep, gravelly, confident, passionate, speaks from experience",
    signature_phrases=[
        "When I was on that pitch",
        "You can't measure heart with a spreadsheet",
        "I've been in that situation",
        "Let me tell you something",
        "That's what separates the good from the great",
        "In my day",
        "The mentality is everything",
    ]
)

# Default trio
DEFAULT_CHARACTERS = [ALEX_HOST, MARCUS_ANALYST, DAVID_LEGEND]


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
