"""Entity base class shared by Player, Enemy, Projectile, LootDrop."""

from __future__ import annotations

import pygame


class Entity(pygame.sprite.Sprite):
    """Base game entity.  Subclasses override ``update`` and ``draw``.

    Attributes:
        pos: World-space centre position.
        velocity: Current movement vector (pixels/second).
        health / max_health: Hit-point pool.
        alive: ``False`` once health reaches zero.
        facing_direction: Normalised direction the entity is facing.
        width / height: Dimensions for AABB collision rect.
    """

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        health: int = 100,
        width: int = 32,
        height: int = 32,
    ) -> None:
        super().__init__()
        self.pos = pygame.math.Vector2(x, y)
        self.velocity = pygame.math.Vector2(0, 0)
        self.health = health
        self.max_health = health
        self.alive = True
        self.facing_direction = pygame.math.Vector2(1, 0)
        self.width = width
        self.height = height
        # Pygame Sprite requires an image and rect; supply defaults.
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(int(x), int(y)))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_rect(self) -> pygame.Rect:
        """Return an AABB centred on ``self.pos``."""
        return pygame.Rect(
            int(self.pos.x - self.width // 2),
            int(self.pos.y - self.height // 2),
            self.width,
            self.height,
        )

    def take_damage(self, amount: int, source: Entity | None = None) -> int:
        """Reduce health by *amount*.  Returns actual damage dealt."""
        if not self.alive:
            return 0
        actual = min(amount, self.health)
        self.health -= actual
        if self.health <= 0:
            self.health = 0
            self.alive = False
        return actual

    def update(self, dt: float, **kwargs) -> None:  # noqa: D401
        """Override in subclass.  *dt* is seconds since last frame."""

    def draw(self, surface: pygame.Surface, camera) -> None:
        """Override in subclass to render the entity."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _sync_rect(self) -> None:
        """Keep ``self.rect`` in sync with ``self.pos``."""
        self.rect.center = (int(self.pos.x), int(self.pos.y))


def resolve_tilemap_collision(
    entity: Entity,
    tilemap,
    dx: float,
    dy: float,
) -> tuple[float, float]:
    """Move *entity* by (*dx*, *dy*) resolving per-axis AABB vs. tilemap.

    Returns the final resolved (dx, dy) after removing motion that would
    overlap solid tiles.
    """
    tile_size = tilemap.tile_size

    # --- X axis ---
    entity.pos.x += dx
    entity_rect = entity.get_rect()
    resolved_dx = dx
    for ty in range(_grid(entity_rect.top, tile_size), _grid(entity_rect.bottom - 1, tile_size) + 1):
        for tx in range(_grid(entity_rect.left, tile_size), _grid(entity_rect.right - 1, tile_size) + 1):
            if tilemap.is_solid(tx, ty):
                tile_rect = pygame.Rect(tx * tile_size, ty * tile_size, tile_size, tile_size)
                if entity_rect.colliderect(tile_rect):
                    if dx > 0:
                        entity.pos.x = tile_rect.left - entity.width / 2
                    elif dx < 0:
                        entity.pos.x = tile_rect.right + entity.width / 2
                    resolved_dx = 0
                    entity_rect = entity.get_rect()

    # --- Y axis ---
    entity.pos.y += dy
    entity_rect = entity.get_rect()
    resolved_dy = dy
    for ty in range(_grid(entity_rect.top, tile_size), _grid(entity_rect.bottom - 1, tile_size) + 1):
        for tx in range(_grid(entity_rect.left, tile_size), _grid(entity_rect.right - 1, tile_size) + 1):
            if tilemap.is_solid(tx, ty):
                tile_rect = pygame.Rect(tx * tile_size, ty * tile_size, tile_size, tile_size)
                if entity_rect.colliderect(tile_rect):
                    if dy > 0:
                        entity.pos.y = tile_rect.top - entity.height / 2
                    elif dy < 0:
                        entity.pos.y = tile_rect.bottom + entity.height / 2
                    resolved_dy = 0
                    entity_rect = entity.get_rect()

    entity._sync_rect()
    return resolved_dx, resolved_dy


def _grid(pixel: float, tile_size: int) -> int:
    """Convert a pixel coordinate to a tile-grid index."""
    return int(pixel) // tile_size
