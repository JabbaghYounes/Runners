"""GameScene — in-round 60 FPS game loop.

This module wires together all consumables-feature subsystems:
- ``BuffSystem``  — ticked every frame; expires timed buffs.
- ``LootSystem``  — spawns loot on enemy death; handles E-key pickup.
- ``Inventory``   — player item storage + quick-slot use.
- ``Player``      — health, buffs, stat access.
- ``HUD``         — health bar, buff icon strip, quick-slot bar.

Number keys 1–4 trigger ``inventory.use_consumable(qs_idx, player)``.
E key is polled each frame for proximity loot pickup.

Full scene responsibilities (TileMap, PhysicsSystem, CombatSystem, etc.)
are to be added in subsequent implementation passes.
"""

from __future__ import annotations

import pygame

from src.entities.player import Player
from src.inventory.inventory import Inventory
from src.systems.buff_system import BuffSystem
from src.systems.loot_system import LootSystem
from src.ui.hud import HUD

# Keys 1-4 map to quick-slot indices 0-3.
_QUICK_SLOT_KEYS: dict[int, int] = {
    pygame.K_1: 0,
    pygame.K_2: 1,
    pygame.K_3: 2,
    pygame.K_4: 3,
}


class GameScene:
    """In-round game scene.

    Owns all mutable in-round state and coordinates subsystem updates.

    Lifecycle::

        scene = GameScene()
        while running:
            scene.handle_events(pygame.event.get())
            scene.update(dt)
            scene.render(screen)
        scene.teardown()
    """

    def __init__(self) -> None:
        # --- Systems ---
        self.buff_system  = BuffSystem()
        self.loot_system  = LootSystem()

        # --- Inventory + Player ---
        self.inventory = Inventory()
        self.player = Player(
            x=400.0,
            y=300.0,
            max_health=100,
            buff_system=self.buff_system,
            inventory=self.inventory,
        )

        # --- HUD ---
        self.hud = HUD()

        # Currently highlighted quick-slot (for HUD border highlight).
        self._active_qs: int | None = None

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        """Route Pygame events to subsystems."""
        for event in events:
            if event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)

    def _handle_keydown(self, key: int) -> None:
        """Number keys 1–4 → use the consumable in the matching quick-slot."""
        if key in _QUICK_SLOT_KEYS:
            qs_idx = _QUICK_SLOT_KEYS[key]
            self._active_qs = qs_idx
            self.hud.set_active_quick_slot(qs_idx)
            # use_consumable returns False on empty slot — always safe to call.
            self.inventory.use_consumable(qs_idx, self.player)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Advance all subsystems by *dt* seconds."""
        e_pressed = bool(pygame.key.get_pressed()[pygame.K_e])

        self.player.update(dt)
        self.buff_system.update(dt)
        self.loot_system.update(self.player, e_pressed)

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self, screen: pygame.Surface) -> None:
        """Render the world then the HUD overlay.

        TileMap, entity sprites, etc. are rendered here in the full
        implementation.  For now only the HUD is drawn.
        """
        self.hud.render(screen, self.player)

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    def teardown(self) -> None:
        """Release resources and unsubscribe event handlers."""
        self.hud.teardown()
        self.loot_system.teardown()
        self.buff_system.remove_entity(self.player)
