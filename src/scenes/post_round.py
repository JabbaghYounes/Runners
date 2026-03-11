"""PostRound — post-round summary screen scene."""
from __future__ import annotations

import pygame

from src.core.round_summary import RoundSummary
from src.scenes.game_scene import GameScene
from src.scenes.home_base_scene import HomeBaseScene
from src.scenes.main_menu import MainMenu

_SFX_BY_STATUS: dict[str, str] = {
    "success": "extraction_success",
    "timeout": "extraction_fail",
    "eliminated": "extraction_fail",
}

_NUM_BUTTONS = 3


class PostRound:
    """Displays round statistics and lets the player choose what to do next.

    Progression (XP award, currency credit, save) is committed exactly once
    inside ``__init__``; subsequent ``update`` calls do not re-apply it.
    """

    def __init__(
        self,
        summary: RoundSummary,
        blurred_bg: pygame.Surface,
        xp_system,
        currency,
        save_manager,
        scene_manager,
        asset_manager,
        audio_system,
    ) -> None:
        self.summary = summary
        self.blurred_bg = blurred_bg
        self.xp_system = xp_system
        self.currency = currency
        self.save_manager = save_manager
        self.scene_manager = scene_manager
        self.asset_manager = asset_manager
        self.audio_system = audio_system

        # ── Commit progression (once) ────────────────────────────────────────
        xp_system.award(summary.xp_earned)
        summary.level_after = xp_system.level
        currency.add(summary.money_earned)
        save_manager.save()

        # ── Play outcome SFX ─────────────────────────────────────────────────
        audio_system.play_sfx(_SFX_BY_STATUS[summary.extraction_status])

        # ── Derived display values ───────────────────────────────────────────
        self.focused_button_index: int = 0
        self.show_level_up: bool = summary.level_after > summary.level_before
        self.total_loot_value: int = sum(
            item.monetary_value for item in summary.extracted_items
        )

    # ── Scene interface ──────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        """Advance widget animations."""

    def handle_events(self, events) -> None:
        """Route keyboard input to focus management and button activation."""
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if event.key == pygame.K_DOWN:
                self.focused_button_index = (
                    self.focused_button_index + 1
                ) % _NUM_BUTTONS
            elif event.key == pygame.K_UP:
                self.focused_button_index = (
                    self.focused_button_index - 1
                ) % _NUM_BUTTONS
            elif event.key == pygame.K_RETURN:
                self._activate_button(self.focused_button_index)

    def render(self, surface: pygame.Surface) -> None:
        """Draw the post-round screen onto *surface*."""
        surface.blit(self.blurred_bg, (0, 0))
        font = pygame.font.Font(None, 36)
        label = self.summary.extraction_status.upper()
        img = font.render(label, True, (255, 255, 255))
        surface.blit(img, (100, 100))

    # ── Private helpers ──────────────────────────────────────────────────────

    def _activate_button(self, index: int) -> None:
        if index == 0:
            self.scene_manager.replace(GameScene())
        elif index == 1:
            self.scene_manager.replace(HomeBaseScene())
        elif index == 2:
            self.scene_manager.replace(MainMenu())
