"""PostRound -- post-round summary screen scene."""
from __future__ import annotations

import logging

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

_STATUS_COLORS: dict[str, tuple] = {
    "success": (57, 255, 20),      # ACCENT_GREEN
    "timeout": (255, 165, 0),      # ACCENT_ORANGE
    "eliminated": (255, 50, 50),   # ACCENT_RED
}

_NUM_BUTTONS = 3
_log = logging.getLogger(__name__)


class PostRound:
    """Displays round statistics and lets the player choose what to do next.

    Progression (XP commit, currency credit, save) is committed exactly once
    inside ``__init__``; subsequent ``update`` calls do not re-apply it.

    XP is applied to the player in real-time during the round via event
    subscriptions on ``XPSystem``.  ``PostRound`` calls ``xp_system.commit()``
    to zero ``_pending_xp`` and finalise the round — it does **not** re-award.
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
            self._completed_challenges: list = []
            return

        self.summary = summary
        self.blurred_bg = blurred_bg
        self.xp_system = xp_system
        self.currency = currency
        self.save_manager = save_manager
        self.scene_manager = scene_manager
        self.asset_manager = asset_manager
        self.audio_system = audio_system

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
            save_manager.save(currency=currency, xp_system=xp_system)

        # Play outcome SFX
        if audio_system and summary:
            audio_system.play_sfx(_SFX_BY_STATUS.get(summary.extraction_status, "extraction_fail"))

        # Derived display values
        self.focused_button_index: int = 0
        self.show_level_up: bool = (
            summary.level_after > summary.level_before if summary else False
        )
        self.total_loot_value: int = sum(
            getattr(item, 'monetary_value', 0)
            for item in (summary.extracted_items if summary else [])
        )

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
        from src.constants import (
            BG_DEEP, BG_PANEL, BORDER_DIM,
            TEXT_PRIMARY, TEXT_SECONDARY, XP_COLOR, ACCENT_GREEN,
        )
        from src.ui.widgets import Panel, Label, ProgressBar

        self._ensure_fonts()

        if self.blurred_bg:
            surface.blit(self.blurred_bg, (0, 0))

        font = pygame.font.Font(None, 36)
        small_font = pygame.font.Font(None, 24)

        if self.summary:
            label = self.summary.extraction_status.upper()
        else:
            surface.fill(BG_DEEP)

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
    # ------------------------------------------------------------------

    def _ensure_fonts(self) -> None:
        if self._font_lg is None:
            self._font_lg = pygame.font.SysFont('monospace', 26, bold=True)
            self._font_md = pygame.font.SysFont('monospace', 18)
            self._font_sm = pygame.font.SysFont('monospace', 13)

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
