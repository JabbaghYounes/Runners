"""HomeBaseScene — between-round hub with facility upgrades and skill tree."""
from __future__ import annotations
from typing import Optional

import pygame

from src.scenes.base_scene import BaseScene
from src.ui.home_base_screen import HomeBaseScreen
from src.ui.widgets import (
    ACCENT_AMBER, ACCENT_CYAN, ACCENT_GREEN, BG_DEEP, BG_PANEL,
    BORDER_DIM, DANGER_RED, TEXT_PRIMARY, TEXT_SECONDARY,
    Button, Panel, Label, ProgressBar, TabBar,
)


class HomeBaseScene(BaseScene):
    """Between-round progression hub.

    Layout:
        ┌─ Status bar (level, XP, money) ──────────────────────────┐
        │ ┌─ TabBar: HOME BASE | SKILL TREE ──────────────────────┐ │
        │ │ Content area (facility cards OR skill tree stub)       │ │
        │ └────────────────────────────────────────────────────────┘ │
        │            [ QUEUE FOR ROUND ▶ ]                           │
        └────────────────────────────────────────────────────────────┘

    Args:
        home_base: HomeBase progression object (long-lived).
        currency: Currency progression object.
        xp_system: XPSystem progression object.
        scene_manager: SceneManager for scene transitions.
        save_manager: SaveManager to persist state on exit.
    """

    _STATUS_H = 56      # px — height of top status bar
    _TABBAR_H = 44      # px — height of tab bar
    _QUEUE_BTN_H = 48   # px — height of the queue button
    _QUEUE_BTN_W = 560  # px

    def __init__(
        self,
        home_base,
        currency,
        xp_system,
        scene_manager,
        save_manager,
    ) -> None:
        self._home_base = home_base
        self._currency = currency
        self._xp_system = xp_system
        self._scene_manager = scene_manager
        self._save_manager = save_manager

        self._active_tab: int = 0
        self._initialized = False

        # These are built lazily on first render because we need surface size
        self._tab_bar: Optional[TabBar] = None
        self._queue_btn: Optional[Button] = None
        self._home_base_screen: Optional[HomeBaseScreen] = None
        self._xp_bar: Optional[ProgressBar] = None

    # ------------------------------------------------------------------
    # Scene lifecycle
    # ------------------------------------------------------------------

    def on_enter(self) -> None:
        self._initialized = False  # force re-init next render

    def on_exit(self) -> None:
        """Save progression state when leaving the scene."""
        self._save_manager.save(
            home_base=self._home_base,
            currency=self._currency,
            xp_system=self._xp_system,
        )

    # ------------------------------------------------------------------
    # Lazy initialisation (needs surface dimensions)
    # ------------------------------------------------------------------

    def _ensure_init(self, surface) -> None:
        if self._initialized:
            return
        sw, sh = surface.get_size()

        # --- Tab bar ---
        tab_rect = pygame.Rect(16, self._STATUS_H + 8, sw - 32, self._TABBAR_H)
        self._tab_bar = TabBar(
            tabs=["HOME BASE", "SKILL TREE"],
            active_index=self._active_tab,
            rect=tab_rect,
            on_change=self._on_tab_change,
        )

        # --- Queue button ---
        btn_x = (sw - self._QUEUE_BTN_W) // 2
        btn_y = sh - self._QUEUE_BTN_H - 20
        self._queue_btn = Button(
            label="QUEUE FOR ROUND  \u25b6",
            rect=pygame.Rect(btn_x, btn_y, self._QUEUE_BTN_W, self._QUEUE_BTN_H),
            style="primary",
            on_click=self._on_queue,
        )

        # --- Content area for HomeBaseScreen ---
        content_y = self._STATUS_H + self._TABBAR_H + 16
        content_h = btn_y - content_y - 8
        content_rect = pygame.Rect(16, content_y, sw - 32, content_h)
        self._home_base_screen = HomeBaseScreen(
            self._home_base, self._currency, content_rect
        )

        # --- XP progress bar ---
        xp_bar_rect = pygame.Rect(100, 16, 280, 16)
        total_xp = max(1, self._xp_system.xp + max(1, self._xp_system.xp_to_next_level()))
        self._xp_bar = ProgressBar(
            value=self._xp_system.xp,
            max_value=total_xp,
            rect=xp_bar_rect,
            variant="xp",
        )

        self._initialized = True

    def _on_tab_change(self, idx: int) -> None:
        self._active_tab = idx

    def _on_queue(self) -> None:
        """Navigate to GameScene with home_base bonuses applied."""
        # Import here to avoid circular imports at module load time
        from src.scenes.game_scene import GameScene
        from src.core.event_bus import EventBus
        from src.core.settings import Settings
        from src.systems.audio_system import AudioSystem
        from src.core.asset_manager import AssetManager

        event_bus = EventBus()
        asset_manager = AssetManager()
        settings = Settings.load()
        audio = AudioSystem(event_bus, asset_manager, settings)

        game_scene = GameScene(
            event_bus=event_bus,
            audio=audio,
            settings=settings,
            zones=None,
            home_base=self._home_base,
        )
        self._scene_manager.replace(game_scene)

    # ------------------------------------------------------------------
    # BaseScene interface
    # ------------------------------------------------------------------

    def handle_events(self, events: list) -> None:
        self._ensure_init_stub()
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._scene_manager.pop()
                return
            if self._tab_bar:
                self._tab_bar.handle_event(event)
            if self._queue_btn:
                self._queue_btn.handle_event(event)
            if self._home_base_screen and self._active_tab == 0:
                self._home_base_screen.handle_events([event])

    def _ensure_init_stub(self) -> None:
        pass

    def update(self, dt: float) -> None:
        if self._xp_bar:
            total = max(1, self._xp_system.xp + max(1, self._xp_system.xp_to_next_level()))
            self._xp_bar.value = self._xp_system.xp
            self._xp_bar.max_value = total

    def render(self, screen) -> None:
        self._ensure_init(screen)
        sw, sh = screen.get_size()

        # --- Background ---
        screen.fill(BG_DEEP)

        # --- Status bar ---
        self._render_status_bar(screen, sw)

        # --- Tab bar ---
        if self._tab_bar:
            self._tab_bar.render(screen)

        # --- Tab underline separator ---
        sep_y = self._STATUS_H + self._TABBAR_H + 8
        pygame.draw.line(screen, BORDER_DIM, (0, sep_y), (sw, sep_y), 1)

        # --- Content area ---
        if self._active_tab == 0 and self._home_base_screen:
            self._home_base_screen.render(screen)
        elif self._active_tab == 1:
            self._render_skill_tree_stub(screen, sw, sh)

        # --- Queue button ---
        if self._queue_btn:
            self._queue_btn.render(screen)

    def _render_status_bar(self, screen, sw: int) -> None:
        """Draw the top status bar: level badge, XP bar, name, money."""
        font_sm = pygame.font.SysFont("monospace", 13)
        font_md = pygame.font.SysFont("monospace", 16, bold=True)

        # Background panel
        bar_panel = Panel(
            pygame.Rect(0, 0, sw, self._STATUS_H),
            bg_color=BG_PANEL,
            border_color=BORDER_DIM,
            border_width=1,
        )
        bar_panel.render(screen)

        # Level badge
        lvl_text = f"Lv.{self._xp_system.level}"
        lvl_surf = font_md.render(lvl_text, True, ACCENT_CYAN)
        screen.blit(lvl_surf, (16, (self._STATUS_H - lvl_surf.get_height()) // 2))

        # XP bar
        xp_x = 16 + lvl_surf.get_width() + 12
        xp_rect = pygame.Rect(xp_x, (self._STATUS_H - 14) // 2, 240, 14)
        total_xp = max(1, self._xp_system.xp + max(1, self._xp_system.xp_to_next_level()))
        xp_bar = ProgressBar(
            value=self._xp_system.xp,
            max_value=total_xp,
            rect=xp_rect,
            variant="xp",
        )
        xp_bar.render(screen)

        # Player name (stub)
        name_surf = font_sm.render("RUNNER-01", True, TEXT_SECONDARY)
        name_x = xp_rect.right + 20
        screen.blit(name_surf, (name_x, (self._STATUS_H - name_surf.get_height()) // 2))

        # Money (amber)
        money_text = self._currency.formatted()
        money_surf = font_md.render(money_text, True, ACCENT_AMBER)
        screen.blit(money_surf, (sw - money_surf.get_width() - 20,
                                  (self._STATUS_H - money_surf.get_height()) // 2))

    def _render_skill_tree_stub(self, screen, sw: int, sh: int) -> None:
        """Placeholder for the Skill Tree tab (full implementation deferred)."""
        font = pygame.font.SysFont("monospace", 18, bold=True)
        msg = "SKILL TREE — Coming Soon"
        surf = font.render(msg, True, TEXT_SECONDARY)
        rect = surf.get_rect(center=(sw // 2, sh // 2))
        screen.blit(surf, rect)
