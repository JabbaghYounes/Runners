"""RoundSummary dataclass — carries all post-round statistics."""
from dataclasses import dataclass

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

    def __post_init__(self):
        if self.extraction_status not in _VALID_STATUSES:
            raise ValueError(
                f"extraction_status must be one of {sorted(_VALID_STATUSES)!r}; "
                f"got {self.extraction_status!r}"
            )
