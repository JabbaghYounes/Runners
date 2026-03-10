"""Game over scene — displayed when a round ends in failure."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    pass

# Colours
BG_DARK = (10, 14, 23)            # #0A0E17
ACCENT_RED = (255, 23, 68)        # #FF1744
ACCENT_GREEN = (105, 240, 174)    # #69F0AE
TEXT_PRIMARY = (224, 224, 224)     # #E0E0E0
TEXT_SECONDARY = (158, 158, 158)  # #9E9E9E
PANEL_BG = (18, 24, 38)

# Cause display text
CAUSE_TEXT = {
    "eliminated": "You were eliminated",
    "timeout": "Time expired",
}


class GameOverScene:
    """Failure screen with cause, lost loot, retained XP, and navigation buttons.

    Parameters:
        game: The Game instance (provides ``replace_scene``).
        result_data: Dict from RoundManager containing cause, loot_lost,
            xp_retained.
    """

    # Letter-by-letter typing speed (seconds per character)
    TYPE_SPEED = 0.04

    def __init__(self, game, result_data: dict) -> None:
        self.game = game
        self.result_data = result_data

        self.cause: str = result_data.get("cause", "eliminated")
        self.loot_lost: list[dict] = result_data.get("loot_lost", [])
        self.total_lost: int = result_data.get("total_lost", 0)
        self.xp_retained: int = result_data.get("xp_retained", 0)

        # Animation state
        self._elapsed = 0.0
        self._fade_alpha = 255  # fade-in from black

        # Cause text letter-by-letter animation
        self._cause_text = CAUSE_TEXT.get(self.cause, "Mission failed")
        self._cause_chars_shown = 0

        # Button rects (created during draw)
        self._btn_retry_rect: pygame.Rect | None = None
        self._btn_home_rect: pygame.Rect | None = None
        self._btn_menu_rect: pygame.Rect | None = None

        # Fonts (lazy init)
        self._fonts_initialized = False
        self._font_heading: pygame.font.Font | None = None
        self._font_body: pygame.font.Font | None = None
        self._font_number: pygame.font.Font | None = None
        self._font_button: pygame.font.Font | None = None

    def _init_fonts(self) -> None:
        if self._fonts_initialized:
            return
        self._fonts_initialized = True
        self._font_heading = pygame.font.SysFont("monospace", 36, bold=True)
        self._font_body = pygame.font.SysFont("monospace", 16)
        self._font_number = pygame.font.SysFont("monospace", 20, bold=True)
        self._font_button = pygame.font.SysFont("monospace", 18, bold=True)

    # ------------------------------------------------------------------
    # Scene interface
    # ------------------------------------------------------------------

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self._btn_retry_rect and self._btn_retry_rect.collidepoint(event.pos):
                    self._on_retry()
                elif self._btn_home_rect and self._btn_home_rect.collidepoint(event.pos):
                    self._on_home()
                elif self._btn_menu_rect and self._btn_menu_rect.collidepoint(event.pos):
                    self._on_menu()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    self._on_retry()
                elif event.key == pygame.K_RETURN:
                    self._on_menu()

    def update(self, dt: float) -> None:
        self._elapsed += dt

        # Fade-in from black
        if self._fade_alpha > 0:
            self._fade_alpha = max(0, self._fade_alpha - int(300 * dt))

        # Letter-by-letter cause text
        chars_target = int(self._elapsed / self.TYPE_SPEED)
        self._cause_chars_shown = min(chars_target, len(self._cause_text))

    def draw(self, surface: pygame.Surface) -> None:
        self._init_fonts()
        surface.fill(BG_DARK)

        sw, sh = surface.get_size()

        # --- Header: "MISSION FAILED" ---
        header = self._font_heading.render("MISSION FAILED", True, ACCENT_RED)
        surface.blit(header, (sw // 2 - header.get_width() // 2, 50))

        # --- Cause text (letter-by-letter) ---
        visible_text = self._cause_text[: self._cause_chars_shown]
        cause_surface = self._font_number.render(visible_text, True, TEXT_PRIMARY)
        surface.blit(cause_surface, (sw // 2 - cause_surface.get_width() // 2, 110))

        # --- Loot lost panel ---
        self._draw_loot_lost(surface, sw, sh)

        # --- XP retained ---
        xp_text = self._font_number.render(
            f"XP Retained: +{self.xp_retained}", True, ACCENT_GREEN
        )
        surface.blit(xp_text, (sw // 2 - xp_text.get_width() // 2, sh - 180))

        # --- Buttons ---
        self._draw_buttons(surface, sw, sh)

        # Fade overlay
        if self._fade_alpha > 0:
            fade_surface = pygame.Surface((sw, sh), pygame.SRCALPHA)
            fade_surface.fill((0, 0, 0, self._fade_alpha))
            surface.blit(fade_surface, (0, 0))

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------

    def _draw_loot_lost(self, surface: pygame.Surface, sw: int, sh: int) -> None:
        panel_w = sw - 160
        panel_h = sh - 360
        panel_x = 80
        panel_y = 160

        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        pygame.draw.rect(surface, PANEL_BG, panel_rect, border_radius=4)
        pygame.draw.rect(surface, ACCENT_RED, panel_rect, width=1, border_radius=4)

        header = self._font_number.render("LOOT LOST", True, ACCENT_RED)
        surface.blit(header, (panel_x + 16, panel_y + 12))

        y_offset = panel_y + 44
        for item in self.loot_lost:
            if y_offset > panel_y + panel_h - 24:
                break
            name = item.get("name", "Unknown")
            value = item.get("value", 0)
            name_s = self._font_body.render(f"  {name}", True, TEXT_SECONDARY)
            value_s = self._font_body.render(f"-${value}", True, ACCENT_RED)
            surface.blit(name_s, (panel_x + 16, y_offset))
            surface.blit(
                value_s,
                (panel_x + panel_w - value_s.get_width() - 16, y_offset),
            )
            y_offset += 24

        if not self.loot_lost:
            empty = self._font_body.render("  No items were lost", True, TEXT_SECONDARY)
            surface.blit(empty, (panel_x + 16, y_offset))

        # Total lost
        total_text = self._font_number.render(
            f"Total Lost: ${self.total_lost}", True, ACCENT_RED
        )
        surface.blit(
            total_text,
            (panel_x + panel_w - total_text.get_width() - 16, panel_y + panel_h - 32),
        )

    def _draw_buttons(self, surface: pygame.Surface, sw: int, sh: int) -> None:
        btn_w, btn_h = 180, 44
        gap = 24
        total_w = btn_w * 3 + gap * 2
        start_x = sw // 2 - total_w // 2
        btn_y = sh - 80

        buttons = [
            ("TRY AGAIN", ACCENT_RED, "retry"),
            ("HOME BASE", ACCENT_GREEN, "home"),
            ("MAIN MENU", TEXT_PRIMARY, "menu"),
        ]

        for i, (label, color, key) in enumerate(buttons):
            x = start_x + i * (btn_w + gap)
            rect = pygame.Rect(x, btn_y, btn_w, btn_h)
            pygame.draw.rect(surface, color, rect, width=2, border_radius=6)
            text = self._font_button.render(label, True, color)
            surface.blit(
                text,
                (x + btn_w // 2 - text.get_width() // 2, btn_y + 12),
            )
            if key == "retry":
                self._btn_retry_rect = rect
            elif key == "home":
                self._btn_home_rect = rect
            elif key == "menu":
                self._btn_menu_rect = rect

    # ------------------------------------------------------------------
    # Button actions
    # ------------------------------------------------------------------

    def _on_retry(self) -> None:
        """Start a new gameplay round."""
        try:
            from src.scenes.gameplay import GameplayScene
            self.game.replace_scene(GameplayScene(self.game))
        except (ImportError, AttributeError):
            pass

    def _on_home(self) -> None:
        """Go to home base."""
        try:
            from src.scenes.home_base_scene import HomeBaseScene
            self.game.replace_scene(HomeBaseScene(self.game))
        except (ImportError, AttributeError):
            self._on_menu()

    def _on_menu(self) -> None:
        """Return to main menu."""
        try:
            from src.scenes.main_menu import MainMenuScene
            self.game.replace_scene(MainMenuScene(self.game))
        except (ImportError, AttributeError):
            pass
