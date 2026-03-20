"""Home Base scene — facility cards + skill tree tab, QUEUE FOR ROUND."""
from __future__ import annotations

import pygame
from typing import List, Any, Optional

from src.scenes.base_scene import BaseScene
from src.ui.widgets import Button, Panel, Label
from src.ui.skill_tree_screen import SkillTreeScreen
from src.constants import (
    SCREEN_W, SCREEN_H, BG_MID, ACCENT_CYAN, ACCENT_GREEN,
    TEXT_BRIGHT, TEXT_DIM, PANEL_BG, BORDER_DIM, BORDER_BRIGHT,
)

# Content area rect — used in both render() and handle_events()
_CONTENT_RECT = pygame.Rect(40, 160, SCREEN_W - 80, SCREEN_H - 280)


class HomeBaseScene(BaseScene):
    TAB_HOME  = 0
    TAB_SKILL = 1

    def __init__(self, sm: Any, settings: Any, assets: Any,
                 home_base: Any, skill_tree: Any, currency: Any,
                 xp_system: Any):
        self._sm         = sm
        self._settings   = settings
        self._assets     = assets
        self._home_base  = home_base
        self._skill_tree = skill_tree
        self._currency   = currency
        self._xp_system  = xp_system
        self._tab        = self.TAB_HOME
        self._font: Optional[pygame.font.Font] = None

        # Skill tree widget — drives the SKILL TREE tab content
        self._skill_tree_screen = SkillTreeScreen(skill_tree, xp_system)

        bw, bh = 220, 48
        cx = SCREEN_W // 2

        self._tab_buttons: List[Button] = [
            Button(pygame.Rect(cx - 240, 60, 220, 40), "HOME BASE", "primary",
                   on_click=lambda: setattr(self, "_tab", self.TAB_HOME)),
            Button(pygame.Rect(cx + 20,  60, 220, 40), "SKILL TREE", "secondary",
                   on_click=lambda: setattr(self, "_tab", self.TAB_SKILL)),
        ]

        self._queue_btn = Button(
            pygame.Rect(cx - bw // 2, SCREEN_H - 80, bw, bh),
            "QUEUE FOR ROUND", "primary",
            on_click=self._queue_round,
        )
        self._back_btn = Button(
            pygame.Rect(20, SCREEN_H - 60, 140, 40),
            "BACK", "ghost",
            on_click=self._back,
        )

    # ------------------------------------------------------------------
    # Scene transitions
    # ------------------------------------------------------------------

    def _queue_round(self) -> None:
        from src.scenes.game_scene import GameScene
        from src.core.event_bus import EventBus
        eb = EventBus()
        self._sm.replace(GameScene(
            self._sm, self._settings, self._assets, eb,
            self._xp_system, self._currency, self._home_base,
            skill_tree=self._skill_tree,
        ))

    def _back(self) -> None:
        from src.scenes.main_menu import MainMenu
        self._sm.replace(MainMenu(self._sm, self._settings, self._assets))

    # ------------------------------------------------------------------
    # BaseScene interface
    # ------------------------------------------------------------------

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        for event in events:
            for btn in self._tab_buttons:
                btn.handle_event(event)
            self._queue_btn.handle_event(event)
            self._back_btn.handle_event(event)

            # Forward events to the skill tree widget when its tab is active
            if self._tab == self.TAB_SKILL:
                self._skill_tree_screen.handle_event(event, _CONTENT_RECT)

    def update(self, dt: float) -> None:
        pass

    def render(self, screen: pygame.Surface) -> None:
        if self._font is None:
            self._font = pygame.font.Font(None, 22)
        font_sm = pygame.font.Font(None, 18)

        screen.fill(BG_MID)

        # Title
        title_font = pygame.font.Font(None, 40)
        title = title_font.render("HOME BASE", True, ACCENT_CYAN)
        screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 14))

        # Currency + level + SP balance
        sp = getattr(self._xp_system, "skill_points", 0)
        info = self._font.render(
            f"{self._currency.formatted()}  |  Level {self._xp_system.level}"
            f"  |  SP: {sp}",
            True, ACCENT_GREEN,
        )
        screen.blit(info, (SCREEN_W // 2 - info.get_width() // 2, 110))

        # Tab buttons
        for btn in self._tab_buttons:
            btn.draw(screen)

        # Content panel
        pygame.draw.rect(screen, PANEL_BG, _CONTENT_RECT, border_radius=6)
        pygame.draw.rect(screen, BORDER_DIM, _CONTENT_RECT, 1, border_radius=6)

        if self._tab == self.TAB_HOME:
            self._draw_facilities(screen, _CONTENT_RECT, font_sm)
        else:
            self._skill_tree_screen.render(screen, _CONTENT_RECT)

        self._queue_btn.draw(screen)
        self._back_btn.draw(screen)

    # ------------------------------------------------------------------
    # Facilities tab
    # ------------------------------------------------------------------

    def _draw_facilities(self, screen: pygame.Surface,
                         area: pygame.Rect,
                         font: pygame.font.Font) -> None:
        facilities = self._home_base.get_facilities()
        card_w, card_h = 240, 100
        gap       = 20
        total_w   = len(facilities) * card_w + (len(facilities) - 1) * gap
        start_x   = area.x + (area.w - total_w) // 2
        cy        = area.y + (area.h - card_h) // 2

        for i, fac in enumerate(facilities):
            cx   = start_x + i * (card_w + gap)
            card = pygame.Rect(cx, cy, card_w, card_h)
            pygame.draw.rect(screen, (20, 30, 50), card, border_radius=6)
            pygame.draw.rect(screen, BORDER_BRIGHT, card, 1, border_radius=6)

            name_s = font.render(fac["name"], True, (220, 235, 255))
            screen.blit(name_s, (cx + 10, cy + 10))

            lvl     = fac.get("level", 0)
            max_lvl = fac.get("max_level", 3)
            lvl_s   = font.render(f"Level {lvl}/{max_lvl}", True, ACCENT_CYAN)
            screen.blit(lvl_s, (cx + 10, cy + 34))

            costs = fac.get("upgrade_cost", [])
            if lvl < max_lvl and lvl < len(costs):
                cost_s = font.render(f"Upgrade: ${costs[lvl]:,}", True, ACCENT_GREEN)
                screen.blit(cost_s, (cx + 10, cy + 58))
            else:
                maxed_s = font.render("MAXED", True, ACCENT_GREEN)
                screen.blit(maxed_s, (cx + 10, cy + 58))
