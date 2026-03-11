"""Player entity."""
from __future__ import annotations
from typing import TYPE_CHECKING

from src.core import event_bus as _event_bus_module
from src.entities.entity import Entity
from src.inventory.inventory import Inventory

if TYPE_CHECKING:
    from src.systems.buff_system import ActiveBuff, BuffSystem


class Player(Entity):
    """The human-controlled player entity."""

    def __init__(
        self,
        x: float,
        y: float,
        max_health: int = 100,
        buff_system: "BuffSystem | None" = None,
        inventory: Inventory | None = None,
    ) -> None:
        super().__init__(x, y, 32, 48)
        self.max_health: int = max_health
        self.health: int = max_health
        self.max_armor: int = 100
        self.armor: int = 0
        self.velocity_x: float = 0.0
        self.velocity_y: float = 0.0
        self._buff_system: "BuffSystem | None" = buff_system
        self.inventory: Inventory = inventory or Inventory()

    def set_buff_system(self, buff_system: "BuffSystem") -> None:
        self._buff_system = buff_system

    def heal(self, amount: int) -> None:
        before = self.health
        self.health = min(self.max_health, self.health + max(0, amount))
        gained = self.health - before
        if gained:
            _event_bus_module.event_bus.emit('player_healed', player=self, amount=gained)

    def take_damage(self, amount: int) -> None:
        effective = max(0, amount - self.armor // 10)
        self.health = max(0, self.health - effective)
        _event_bus_module.event_bus.emit('player_damaged', player=self, amount=effective)
        if self.health <= 0:
            self.alive = False
            _event_bus_module.event_bus.emit('player_killed', victim=self)

    def apply_buff(self, buff: "ActiveBuff") -> None:
        if self._buff_system:
            self._buff_system.add_buff(self, buff)

    def get_stat(self, name: str) -> float:
        """Return effective stat value after applying all active modifiers."""
        base: float = getattr(self, name, 0)
        if self._buff_system is None:
            return base
        modifiers = self._buff_system.get_modifiers(self, name)
        return base + sum(modifiers)

    def is_moving(self) -> bool:
        return self.velocity_x != 0.0 or self.velocity_y != 0.0

    def update(self, dt: float) -> None:
        self.x += self.velocity_x * dt
        self.y += self.velocity_y * dt
        # Sync rect
        if self._rect is not None:
            self._rect.x = int(self.x)
            self._rect.y = int(self.y)

    def render(self, surface: object, camera_offset: tuple[int, int] = (0, 0)) -> None:
        import pygame
        draw_rect = pygame.Rect(
            int(self.x) - camera_offset[0],
            int(self.y) - camera_offset[1],
            self.width,
            self.height,
        )
        pygame.draw.rect(surface, (0, 200, 255), draw_rect)
