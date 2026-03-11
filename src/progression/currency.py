class Currency:
    def __init__(self, initial: int = 0):
        self.balance: int = initial

    def add(self, amount: int) -> None:
        self.balance += amount

    def spend(self, amount: int) -> bool:
        if self.balance >= amount:
            self.balance -= amount
            return True
        return False

    def formatted(self) -> str:
        return f"${self.balance:,}"

    def load(self, data: dict) -> None:
        self.balance = data.get('balance', 0)

    def to_save_dict(self) -> dict:
        return {'balance': self.balance}
