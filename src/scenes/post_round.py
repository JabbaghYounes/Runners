"""PostRound -- post-round summary screen scene."""
from __future__ import annotations

import pygame

from src.core.round_summary import RoundSummary
from src.scenes.game_scene import GameScene
from src.scenes.main_menu import MainMenu

try:
    from src.scenes.home_base_scene import HomeBaseScene
except ImportError:
    HomeBaseScene = type('HomeBaseScene', (), {})  # type: ignore[misc]

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
        summary: "RoundSummary | None" = None,
        blurred_bg: "pygame.Surface | None" = None,
        xp_system=None,
        currency=None,
        save_manager=None,
        scene_manager=None,
        asset_manager=None,
        audio_system=None,
        # Legacy positional args
        sm=None,
        settings=None,
        assets=None,
        extracted: bool = False,
        loot_items=None,
    ) -> None:
        # Support legacy positional constructor: PostRound(sm, settings, assets, ...)
        if sm is not None and summary is None:
            self._sm = sm
            self._settings = settings
            self._assets = assets
            self.summary = None
            self.focused_button_index = 0
            self.show_level_up = False
            self.total_loot_value = 0
            return

        self.summary = summary
        self.blurred_bg = blurred_bg
        self.xp_system = xp_system
        self.currency = currency
        self.save_manager = save_manager
        self.scene_manager = scene_manager
        self.asset_manager = asset_manager
        self.audio_system = audio_system

        # Commit progression (once)
        if xp_system and summary:
            xp_system.award(summary.xp_earned)
            summary.level_after = xp_system.level
        if currency and summary:
            currency.add(summary.money_earned)
        if save_manager:
            save_manager.save()

        # Play outcome SFX
        if audio_system and summary:
            audio_system.play_sfx(_SFX_BY_STATUS.get(summary.extraction_status, "extraction_fail"))

        # Derived display values
        self.focused_button_index: int = 0
        self.show_level_up: bool = (
            summary.level_after > summary.level_before if summary else False
        )
        self.total_loot_value: int = sum(
            item.monetary_value for item in (summary.extracted_items if summary else [])
        )

    # Scene interface

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
        if self.blurred_bg:
            surface.blit(self.blurred_bg, (0, 0))
        font = pygame.font.Font(None, 36)
        if self.summary:
            label = self.summary.extraction_status.upper()
        else:
            label = "ROUND ENDED"
        img = font.render(label, True, (255, 255, 255))
        surface.blit(img, (100, 100))

    # Private helpers

    def _activate_button(self, index: int) -> None:
        sm = self.scene_manager or getattr(self, '_sm', None)
        if sm is None:
            return

        if index == 0:
            sm.replace(GameScene())
        elif index == 1:
            sm.replace(HomeBaseScene())
        elif index == 2:
            sm.replace(MainMenu())
