"""RoundSummary dataclass — carries all post-round statistics."""
from dataclasses import dataclass, field

_VALID_STATUSES = frozenset({"success", "timeout", "eliminated"})


@dataclass
class RoundSummary:
    extraction_status: str
    extracted_items: list
    xp_earned: int
    money_earned: int
    kills: int
    challenges_completed: int
    challenges_total: int
    level_before: int
    level_after: int = 0
    # Challenge bonus totals applied at PostRound
    challenge_bonus_xp: int = 0
    challenge_bonus_money: int = 0
    challenge_bonus_items: list = field(default_factory=list)

    def __post_init__(self):
        if self.extraction_status not in _VALID_STATUSES:
            raise ValueError(
                f"extraction_status must be one of {sorted(_VALID_STATUSES)!r}; "
                f"got {self.extraction_status!r}"
            )
