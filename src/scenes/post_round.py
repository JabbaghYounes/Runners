"""PostRound -- post-round summary screen scene.

Progression (XP award, currency credit, save) is committed exactly once inside
``__init__``.  Subsequent ``update`` / ``render`` calls are purely presentational.

Navigation buttons:
  0 – QUEUE AGAIN  → replace with a fresh GameScene
  1 – HOME BASE    → replace with HomeBaseScene
  2 – MAIN MENU    → replace with MainMenu
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from src.constants import (
    ACCENT_CYAN,
    ACCENT_GREEN,
    ACCENT_MAGENTA,
    BG_PANEL,
    BG_DEEP,
    BORDER_DIM,
    DANGER_RED,
    SCREEN_W,
    SCREEN_H,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from src.core.round_summary import RoundSummary
from src.scenes.game_scene import GameScene
from src.scenes.home_base_scene import HomeBaseScene
from src.scenes.main_menu import MainMenu

# Amber is not in src.constants — define locally.
_ACCENT_AMBER: tuple[int, int, int] = (255, 184, 0)

# Map extraction_status → SFX key
_SFX_BY_STATUS: dict[str, str] = {
    "success": "extraction_success",
    "timeout": "extraction_fail",
    "eliminated": "extraction_fail",
}

# How many buttons are shown on this screen
_NUM_BUTTONS = 3

# Map rarity string → display colour
_RARITY_COLOR: dict[str, tuple[int, int, int]] = {
    "common":    TEXT_PRIMARY,
    "uncommon":  ACCENT_GREEN,
    "rare":      ACCENT_CYAN,
    "epic":      ACCENT_MAGENTA,
    "legendary": _ACCENT_AMBER,
}

# ---------------------------------------------------------------------------
# Layout constants (all in screen-space pixels, 1280 × 720)
# ---------------------------------------------------------------------------
_PANEL_RECT = pygame.Rect(100, 30, 1080, 645)  # main card
_CL = 130          # content left edge
_CR = 1150         # content right edge
_COL2 = 660        # stats right column X

_HDR_Y = 78        # large status header centre-Y
_SUB_Y = 128       # sub-header (failure reason) centre-Y
_RULE1_Y = 150     # first separator line
_LOOT_LABEL_Y = 160  # "LOOT" section label
_ITEMS_Y = 185     # first item row top
_ITEM_ROW_H = 26   # pixels per item row
_MAX_ITEM_ROWS = 8  # clip after this many rows (last row becomes "…and N more")

_RULE2_Y = _ITEMS_Y + _MAX_ITEM_ROWS * _ITEM_ROW_H + 8   # = 401
_STATS_Y = 416     # stats section top
_STAT_ROW_H = 30   # stats row height

_XP_BAR_Y = 480    # XP progress bar top
_XP_BAR_W = 500    # bar width
_XP_BAR_H = 8      # bar height

_LEVELUP_Y = 505   # level-up label centre-Y
_BTN_Y = 566       # button row top
_BTN_W = 256       # each button width
_BTN_H = 44        # button height
_BTN_GAP = 20      # gap between buttons

# Focused button highlight colours
_BTN_BG_FOCUSED = (0, 60, 80)
_BTN_BG_NORMAL = (18, 22, 36)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rarity_color(item: object) -> tuple[int, int, int]:
    """Return the display colour for an item's rarity tier."""
    rarity = getattr(item, "rarity", None)
    if rarity is None:
        return TEXT_PRIMARY
    key = rarity.value if hasattr(rarity, "value") else str(rarity).lower()
    return _RARITY_COLOR.get(key, TEXT_PRIMARY)


def _safe_font(size: int) -> pygame.font.Font:
    if not pygame.font.get_init():
        pygame.font.init()
    return pygame.font.Font(None, size)


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------

class PostRound:
    """Displays round statistics and lets the player choose what to do next.

    Progression (XP award, currency credit, save) is committed exactly once
    inside ``__init__``; subsequent ``update`` calls do not re-apply it.
    """

    def __init__(
        self,
        summary: RoundSummary | None = None,
        blurred_bg: pygame.Surface | None = None,
        xp_system: object = None,
        currency: object = None,
        save_manager: object = None,
        scene_manager: object = None,
        asset_manager: object = None,
        audio_system: object = None,
        # Extra named args used by GameScene
        settings: object = None,
        assets: object = None,
        event_bus: object = None,
        home_base: object = None,
        # Legacy positional-style kwargs (kept for backward compatibility)
        sm: object = None,
        extracted: bool = False,
        loot_items: list | None = None,
    ) -> None:
        # ------------------------------------------------------------------
        # Legacy path: PostRound(sm=sm, settings=settings, assets=assets, …)
        # Used by any code that hasn't been updated to pass a RoundSummary.
        # ------------------------------------------------------------------
        if sm is not None and summary is None:
            self._sm = sm
            self._settings = settings
            self._assets = assets or asset_manager
            self._event_bus = event_bus
            self._home_base = home_base
            self._xp_system = xp_system
            self._currency = currency
            self._save_manager = save_manager
            self._audio_system = audio_system
            # Minimal display state (no real summary to render)
            self.summary: RoundSummary | None = None
            self.focused_button_index: int = 0
            self.show_level_up: bool = False
            self.total_loot_value: int = 0
            self._xp_before: int = 0
            self._xp_to_next_before: int = 100
            self._fonts: dict[str, pygame.font.Font] = {}
            self._btn_rects: list[pygame.Rect] = []
            return

        # ------------------------------------------------------------------
        # New path: PostRound(summary=summary, scene_manager=sm, …)
        # ------------------------------------------------------------------
        self._sm = scene_manager
        self._settings = settings
        self._assets = assets or asset_manager
        self._event_bus = event_bus
        self._home_base = home_base
        self._xp_system = xp_system
        self._currency = currency
        self._save_manager = save_manager
        self._audio_system = audio_system
        self.blurred_bg = blurred_bg

        # Snapshot XP position BEFORE awarding so the progress bar can
        # visualise the before → after transition within the level band.
        self._xp_before: int = xp_system.xp if xp_system else 0
        self._xp_to_next_before: int = (
            xp_system.xp_to_next_level() if xp_system else 100
        )

        # ------------------------------------------------------------------
        # Commit progression exactly once
        # ------------------------------------------------------------------
        if xp_system is not None and summary is not None:
            xp_system.award(summary.xp_earned)
            summary.level_after = xp_system.level
        if currency is not None and summary is not None:
            currency.add(summary.money_earned)
        if save_manager is not None:
            save_manager.save(
                xp_system=xp_system,
                currency=currency,
                home_base=home_base,
            )

        # Play outcome SFX (guarded: audio may be None or uninitialised)
        if audio_system is not None and summary is not None:
            sfx_key = _SFX_BY_STATUS.get(summary.extraction_status, "extraction_fail")
            try:
                audio_system.play_sfx(sfx_key)
            except Exception:
                pass

        # ------------------------------------------------------------------
        # Derived display state
        # ------------------------------------------------------------------
        self.summary: RoundSummary | None = summary
        self.focused_button_index: int = 0
        self.show_level_up: bool = bool(
            summary and summary.level_after > summary.level_before
        )
        self.total_loot_value: int = summary.total_loot_value if summary else 0

        # Lazily populated on first render
        self._fonts: dict[str, pygame.font.Font] = {}
        self._btn_rects: list[pygame.Rect] = []

    # ------------------------------------------------------------------
    # Scene interface
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """No per-frame state to advance on this screen."""

    def handle_events(self, events: list) -> None:
        """Route keyboard and mouse input to focus management and button activation."""
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_DOWN:
                    self.focused_button_index = (
                        self.focused_button_index + 1
                    ) % _NUM_BUTTONS
                elif event.key == pygame.K_UP:
                    self.focused_button_index = (
                        self.focused_button_index - 1
                    ) % _NUM_BUTTONS
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._activate_button(self.focused_button_index)

            elif event.type == pygame.MOUSEMOTION:
                # Hover updates focus without activating
                for i, rect in enumerate(self._btn_rects):
                    if rect.collidepoint(event.pos):
                        self.focused_button_index = i
                        break

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, rect in enumerate(self._btn_rects):
                    if rect.collidepoint(event.pos):
                        self.focused_button_index = i
                        self._activate_button(i)
                        break

    def render(self, surface: pygame.Surface) -> None:
        """Draw the full post-round screen onto *surface*."""
        self._ensure_fonts()
        self._ensure_button_rects()

        # Background fill
        surface.fill(BG_DEEP)

        # Main panel card
        self._draw_panel(surface)

        s = self.summary
        if s is None:
            # Minimal legacy render (no summary data)
            img = self._fonts["lg"].render("ROUND ENDED", True, TEXT_PRIMARY)
            surface.blit(img, img.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2)))
            self._draw_buttons(surface)
            return

        success = s.extraction_status == "success"

        # ── Header ────────────────────────────────────────────────────────
        hdr_text = "EXTRACTED" if success else "FAILED TO EXTRACT"
        hdr_color = ACCENT_GREEN if success else DANGER_RED
        hdr_surf = self._fonts["lg"].render(hdr_text, True, hdr_color)
        surface.blit(hdr_surf, hdr_surf.get_rect(center=(SCREEN_W // 2, _HDR_Y)))

        # Sub-header explaining failure (skipped on success)
        if not success:
            if s.extraction_status == "timeout":
                sub_text = "Round timer expired — all loot lost"
            else:
                sub_text = "You were eliminated — all loot lost"
            sub_surf = self._fonts["sm"].render(sub_text, True, TEXT_SECONDARY)
            surface.blit(sub_surf, sub_surf.get_rect(center=(SCREEN_W // 2, _SUB_Y)))

        # ── Separator 1 ───────────────────────────────────────────────────
        pygame.draw.line(surface, BORDER_DIM, (_CL, _RULE1_Y), (_CR, _RULE1_Y), 1)

        # ── Loot section ──────────────────────────────────────────────────
        loot_lbl = self._fonts["xs"].render("LOOT", True, TEXT_SECONDARY)
        surface.blit(loot_lbl, (_CL, _LOOT_LABEL_Y))

        if success and s.extracted_items:
            self._draw_items(surface, s.extracted_items)
        else:
            msg = "All loot lost." if not success else "No items extracted."
            msg_surf = self._fonts["md"].render(msg, True, TEXT_SECONDARY)
            center_y = _ITEMS_Y + (_MAX_ITEM_ROWS * _ITEM_ROW_H) // 2
            surface.blit(msg_surf, msg_surf.get_rect(center=(SCREEN_W // 2, center_y)))

        # ── Separator 2 ───────────────────────────────────────────────────
        pygame.draw.line(surface, BORDER_DIM, (_CL, _RULE2_Y), (_CR, _RULE2_Y), 1)

        # ── Stats section ─────────────────────────────────────────────────
        self._draw_stats(surface, s)

        # ── XP progress bar ───────────────────────────────────────────────
        if s.xp_earned > 0:
            self._draw_xp_bar(surface)

        # ── Level-up row ──────────────────────────────────────────────────
        if self.show_level_up:
            lvl_txt = f"LEVEL UP!   {s.level_before} → {s.level_after}"
            lvl_surf = self._fonts["md"].render(lvl_txt, True, _ACCENT_AMBER)
            surface.blit(lvl_surf, lvl_surf.get_rect(center=(SCREEN_W // 2, _LEVELUP_Y)))

        # ── Navigation buttons ────────────────────────────────────────────
        self._draw_buttons(surface)

    # ------------------------------------------------------------------
    # Private rendering helpers
    # ------------------------------------------------------------------

    def _draw_panel(self, surface: pygame.Surface) -> None:
        """Draw the semi-transparent background card."""
        r, g, b = BG_PANEL[:3]
        panel_surf = pygame.Surface(_PANEL_RECT.size, pygame.SRCALPHA)
        pygame.draw.rect(
            panel_surf, (r, g, b, 230),
            panel_surf.get_rect(), border_radius=8,
        )
        surface.blit(panel_surf, _PANEL_RECT.topleft)
        pygame.draw.rect(surface, BORDER_DIM, _PANEL_RECT, width=1, border_radius=8)

    def _draw_items(self, surface: pygame.Surface, items: list) -> None:
        """Render extracted items list, clipping to _MAX_ITEM_ROWS."""
        font = self._fonts["md"]
        total = len(items)
        # Reserve the last row for the "…and N more" overflow notice
        if total > _MAX_ITEM_ROWS:
            visible = items[: _MAX_ITEM_ROWS - 1]
            remainder = total - len(visible)
        else:
            visible = items
            remainder = 0

        for i, item in enumerate(visible):
            y = _ITEMS_Y + i * _ITEM_ROW_H
            color = _rarity_color(item)

            # Item name (left-aligned)
            name_surf = font.render(item.name, True, color)
            surface.blit(name_surf, (_CL + 8, y))

            # Monetary value (right-aligned)
            val = int(getattr(item, "monetary_value", getattr(item, "value", 0)))
            val_surf = font.render(f"${val:,}", True, color)
            surface.blit(val_surf, val_surf.get_rect(right=_CR, y=y))

        if remainder > 0:
            y = _ITEMS_Y + len(visible) * _ITEM_ROW_H
            more_surf = self._fonts["xs"].render(
                f"…and {remainder} more", True, TEXT_SECONDARY
            )
            surface.blit(more_surf, (_CL + 8, y))

    def _draw_stats(self, surface: pygame.Surface, s: RoundSummary) -> None:
        """Render the two-column stats grid."""
        font = self._fonts["md"]

        # ── Left column ───────────────────────────────────────────────────
        y = _STATS_Y
        surface.blit(
            font.render(f"XP earned:  +{s.xp_earned:,}", True, TEXT_PRIMARY),
            (_CL, y),
        )
        y += _STAT_ROW_H
        surface.blit(
            font.render(f"Money:  ${s.money_earned:,}", True, TEXT_PRIMARY),
            (_CL, y),
        )

        # ── Right column ──────────────────────────────────────────────────
        y = _STATS_Y
        surface.blit(
            font.render(f"Kills:  {s.kills}", True, TEXT_PRIMARY),
            (_COL2, y),
        )
        y += _STAT_ROW_H
        if s.challenges_total > 0:
            surface.blit(
                font.render(
                    f"Challenges:  {s.challenges_completed}/{s.challenges_total}",
                    True, TEXT_PRIMARY,
                ),
                (_COL2, y),
            )

    def _draw_xp_bar(self, surface: pygame.Surface) -> None:
        """Render a horizontal XP progress bar showing before → after within level."""
        bar_x = SCREEN_W // 2 - _XP_BAR_W // 2
        bar_y = _XP_BAR_Y

        # If the player levelled up, fill to 100%; otherwise show new position
        if self.show_level_up:
            fill_ratio = 1.0
        else:
            xp_after = self._xp_system.xp if self._xp_system else 0
            xp_cap = max(self._xp_to_next_before, 1)
            fill_ratio = min(1.0, xp_after / xp_cap)

        # Background track
        pygame.draw.rect(
            surface, BORDER_DIM,
            (bar_x, bar_y, _XP_BAR_W, _XP_BAR_H),
            border_radius=4,
        )
        # Filled portion
        fill_w = max(0, int(_XP_BAR_W * fill_ratio))
        if fill_w > 0:
            pygame.draw.rect(
                surface, ACCENT_CYAN,
                (bar_x, bar_y, fill_w, _XP_BAR_H),
                border_radius=4,
            )

    def _ensure_button_rects(self) -> None:
        """Compute the three button Rects once and cache them."""
        if self._btn_rects:
            return
        total_w = _NUM_BUTTONS * _BTN_W + (_NUM_BUTTONS - 1) * _BTN_GAP
        start_x = (SCREEN_W - total_w) // 2
        self._btn_rects = [
            pygame.Rect(start_x + i * (_BTN_W + _BTN_GAP), _BTN_Y, _BTN_W, _BTN_H)
            for i in range(_NUM_BUTTONS)
        ]

    def _draw_buttons(self, surface: pygame.Surface) -> None:
        """Render the three navigation buttons with focus highlighting."""
        labels = ["QUEUE AGAIN", "HOME BASE", "MAIN MENU"]
        font = self._fonts.get("btn", self._fonts.get("md", _safe_font(24)))

        for i, (rect, label) in enumerate(zip(self._btn_rects, labels)):
            focused = i == self.focused_button_index
            bg = _BTN_BG_FOCUSED if focused else _BTN_BG_NORMAL
            border = ACCENT_CYAN if focused else BORDER_DIM
            border_w = 2 if focused else 1
            txt_color = ACCENT_CYAN if focused else TEXT_PRIMARY

            pygame.draw.rect(surface, bg, rect, border_radius=4)
            pygame.draw.rect(surface, border, rect, width=border_w, border_radius=4)

            txt_surf = font.render(label, True, txt_color)
            surface.blit(txt_surf, txt_surf.get_rect(center=rect.center))

    def _ensure_fonts(self) -> None:
        """Lazily create pygame fonts on first render call."""
        if self._fonts:
            return
        self._fonts = {
            "lg":  _safe_font(52),   # status header
            "md":  _safe_font(26),   # body text / item rows
            "sm":  _safe_font(22),   # sub-header
            "xs":  _safe_font(18),   # section labels / hints
            "btn": _safe_font(24),   # button labels
        }

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _activate_button(self, index: int) -> None:
        """Route the activated button to the correct scene transition."""
        sm = self._sm
        if sm is None:
            return

        if index == 0:
            # Queue Again — start a completely fresh round
            try:
                from src.core.event_bus import EventBus
                eb = EventBus()
                sm.replace_all(GameScene(
                    sm,
                    self._settings,
                    self._assets,
                    eb,
                    self._xp_system,
                    self._currency,
                    self._home_base,
                ))
            except Exception as e:
                print(f"[PostRound] Queue Again failed: {e}")

        elif index == 1:
            # Home Base — peer scene transition (no on_resume for whatever was below)
            try:
                sm.replace(HomeBaseScene(
                    sm,
                    self._settings,
                    self._assets,
                    self._home_base,
                    None,           # skill_tree — PostRound doesn't carry it
                    self._currency,
                    self._xp_system,
                ))
            except Exception as e:
                print(f"[PostRound] Home Base navigate failed: {e}")

        elif index == 2:
            # Main Menu — hard navigation, clear the entire stack
            try:
                sm.replace_all(MainMenu(sm, self._settings, self._assets))
            except Exception as e:
                print(f"[PostRound] Main Menu navigate failed: {e}")
