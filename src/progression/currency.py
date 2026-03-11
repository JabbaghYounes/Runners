"""Currency -- tracks the player's in-game money balance."""


class Currency:
    """Tracks and mutates the player's money balance."""

    def __init__(self, balance: int = 0, initial: int = 0) -> None:
        # Support both Currency(balance=500) and Currency(initial=500)
        start = balance if balance != 0 else initial
        self.balance: int = max(0, int(start))

    def add(self, amount: int) -> None:
        if amount < 0:
            raise ValueError(f"Currency.add() requires a non-negative amount, got {amount}")
        self.balance += amount

    def spend(self, amount: int) -> bool:
        if amount < 0:
            raise ValueError(f"Currency.spend() requires a non-negative amount, got {amount}")
        if self.balance < amount:
            return False
        self.balance -= amount
        return True

    def formatted(self) -> str:
        return f"${self.balance:,}"

    def load(self, data: dict) -> None:
        self.balance = data.get('balance', 0)

    def to_save_dict(self) -> dict:
        return {'balance': self.balance}

    def __repr__(self) -> str:
        return f"Currency(balance={self.balance})"
