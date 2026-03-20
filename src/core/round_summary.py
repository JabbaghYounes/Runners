"""RoundSummary dataclass — carries all post-round statistics."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.inventory.item import Item

_VALID_STATUSES = frozenset({"success", "timeout", "eliminated"})


@dataclass
class RoundSummary:
    extraction_status: str
    extracted_items: list[Item]
    xp_earned: int
    money_earned: int
    kills: int
    challenges_completed: int
    challenges_total: int
    level_before: int
    level_after: int = 0

    def __post_init__(self) -> None:
        if self.extraction_status not in _VALID_STATUSES:
            raise ValueError(
                f"extraction_status must be one of {sorted(_VALID_STATUSES)!r}; "
                f"got {self.extraction_status!r}"
            )

    @property
    def total_loot_value(self) -> int:
        """Sum of monetary_value across all extracted items."""
        return sum(
            int(getattr(item, "monetary_value", getattr(item, "value", 0)))
            for item in self.extracted_items
        )
