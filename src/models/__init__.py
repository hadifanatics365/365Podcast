"""Data models for the podcast generation service."""

from .enums import ContentMode, GameStatus, SportType
from .game import (
    BetLine,
    BetLineOption,
    Competitor,
    Event,
    Game,
    LineUp,
    Player,
    ScoresData,
    Statistic,
)
from .requests import PodcastFormat, PodcastMode, PodcastRequest
from .responses import PodcastResponse, PodcastStatusResponse
from .characters import (
    Character,
    CharacterRole,
    DEFAULT_CHARACTERS,
    ALEX_HOST,
    MARCUS_ANALYST,
    DAVID_LEGEND,
    get_all_voice_ids,
)

__all__ = [
    # Enums
    "ContentMode",
    "GameStatus",
    "SportType",
    "PodcastMode",
    "PodcastFormat",
    # Game models
    "Game",
    "Competitor",
    "Event",
    "Statistic",
    "LineUp",
    "Player",
    "BetLine",
    "BetLineOption",
    "ScoresData",
    # Request/Response
    "PodcastRequest",
    "PodcastResponse",
    "PodcastStatusResponse",
    # Characters
    "Character",
    "CharacterRole",
    "DEFAULT_CHARACTERS",
    "ALEX_HOST",
    "MARCUS_ANALYST",
    "DAVID_LEGEND",
    "get_all_voice_ids",
]
