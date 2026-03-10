"""Extraction summary scene — displayed after a successful extraction."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    pass

# Colours
BG_DARK = (10, 14, 23)            # #0A0E17
ACCENT_CYAN = (0, 229, 255)       # #00E5FF
ACCENT_GREEN = (105, 240, 174)    # #69F0AE
ACCENT_GOLD = (255, 215, 64)      # #FFD740
TEXT_PRIMARY = (224, 224, 224)     # #E0E0E0
TEXT_SECONDARY = (158, 158, 158)  # #9E9E9E
PANEL_BG = (18, 24, 38)           # slightly lighter than BG_DARK


class ExtractionSummaryScene:
    """Post-extraction loot/XP/money summary with staggered animations.

    Parameters:
        game: The Game instance (provides ``replace_scene``).
        result_data: Dict from RoundManager containing items, total_value,
            xp_earned, money_gained, level_before, level_after.
    """

    # Stagger delay between section reveals (seconds)
    SECTION_DELAY = 0.3
    # Number count-up duration (seconds)
    COUNT_UP_DURATION = 0.5

    def __init__(self, game, result_data: dict) -> None:
        self.game = game
        self.result_data = result_data

        # Unpack result data with safe defaults
        self.items: list[dict] = result_data.get("items", [])
        self.total_value: int = result_data.get("total_value", 0)
        self.xp_earned: dict = result_data.get("xp_earned", {})
        self.money_gained: int = result_data.get("money_gained", 0)
        self.level_before: int = result_data.get("level_before", 1)
        self.level_after: int = result_data.get("level_after", 1)

        # Animation state
        self._elapsed = 0.0
        self._continue_pressed = False

        # Fonts (created lazily to avoid Pygame init issues in tests)
        self._fonts_initialized = False
        self._font_heading: pygame.font.Font | None = None
        self._font_body: pygame.font.Font | None = None
        self._font_number: pygame.font.Font | None = None
        self._font_button: pygame.font.Font | None = None

    # ------------------------------------------------------------------
    # Font initialization
    # ------------------------------------------------------------------

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
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                    self._continue_pressed = True
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Check continue button click
                if self._continue_btn_rect and self._continue_btn_rect.collidepoint(event.pos):
                    self._continue_pressed = True

    def update(self, dt: float) -> None:
        self._elapsed += dt

        if self._continue_pressed:
            self._transition_next()

    def draw(self, surface: pygame.Surface) -> None:
        self._init_fonts()
        surface.fill(BG_DARK)

        sw, sh = surface.get_size()

        # --- Header: "EXTRACTION SUCCESSFUL" ---
        if self._section_visible(0):
            header_text = self._font_heading.render(
                "EXTRACTION SUCCESSFUL", True, ACCENT_CYAN
            )
            surface.blit(header_text, (sw // 2 - header_text.get_width() // 2, 40))

        # --- Left panel: Loot list ---
        if self._section_visible(1):
            self._draw_loot_panel(surface, sw, sh)

        # --- Right panel: Rewards breakdown ---
        if self._section_visible(2):
            self._draw_rewards_panel(surface, sw, sh)

        # --- Bottom: XP bar + Level-up + Continue ---
        if self._section_visible(3):
            self._draw_bottom_section(surface, sw, sh)

    # ------------------------------------------------------------------
    # Section visibility (staggered reveal)
    # ------------------------------------------------------------------

    def _section_visible(self, index: int) -> bool:
        return self._elapsed >= index * self.SECTION_DELAY

    def _count_up_value(self, target: int | float, section_index: int) -> int:
        """Return the animated count-up value for a given section."""
        section_start = section_index * self.SECTION_DELAY
        elapsed_in_section = self._elapsed - section_start
        if elapsed_in_section <= 0:
            return 0
        ratio = min(elapsed_in_section / self.COUNT_UP_DURATION, 1.0)
        return int(target * ratio)

    # ------------------------------------------------------------------
    # Panel drawing
    # ------------------------------------------------------------------

    def _draw_loot_panel(self, surface: pygame.Surface, sw: int, sh: int) -> None:
        panel_x, panel_y = 40, 100
        panel_w, panel_h = sw // 2 - 60, sh - 260

        # Panel background
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        pygame.draw.rect(surface, PANEL_BG, panel_rect, border_radius=4)
        pygame.draw.rect(surface, ACCENT_CYAN, panel_rect, width=1, border_radius=4)

        # Section header
        header = self._font_number.render("LOOT EXTRACTED", True, ACCENT_CYAN)
        surface.blit(header, (panel_x + 16, panel_y + 12))

        # Item list
        y_offset = panel_y + 44
        for i, item in enumerate(self.items):
            if y_offset > panel_y + panel_h - 24:
                break
            name = item.get("name", "Unknown")
            rarity = item.get("rarity", "common")
            value = item.get("value", 0)

            # Rarity colour
            rarity_color = _rarity_color(rarity)
            name_surface = self._font_body.render(f"  {name}", True, rarity_color)
            value_surface = self._font_body.render(f"${value}", True, ACCENT_GREEN)
            surface.blit(name_surface, (panel_x + 16, y_offset))
            surface.blit(
                value_surface,
                (panel_x + panel_w - value_surface.get_width() - 16, y_offset),
            )
            y_offset += 24

        if not self.items:
            empty_text = self._font_body.render("  No items extracted", True, TEXT_SECONDARY)
            surface.blit(empty_text, (panel_x + 16, y_offset))

    def _draw_rewards_panel(self, surface: pygame.Surface, sw: int, sh: int) -> None:
        panel_x = sw // 2 + 20
        panel_y = 100
        panel_w = sw // 2 - 60
        panel_h = sh - 260

        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        pygame.draw.rect(surface, PANEL_BG, panel_rect, border_radius=4)
        pygame.draw.rect(surface, ACCENT_CYAN, panel_rect, width=1, border_radius=4)

        header = self._font_number.render("REWARDS", True, ACCENT_CYAN)
        surface.blit(header, (panel_x + 16, panel_y + 12))

        y_offset = panel_y + 50

        # Total value
        display_value = self._count_up_value(self.total_value, 2)
        total_text = self._font_number.render(
            f"Loot Value: ${display_value}", True, ACCENT_GREEN
        )
        surface.blit(total_text, (panel_x + 16, y_offset))
        y_offset += 36

        # XP breakdown
        xp_header = self._font_body.render("XP Earned:", True, TEXT_PRIMARY)
        surface.blit(xp_header, (panel_x + 16, y_offset))
        y_offset += 24
        total_xp = 0
        for source, amount in self.xp_earned.items():
            display_xp = self._count_up_value(amount, 2)
            total_xp += amount
            label = source.replace("_", " ").title()
            xp_line = self._font_body.render(
                f"  {label}: +{display_xp} XP", True, ACCENT_GREEN
            )
            surface.blit(xp_line, (panel_x + 16, y_offset))
            y_offset += 22
        y_offset += 12

        # Money gained
        display_money = self._count_up_value(self.money_gained, 2)
        money_text = self._font_number.render(
            f"Money: +${display_money}", True, ACCENT_GOLD
        )
        surface.blit(money_text, (panel_x + 16, y_offset))

    def _draw_bottom_section(self, surface: pygame.Surface, sw: int, sh: int) -> None:
        # Level-up banner
        if self.level_after > self.level_before:
            pulse = 0.5 + 0.5 * math.sin(self._elapsed * 4.0)
            glow_alpha = int(180 + 75 * pulse)
            level_text = self._font_heading.render("LEVEL UP!", True, ACCENT_GOLD)
            # Glow effect via a slightly larger transparent blit
            glow_surface = pygame.Surface(
                (level_text.get_width() + 20, level_text.get_height() + 10),
                pygame.SRCALPHA,
            )
            glow_surface.fill((*ACCENT_GOLD, int(30 * pulse)))
            surface.blit(
                glow_surface,
                (sw // 2 - glow_surface.get_width() // 2, sh - 170),
            )
            surface.blit(
                level_text,
                (sw // 2 - level_text.get_width() // 2, sh - 165),
            )

        # XP progress bar
        bar_w, bar_h = 400, 16
        bar_x = sw // 2 - bar_w // 2
        bar_y = sh - 110
        pygame.draw.rect(surface, PANEL_BG, (bar_x, bar_y, bar_w, bar_h), border_radius=4)
        # Fill (placeholder ratio)
        fill_ratio = 0.3  # placeholder — would come from XP system
        fill_w = int(bar_w * fill_ratio)
        if fill_w > 0:
            pygame.draw.rect(
                surface,
                ACCENT_GREEN,
                (bar_x, bar_y, fill_w, bar_h),
                border_radius=4,
            )
        pygame.draw.rect(
            surface, TEXT_SECONDARY, (bar_x, bar_y, bar_w, bar_h), width=1, border_radius=4
        )
        level_label = self._font_body.render(
            f"Level {self.level_after}", True, TEXT_PRIMARY
        )
        surface.blit(level_label, (bar_x + bar_w + 12, bar_y - 2))

        # Continue button
        btn_w, btn_h = 200, 44
        btn_x = sw // 2 - btn_w // 2
        btn_y = sh - 70
        self._continue_btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        pygame.draw.rect(surface, ACCENT_CYAN, self._continue_btn_rect, border_radius=6)
        btn_text = self._font_button.render("CONTINUE", True, BG_DARK)
        surface.blit(
            btn_text,
            (btn_x + btn_w // 2 - btn_text.get_width() // 2, btn_y + 12),
        )

    # ------------------------------------------------------------------
    # Transition
    # ------------------------------------------------------------------

    _continue_btn_rect: pygame.Rect | None = None

    def _transition_next(self) -> None:
        """Move to the next scene (Home Base or Main Menu)."""
        # Try HomeBaseScene first, fall back to MainMenuScene
        try:
            from src.scenes.home_base_scene import HomeBaseScene
            self.game.replace_scene(HomeBaseScene(self.game))
        except (ImportError, AttributeError):
            try:
                from src.scenes.main_menu import MainMenuScene
                self.game.replace_scene(MainMenuScene(self.game))
            except (ImportError, AttributeError):
                # If neither scene exists yet, just signal completion
                pass


def _rarity_color(rarity: str) -> tuple[int, int, int]:
    """Map rarity string to display colour."""
    return {
        "common": TEXT_PRIMARY,
        "uncommon": ACCENT_GREEN,
        "rare": ACCENT_CYAN,
        "epic": (206, 147, 216),  # purple
    }.get(rarity, TEXT_PRIMARY)
