"""PostRound -- post-round summary screen scene.

Progression (XP award, currency credit, save) is committed exactly once inside
``__init__``.  Subsequent ``update`` / ``render`` calls are purely presentational.

Navigation buttons:
  0 – QUEUE AGAIN  → replace with a fresh GameScene
  1 – HOME BASE    → replace with HomeBaseScene
  2 – MAIN MENU    → replace with MainMenu
"""
from __future__ import annotations

import logging

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
_log = logging.getLogger(__name__)

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
        summary: "RoundSummary | None" = None,
        blurred_bg: "pygame.Surface | None" = None,
        xp_system=None,
        currency=None,
        save_manager=None,
        scene_manager=None,
        asset_manager=None,
        audio_system=None,
        challenge_system=None,
        # Legacy positional args
        sm=None,
        settings=None,
        assets=None,
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
            self._assets = assets
            self.summary = None
            self.focused_button_index = 0
            self.show_level_up = False
            self.total_loot_value = 0
            self._completed_challenges: list = []
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

        # Store completed challenges for render-time display
        self._completed_challenges: list = []

        # --- Commit base progression ---
        if xp_system and summary:
            xp_system.award(summary.xp_earned)
        if currency and summary:
            currency.add(summary.money_earned)

        # --- Apply challenge bonus rewards (idempotent: runs once in __init__) ---
        if challenge_system is not None and summary is not None:
            try:
                completed = challenge_system.get_completed_challenges()
            except Exception as exc:
                _log.warning("[PostRound] get_completed_challenges() failed: %s", exc)
                completed = []

            self._completed_challenges = list(completed)

            for ch in completed:
                if xp_system:
                    xp_system.award(ch.reward_xp)
                if currency:
                    currency.add(ch.reward_money)
                summary.challenge_bonus_xp += ch.reward_xp
                summary.challenge_bonus_money += ch.reward_money

                if ch.reward_item_id:
                    self._grant_item_reward(ch, summary, currency)

        # Update level_after after ALL XP has been awarded
        if xp_system and summary:
            summary.level_after = xp_system.level

        if save_manager:
            save_manager.save()

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
        self.show_level_up: bool = (
            summary.level_after > summary.level_before if summary else False
        )
        self.total_loot_value: int = sum(
            getattr(item, 'monetary_value', 0)
            for item in (summary.extracted_items if summary else [])
        )
        self.total_loot_value: int = summary.total_loot_value if summary else 0

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _grant_item_reward(self, ch: object, summary: "RoundSummary", currency: object) -> None:
        """Create the reward item and append it to the summary, or fall back to money."""
        _FALLBACK_MONEY = 50
        item_id = getattr(ch, 'reward_item_id', None)
        ch_id = getattr(ch, 'id', '?')
        try:
            from src.inventory.item_database import ItemDatabase
            item = ItemDatabase.instance().create(item_id)
            summary.extracted_items.append(item)
            summary.challenge_bonus_items.append(item_id)
        except Exception as exc:
            _log.warning(
                "[PostRound] Unknown reward_item_id %r for challenge %r: %s — "
                "granting %d money fallback instead.",
                item_id,
                ch_id,
                exc,
                _FALLBACK_MONEY,
            )
            if currency:
                currency.add(_FALLBACK_MONEY)
            summary.challenge_bonus_money += _FALLBACK_MONEY

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
        """Draw the post-round screen onto *surface*."""
        if self.blurred_bg:
            surface.blit(self.blurred_bg, (0, 0))

        font = pygame.font.Font(None, 36)
        small_font = pygame.font.Font(None, 24)

        if self.summary:
            label = self.summary.extraction_status.upper()
        else:
            label = "ROUND ENDED"
        img = font.render(label, True, (255, 255, 255))
        surface.blit(img, (100, 100))

        if self.summary:
            y = 148

            # Challenge count summary
            c_done = self.summary.challenges_completed
            c_total = self.summary.challenges_total
            count_surf = small_font.render(
                f"Challenges: {c_done} / {c_total}", True, (200, 200, 200)
            )
            surface.blit(count_surf, (100, y))
            y += 28

            # Challenge bonus totals
            bonus_xp = self.summary.challenge_bonus_xp
            bonus_money = self.summary.challenge_bonus_money
            if bonus_xp > 0 or bonus_money > 0:
                bonus_surf = small_font.render(
                    f"Challenge Bonus: +{bonus_xp} XP,  +{bonus_money} cr",
                    True,
                    (57, 255, 20),
                )
                surface.blit(bonus_surf, (100, y))
                y += 24

            # Per-completed-challenge breakdown
            for ch in self._completed_challenges:
                desc = getattr(ch, 'description', getattr(ch, 'id', '?'))
                xp = getattr(ch, 'reward_xp', 0)
                money = getattr(ch, 'reward_money', 0)
                item_id = getattr(ch, 'reward_item_id', None)
                reward_parts = []
                if xp:
                    reward_parts.append(f"+{xp} XP")
                if money:
                    reward_parts.append(f"+{money} cr")
                if item_id:
                    reward_parts.append(f"+{item_id}")
                reward_str = ", ".join(reward_parts) if reward_parts else ""
                line = f"  \u2713 {desc}"
                if reward_str:
                    line += f"  [{reward_str}]"
                ch_surf = small_font.render(line, True, (57, 255, 20))
                surface.blit(ch_surf, (100, y))
                y += 22

    # Private helpers

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
