"""HUD -- composite in-game overlay orchestrator."""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING

import pygame

from src.ui.mini_map import MiniMap
from src.ui.challenge_widget import ChallengeWidget
from src.ui.widgets import Panel, Label, ProgressBar, IconSlot
from src.ui.hud_state import HUDState
from src.constants import (
    SCREEN_W, SCREEN_H,
    ACCENT_CYAN, ACCENT_GREEN, ACCENT_RED, ACCENT_ORANGE,
    DANGER_RED, BG_PANEL, BORDER_DIM, TEXT_PRIMARY, TEXT_SECONDARY,
    TEXT_BRIGHT, TEXT_DIM, PANEL_BG, BORDER_BRIGHT,
    HEALTH_COLOR, ARMOR_COLOR, XP_COLOR, ACCENT_MAGENTA,
)

if TYPE_CHECKING:
    from src.core.event_bus import EventBus

# Layout
MARGIN = 16
PADDING = 16

_STATUS_RECT_X = MARGIN
_STATUS_RECT_Y = MARGIN
_STATUS_RECT_W = 220
_STATUS_RECT_H = 100

_TIMER_RECT_X = SCREEN_W // 2 - 60
_TIMER_RECT_Y = MARGIN
_TIMER_RECT_W = 120
_TIMER_RECT_H = 32

_MINIMAP_W = 180
_MINIMAP_H = 180
_MINIMAP_X = SCREEN_W - _MINIMAP_W - MARGIN
_MINIMAP_Y = MARGIN

_CHALLENGE_W = 200
_CHALLENGE_H = 200
_CHALLENGE_X = SCREEN_W - _CHALLENGE_W - MARGIN
_CHALLENGE_Y = _MINIMAP_Y + _MINIMAP_H + MARGIN

_WEAPON_RECT_X = MARGIN
_WEAPON_RECT_Y = SCREEN_H - 80 - MARGIN
_WEAPON_RECT_W = 200
_WEAPON_RECT_H = 56

_QUICKSLOT_SIZE = 44
_QUICKSLOT_GAP  = 4
_QUICKSLOT_COUNT = 4
_QUICKSLOTS_W = _QUICKSLOT_COUNT * _QUICKSLOT_SIZE + (_QUICKSLOT_COUNT - 1) * _QUICKSLOT_GAP
_QUICKSLOTS_X = SCREEN_W - _QUICKSLOTS_W - MARGIN
_QUICKSLOTS_Y = SCREEN_H - _QUICKSLOT_SIZE - MARGIN

# Transient effect timers
_DAMAGE_FLASH_DURATION  = 0.3
_LEVELUP_BANNER_DURATION = 1.5
_BUFF_PULSE_THRESHOLD   = 3.0

# Color constants from feature branch
ACCENT_AMBER = (255, 184, 0)


class HUD:
    """Composite in-game heads-up display."""

    def __init__(self, event_bus: "EventBus") -> None:
        self._event_bus = event_bus
        self._state: HUDState = HUDState()

        # Sub-widgets (lazy-init)
        self._minimap: Optional[MiniMap] = None
        self._challenge_widget: Optional[ChallengeWidget] = None

        # Transient effect state
        self._damage_flash_timer: float = 0.0
        self._levelup_banner_timer: float = 0.0
        # Aliases expected by tests
        self._vignette_timer: float = 0.0
        self._level_up_timer: float = 0.0
        self._zone_label_timer: float = 0.0
        self._zone_label: str = ""

        # Fonts (lazy)
        self._font_lg = None
        self._font_md = None
        self._font_sm = None
        self._fonts_ready: bool = False

        # Subscribe to EventBus events
        event_bus.subscribe('player.damaged', self._on_player_damaged)
        event_bus.subscribe('player_damaged', self._on_player_damaged)
        event_bus.subscribe('level.up',       self._on_level_up)
        event_bus.subscribe('level_up',       self._on_level_up)
        event_bus.subscribe('zone_entered',   self._on_zone_entered)

    def _on_player_damaged(self, **payload) -> None:
        self._damage_flash_timer = _DAMAGE_FLASH_DURATION
        self._vignette_timer = 0.5

    def _on_level_up(self, **payload) -> None:
        self._levelup_banner_timer = _LEVELUP_BANNER_DURATION
        self._level_up_timer = 3.0

    def _on_zone_entered(self, **kwargs) -> None:
        zone = kwargs.get('zone')
        if zone is not None:
            self._zone_label = getattr(zone, 'name', '')
            self._zone_label_timer = 2.5

    def teardown(self) -> None:
        """Unsubscribe from EventBus."""
        for event, handler in (
            ('player.damaged', self._on_player_damaged),
            ('player_damaged', self._on_player_damaged),
            ('level.up',       self._on_level_up),
            ('level_up',       self._on_level_up),
            ('zone_entered',   self._on_zone_entered),
        ):
            try:
                self._event_bus.unsubscribe(event, handler)
            except Exception:
                pass

    def update(self, state: HUDState, dt: float) -> None:
        """Cache the latest state snapshot and tick transient timers."""
        self._state = state

        if self._damage_flash_timer > 0:
            self._damage_flash_timer = max(0.0, self._damage_flash_timer - dt)
        if self._levelup_banner_timer > 0:
            self._levelup_banner_timer = max(0.0, self._levelup_banner_timer - dt)
        if self._vignette_timer > 0:
            self._vignette_timer = max(0.0, self._vignette_timer - dt)
        if self._level_up_timer > 0:
            self._level_up_timer = max(0.0, self._level_up_timer - dt)
        if self._zone_label_timer > 0:
            self._zone_label_timer = max(0.0, self._zone_label_timer - dt)

        # Lazy-init sub-widgets
        if self._minimap is None:
            self._minimap = MiniMap(
                pygame.Rect(_MINIMAP_X, _MINIMAP_Y, _MINIMAP_W, _MINIMAP_H)
            )
        if self._challenge_widget is None:
            self._challenge_widget = ChallengeWidget(
                pygame.Rect(_CHALLENGE_X, _CHALLENGE_Y, _CHALLENGE_W, _CHALLENGE_H)
            )
        self._minimap.update(state)
        self._challenge_widget.update(state.active_challenges)

    def draw(self, surface: pygame.Surface) -> None:
        """Render all HUD elements."""
        self._ensure_fonts()
        state = self._state

        # 1. Health / Armor / XP (top-left)
        self._draw_status_panel(surface, state)

        # 2. Buff icon row
        self._draw_buffs(surface, state)

        # 3. Round timer (top-center)
        self._draw_timer(surface, state)

        # 4. Mini-map (top-right)
        if self._minimap:
            self._minimap.draw(surface)

        # 5. Weapon info (bottom-left)
        self._draw_weapon(surface, state)

        # 6. Quick-slots (bottom-right)
        self._draw_quickslots(surface, state)

        # 7. Challenge widget
        if self._challenge_widget:
            self._challenge_widget.draw(surface)

        # 8. Transient effects
        if self._damage_flash_timer > 0:
            self._draw_damage_vignette(surface)
        if self._levelup_banner_timer > 0:
            self._draw_levelup_banner(surface)

    def _ensure_fonts(self) -> None:
        if self._fonts_ready:
            return
        self._font_lg = pygame.font.SysFont('monospace', 18, bold=True)
        self._font_md = pygame.font.SysFont('monospace', 13)
        self._font_sm = pygame.font.SysFont('monospace', 11)
        self._fonts_ready = True

    def _draw_status_panel(self, surface, state):
        panel_rect = pygame.Rect(
            _STATUS_RECT_X, _STATUS_RECT_Y,
            _STATUS_RECT_W, _STATUS_RECT_H,
        )
        Panel(panel_rect).draw(surface)

        inner_x = panel_rect.x + PADDING
        inner_w = panel_rect.width - 2 * PADDING
        bar_h = 14
        gap = 4
        y = panel_rect.y + PADDING

        # Health bar
        hp_ratio = max(0.0, min(1.0, state.hp / max(state.max_hp, 1)))
        if hp_ratio > 0.5:
            hp_color = ACCENT_GREEN
        elif hp_ratio > 0.3:
            hp_color = ACCENT_AMBER
        else:
            hp_color = DANGER_RED

        hp_bar = ProgressBar(
            rect=pygame.Rect(inner_x, y, inner_w, bar_h),
            value=state.hp, max_value=state.max_hp,
            fill_color=hp_color, bg_color=(30, 34, 50),
            border_color=BORDER_DIM, show_text=True,
            font=self._font_sm, text_color=TEXT_PRIMARY,
        )
        hp_bar.draw(surface)
        y += bar_h + gap

        # Armor bar
        armor_bar = ProgressBar(
            rect=pygame.Rect(inner_x, y, inner_w, bar_h),
            value=state.armor, max_value=max(state.max_armor, 1),
            fill_color=ACCENT_CYAN, bg_color=(30, 34, 50),
            border_color=BORDER_DIM, show_text=False,
        )
        armor_bar.draw(surface)
        y += bar_h + gap

        # XP bar
        xp_bar = ProgressBar(
            rect=pygame.Rect(inner_x, y, inner_w - 40, 8),
            value=state.xp, max_value=state.xp + max(state.xp_to_next, 1),
            fill_color=ACCENT_AMBER, bg_color=(30, 34, 50),
            border_color=BORDER_DIM, show_text=False,
        )
        xp_bar.draw(surface)

        lvl_label = Label(
            text=f'LV{state.level}', font=self._font_md,
            color=ACCENT_AMBER, pos=(inner_x + inner_w, y + 4),
            anchor='midright',
        )
        lvl_label.draw(surface)

    def _draw_buffs(self, surface, state):
        if not state.active_buffs:
            return
        buff_y = _STATUS_RECT_Y + _STATUS_RECT_H + MARGIN
        slot_size = 36
        gap = 4
        x = _STATUS_RECT_X

        for buff in state.active_buffs[:6]:
            slot_rect = pygame.Rect(x, buff_y, slot_size, slot_size)
            selected = buff.seconds_left < _BUFF_PULSE_THRESHOLD
            slot = IconSlot(
                rect=slot_rect, icon=buff.icon, label='',
                hotkey='', count=0, font=self._font_sm, selected=selected,
            )
            slot.draw(surface)
            timer_txt = f'{buff.seconds_left:.0f}s'
            timer_surf = self._font_sm.render(timer_txt, True, TEXT_SECONDARY)
            surface.blit(timer_surf, (
                x + slot_size // 2 - timer_surf.get_width() // 2,
                buff_y + slot_size + 2,
            ))
            x += slot_size + gap

    def _draw_timer(self, surface, state):
        secs = max(0, int(state.seconds_remaining))
        mm = secs // 60
        ss = secs % 60
        timer_str = f'{mm:02d}:{ss:02d}'

        if state.seconds_remaining > 120:
            color = TEXT_PRIMARY
        elif state.seconds_remaining > 30:
            color = ACCENT_AMBER
        else:
            color = DANGER_RED

        panel_rect = pygame.Rect(
            _TIMER_RECT_X, _TIMER_RECT_Y, _TIMER_RECT_W, _TIMER_RECT_H,
        )
        Panel(panel_rect).draw(surface)
        timer_label = Label(
            text=timer_str, font=self._font_lg, color=color,
            pos=panel_rect.center, anchor='center',
        )
        timer_label.draw(surface)

    def _draw_weapon(self, surface, state):
        panel_rect = pygame.Rect(
            _WEAPON_RECT_X, _WEAPON_RECT_Y, _WEAPON_RECT_W, _WEAPON_RECT_H,
        )
        Panel(panel_rect).draw(surface)

        if state.equipped_weapon is None:
            no_weapon = Label(
                text='-- NO WEAPON --', font=self._font_sm,
                color=TEXT_SECONDARY, pos=panel_rect.center, anchor='center',
            )
            no_weapon.draw(surface)
            return

        weapon = state.equipped_weapon
        icon_rect = pygame.Rect(
            panel_rect.x + PADDING,
            panel_rect.y + (panel_rect.height - 40) // 2,
            40, 40,
        )
        if weapon.icon:
            try:
                scaled = pygame.transform.scale(weapon.icon, (40, 40))
                surface.blit(scaled, icon_rect)
            except Exception:
                pygame.draw.rect(surface, BORDER_DIM, icon_rect, border_radius=4)
        else:
            pygame.draw.rect(surface, BORDER_DIM, icon_rect, border_radius=4)

        text_x = icon_rect.right + 6
        name_label = Label(
            text=weapon.name[:12], font=self._font_sm,
            color=TEXT_PRIMARY, pos=(text_x, panel_rect.y + PADDING),
            anchor='topleft',
        )
        name_label.draw(surface)

        ammo_str = f'{weapon.ammo_current} / {weapon.ammo_reserve}'
        ammo_color = DANGER_RED if weapon.ammo_current <= 3 else TEXT_PRIMARY
        ammo_label = Label(
            text=ammo_str, font=self._font_md,
            color=ammo_color, pos=(text_x, panel_rect.y + PADDING + 16),
            anchor='topleft',
        )
        ammo_label.draw(surface)

    def _draw_quickslots(self, surface, state):
        slots = list(state.consumable_slots) + [None] * _QUICKSLOT_COUNT
        slots = slots[:_QUICKSLOT_COUNT]

        for i, slot_data in enumerate(slots):
            x = _QUICKSLOTS_X + i * (_QUICKSLOT_SIZE + _QUICKSLOT_GAP)
            slot_rect = pygame.Rect(x, _QUICKSLOTS_Y, _QUICKSLOT_SIZE, _QUICKSLOT_SIZE)
            icon = slot_data.icon if slot_data else None
            count = slot_data.count if slot_data else 0
            icon_slot = IconSlot(
                rect=slot_rect, icon=icon, label='',
                hotkey=str(i + 1), count=count, font=self._font_sm,
            )
            icon_slot.draw(surface)

    def _draw_damage_vignette(self, surface):
        intensity = self._damage_flash_timer / _DAMAGE_FLASH_DURATION
        alpha = int(180 * intensity)
        if alpha <= 0:
            return
        vignette = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        border = 60
        pygame.draw.rect(vignette, (255, 32, 64, alpha),
                         pygame.Rect(0, 0, SCREEN_W, border))
        pygame.draw.rect(vignette, (255, 32, 64, alpha),
                         pygame.Rect(0, SCREEN_H - border, SCREEN_W, border))
        pygame.draw.rect(vignette, (255, 32, 64, alpha),
                         pygame.Rect(0, 0, border, SCREEN_H))
        pygame.draw.rect(vignette, (255, 32, 64, alpha),
                         pygame.Rect(SCREEN_W - border, 0, border, SCREEN_H))
        surface.blit(vignette, (0, 0))

    def _draw_levelup_banner(self, surface):
        alpha = int(255 * min(1.0, self._levelup_banner_timer / _LEVELUP_BANNER_DURATION))
        if alpha <= 0:
            return
        banner_w, banner_h = 300, 60
        banner_x = SCREEN_W // 2 - banner_w // 2
        banner_y = SCREEN_H // 2 - banner_h // 2 - 80
        panel_rect = pygame.Rect(banner_x, banner_y, banner_w, banner_h)
        Panel(panel_rect, bg_color=(0, 30, 0), border_color=ACCENT_GREEN, alpha=alpha).draw(surface)
        lvl_text = f'LEVEL UP!  LV {self._state.level}'
        font_banner = pygame.font.SysFont('monospace', 22, bold=True)
        banner_surf = font_banner.render(lvl_text, True, ACCENT_GREEN)
        blit_x = banner_x + banner_w // 2 - banner_surf.get_width() // 2
        blit_y = banner_y + banner_h // 2 - banner_surf.get_height() // 2
        if alpha < 255:
            banner_surf.set_alpha(alpha)
        surface.blit(banner_surf, (blit_x, blit_y))
