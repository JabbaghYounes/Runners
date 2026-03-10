"""Lightweight projectile entity: position, direction, speed, damage, owner."""

from __future__ import annotations

import pygame

from src.entities.base import Entity


class Projectile(Entity):
    """A projectile fired by a player or enemy.

    Attributes:
        direction: Normalised flight direction.
        speed: Pixels per second.
        damage: Hit-point damage on impact.
        owner: The entity that fired this projectile (used to avoid self-hits).
        max_range: Maximum distance before auto-destroy.
        _distance_travelled: Running total of pixels flown.
    """

    def __init__(
        self,
        x: float,
        y: float,
        direction: pygame.math.Vector2,
        speed: float = 600.0,
        damage: int = 10,
        owner: Entity | None = None,
        max_range: float = 800.0,
    ) -> None:
        super().__init__(x, y, health=1, width=8, height=8)
        self.direction = direction.normalize() if direction.length() > 0 else pygame.math.Vector2(1, 0)
        self.speed = speed
        self.damage = damage
        self.owner = owner
        self.max_range = max_range
        self._distance_travelled: float = 0.0

    def update(self, dt: float, tilemap=None, **kwargs) -> None:
        """Move along direction, check tilemap collision, check range limit."""
        if not self.alive:
            return

        move = self.direction * self.speed * dt
        self.pos += move
        self._distance_travelled += move.length()
        self._sync_rect()

        # Destroy on tilemap collision
        if tilemap is not None:
            gx = int(self.pos.x) // tilemap.tile_size
            gy = int(self.pos.y) // tilemap.tile_size
            if tilemap.is_solid(gx, gy):
                self.alive = False
                self.kill()
                return

        # Destroy at max range
        if self._distance_travelled >= self.max_range:
            self.alive = False
            self.kill()

    def draw(self, surface: pygame.Surface, camera) -> None:
        if not self.alive:
            return
        screen_pos = camera.world_to_screen(self.pos)
        pygame.draw.circle(
            surface,
            (255, 255, 0),
            (int(screen_pos.x), int(screen_pos.y)),
            4,
        )

    def check_hit(self, target: Entity) -> bool:
        """Return ``True`` if this projectile overlaps *target* and they are
        not the owner."""
        if not self.alive or target is self.owner:
            return False
        return self.get_rect().colliderect(target.get_rect())
