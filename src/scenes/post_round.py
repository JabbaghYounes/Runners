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

_STATUS_COLORS: dict[str, tuple] = {
    "success": (57, 255, 20),      # ACCENT_GREEN
    "timeout": (255, 165, 0),      # ACCENT_ORANGE
    "eliminated": (255, 50, 50),   # ACCENT_RED
}

_NUM_BUTTONS = 3


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
            self.xp_system = None
            self._font_lg = None
            self._font_md = None
            self._font_sm = None
            return

        self.summary = summary
        self.blurred_bg = blurred_bg
        self.xp_system = xp_system
        self.currency = currency
        self.save_manager = save_manager
        self.scene_manager = scene_manager
        self.asset_manager = asset_manager
        self.audio_system = audio_system

        # Commit progression (exactly once).
        # XP was already applied live during the round via XPSystem event handlers.
        # commit() zeroes _pending_xp without re-awarding.
        if xp_system and summary:
            summary.level_after = xp_system.level
            xp_system.commit()
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

        # Lazy fonts
        self._font_lg = None
        self._font_md = None
        self._font_sm = None

    # ------------------------------------------------------------------
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
        else:
            surface.fill(BG_DEEP)

        if self.summary is None:
            # Legacy fallback — no RoundSummary (old test path or legacy constructor)
            img = self._font_lg.render("ROUND ENDED", True, TEXT_PRIMARY)
            surface.blit(img, (100, 100))
            return

        s = self.summary
        status_color = _STATUS_COLORS.get(s.extraction_status, TEXT_PRIMARY)

        # ── Main panel ──────────────────────────────────────────────────
        panel_rect = pygame.Rect(80, 50, 600, 560)
        Panel(panel_rect, bg_color=BG_PANEL, border_color=BORDER_DIM).draw(surface)

        y = 76

        # Status header
        Label(
            text=s.extraction_status.upper(),
            font=self._font_lg,
            color=status_color,
            pos=(panel_rect.centerx, y),
            anchor='midtop',
        ).draw(surface)
        y += 56

        # ── XP row ──────────────────────────────────────────────────────
        Label(
            text=f"XP EARNED:  +{s.xp_earned}",
            font=self._font_md,
            color=XP_COLOR,
            pos=(panel_rect.x + 24, y),
            anchor='topleft',
        ).draw(surface)
        y += 38

        # ── Level row ───────────────────────────────────────────────────
        level_after = s.level_after if s.level_after else s.level_before
        if self.show_level_up:
            lvl_text = f"LEVEL:  {s.level_before}  \u2192  {level_after}   \u2605 LEVEL UP!"
            lvl_color = ACCENT_GREEN
        else:
            lvl_text = f"LEVEL:  {level_after}"
            lvl_color = TEXT_PRIMARY
        Label(
            text=lvl_text,
            font=self._font_md,
            color=lvl_color,
            pos=(panel_rect.x + 24, y),
            anchor='topleft',
        ).draw(surface)
        y += 38

        # ── XP progress bar (post-round position within current level) ──
        if self.xp_system is not None:
            bar_rect = pygame.Rect(panel_rect.x + 24, y, panel_rect.width - 48, 10)
            xp_now = self.xp_system.xp
            xp_next = max(self.xp_system.xp_to_next_level(), 1)
            ProgressBar(
                rect=bar_rect,
                value=xp_now,
                max_value=xp_now + xp_next,
                fill_color=XP_COLOR,
                bg_color=(30, 34, 50),
                border_color=BORDER_DIM,
                show_text=False,
            ).draw(surface)
            Label(
                text=f"LV{self.xp_system.level}  {xp_now} / {xp_next} XP to next level",
                font=self._font_sm,
                color=TEXT_SECONDARY,
                pos=(bar_rect.centerx, bar_rect.bottom + 4),
                anchor='midtop',
            ).draw(surface)
            y += 34

        y += 10

        # ── Kill / challenge rows ────────────────────────────────────────
        Label(
            text=f"KILLS:  {s.kills}",
            font=self._font_md,
            color=TEXT_PRIMARY,
            pos=(panel_rect.x + 24, y),
            anchor='topleft',
        ).draw(surface)
        y += 38

        Label(
            text=f"CHALLENGES:  {s.challenges_completed} / {s.challenges_total}",
            font=self._font_md,
            color=TEXT_PRIMARY,
            pos=(panel_rect.x + 24, y),
            anchor='topleft',
        ).draw(surface)
        y += 38

        # ── Loot value (success only) ────────────────────────────────────
        if s.extraction_status == "success" and self.total_loot_value:
            from src.constants import ACCENT_ORANGE
            Label(
                text=f"LOOT VALUE:  \xa4{self.total_loot_value}",
                font=self._font_md,
                color=ACCENT_ORANGE,
                pos=(panel_rect.x + 24, y),
                anchor='topleft',
            ).draw(surface)
            y += 38

        # ── Action buttons ───────────────────────────────────────────────
        btn_labels = ["QUEUE NEXT ROUND", "GO TO HOME BASE", "EXIT TO MAIN MENU"]
        btn_y = panel_rect.bottom - 148
        for i, lbl in enumerate(btn_labels):
            is_focused = (i == self.focused_button_index)
            btn_color = status_color if is_focused else TEXT_SECONDARY
            prefix = "\u25b6  " if is_focused else "   "
            Label(
                text=f"{prefix}{lbl}",
                font=self._font_md,
                color=btn_color,
                pos=(panel_rect.x + 24, btn_y + i * 44),
                anchor='topleft',
            ).draw(surface)

    # ------------------------------------------------------------------
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
