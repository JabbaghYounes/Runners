"""Currency — tracks the player's in-game money balance.

Design notes:
- Zero is the minimum balance; negative balances are not allowed.
- `spend` returns False (non-exception) for insufficient funds — callers check the bool.
"""


class Currency:
    def __init__(self, balance: int = 0) -> None:
        self.balance: int = max(0, int(balance))

    def add(self, amount: int) -> None:
        """Increase balance by *amount* (must be non-negative)."""
        if amount < 0:
            raise ValueError(f'Currency.add() requires a non-negative amount, got {amount}')
        self.balance += int(amount)

    def spend(self, amount: int) -> bool:
        """Deduct *amount* from balance.

        Returns:
            True if the spend succeeded; False if insufficient funds.
        """
        if amount < 0:
            raise ValueError(f'Currency.spend() requires a non-negative amount, got {amount}')
        if self.balance < amount:
            return False
        self.balance -= int(amount)
        return True

    def formatted(self) -> str:
        return f'${self.balance:,}'

    def __repr__(self) -> str:
        return f'Currency(balance={self.balance!r})'
