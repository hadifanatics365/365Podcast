"""Enumerations for the podcast generation service."""

from enum import IntEnum, Enum


class GameStatus(IntEnum):
    """Game status values mapped from iOS Game.swift."""

    DIDNT_START = 0
    FINISHED = 1
    ACTIVE = 2
    SHOW_STATUS = 3
    JUST_ENDED = 163
    INVALID = 999

    @classmethod
    def is_finished(cls, status: int) -> bool:
        """Check if game is finished or just ended."""
        # Status 99 and other high values (90-200) often indicate finished games in some API versions
        if status == 99 or (status >= 90 and status < 200):
            return True
        return status in (cls.FINISHED, cls.JUST_ENDED)

    @classmethod
    def is_upcoming(cls, status: int) -> bool:
        """Check if game hasn't started yet."""
        # Status 0 = didntStart, status -1 or other negative = postponed/not started
        return status <= cls.DIDNT_START

    @classmethod
    def is_live(cls, status: int) -> bool:
        """Check if game is currently active."""
        return status == cls.ACTIVE


class SportType(IntEnum):
    """Sport type IDs from 365Scores."""

    FOOTBALL = 1
    BASKETBALL = 2
    TENNIS = 3
    AMERICAN_FOOTBALL = 4
    BASEBALL = 5
    ICE_HOCKEY = 6
    VOLLEYBALL = 7
    HANDBALL = 8
    RUGBY = 9
    CRICKET = 10
    GOLF = 11
    MOTORSPORT = 12
    MMA = 13
    BOXING = 14
    CYCLING = 15
    ESPORTS = 16


class ContentMode(str, Enum):
    """Content generation mode based on game selection."""

    DAILY_RECAP = "daily_recap"
    GAME_SPOTLIGHT_PREGAME = "game_spotlight_pregame"
    GAME_SPOTLIGHT_POSTGAME = "game_spotlight_postgame"
    PANEL_DISCUSSION = "panel_discussion"


class BetType(IntEnum):
    """Betting line types from iOS BetsType."""

    BET_1X2 = 1
    LEAD = 2
    UNDER_OVER = 3
    OTHER = 4
    BET_1X2_FIRST_HALF = 5
    UNDER_OVER_FIRST_HALF = 6
    SPREAD = 7
    MONEY_LINE = 8
    TOTAL = 9


class EventType(IntEnum):
    """Game event types (goals, cards, etc.)."""

    GOAL = 1
    YELLOW_CARD = 2
    RED_CARD = 3
    SUBSTITUTION = 4
    PENALTY_SCORED = 5
    PENALTY_MISSED = 6
    OWN_GOAL = 7
    ASSIST = 8
    VAR = 9
