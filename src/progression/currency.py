"""Currency — tracks the player's in-game money balance.

Design notes:
- Zero Pygame dependency: pure Python, fully testable without a display.
- `add()` and `spend()` are the only mutation points; callers never touch
  `balance` directly.
- `spend()` returns False (no exception) when funds are insufficient so UI
  code can gate on the return value without a try/except.
"""


class Currency:
    """Tracks and mutates the player's money balance.

    Attributes:
        balance: Current money balance (always >= 0).
    """

    def __init__(self, balance: int = 0) -> None:
        """Initialise with an optional starting balance.

        Args:
            balance: Starting balance in whole units.  Clamped to 0 if
                     a negative value is passed (defensive).
        """
        self.balance: int = max(0, int(balance))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, amount: int) -> None:
        """Credit *amount* to the balance.

        Args:
            amount: Positive integer to add.  Must be >= 0.

        Raises:
            ValueError: If *amount* is negative.
        """
        if amount < 0:
            raise ValueError(f"Currency.add() requires a non-negative amount, got {amount}")
        self.balance += amount

    def spend(self, amount: int) -> bool:
        """Debit *amount* from the balance if funds are sufficient.

        Does **not** raise on insufficient funds — callers check the return
        value and decide how to respond (e.g. play a 'can't afford' sound,
        disable the button, etc.).

        Args:
            amount: Positive integer to deduct.  Must be >= 0.

        Returns:
            True if the deduction succeeded (balance >= amount).
            False if funds were insufficient; balance is **not** mutated.

        Raises:
            ValueError: If *amount* is negative.
        """
        if amount < 0:
            raise ValueError(f"Currency.spend() requires a non-negative amount, got {amount}")
        if self.balance < amount:
            return False
        self.balance -= amount
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def formatted(self) -> str:
        """Return the balance as a human-readable dollar string, e.g. '$3,200'."""
        return f"${self.balance:,}"

    def __repr__(self) -> str:
        return f"Currency(balance={self.balance})"
