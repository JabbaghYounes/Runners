import pygame
import math
from typing import Optional, Any
from src.ui.hud_state import HUDState
from src.ui.mini_map import MiniMap
from src.ui.widgets import ProgressBar
from src.constants import (
    SCREEN_W, SCREEN_H, PANEL_BG, BORDER_DIM, BORDER_BRIGHT,
    ACCENT_CYAN, ACCENT_GREEN, ACCENT_MAGENTA, ACCENT_RED, ACCENT_ORANGE,
    HEALTH_COLOR, ARMOR_COLOR, XP_COLOR, TEXT_BRIGHT, TEXT_DIM
)

class HUD:
    def __init__(self, event_bus: Any):
        self._event_bus = event_bus
        self._font_sm: Optional[pygame.font.Font] = None
        self._font_md: Optional[pygame.font.Font] = None
        self._font_lg: Optional[pygame.font.Font] = None
        self._state: Optional[HUDState] = None
        self._vignette_timer: float = 0.0
        self._level_up_timer: float = 0.0
        self._zone_label: str = ''
        self._zone_label_timer: float = 0.0
        self._mini_map = MiniMap(pygame.Rect(SCREEN_W - 132, 8, 124, 124))

        event_bus.subscribe('player.damaged', self._on_damaged)
        event_bus.subscribe('level.up', self._on_level_up)
        event_bus.subscribe('zone_entered', self._on_zone_entered)

    def _ensure_fonts(self) -> None:
        if self._font_sm is None:
            self._font_sm = pygame.font.Font(None, 16)
            self._font_md = pygame.font.Font(None, 20)
            self._font_lg = pygame.font.Font(None, 28)

    def _on_damaged(self, **kwargs: Any) -> None:
        self._vignette_timer = 0.5

    def _on_level_up(self, **kwargs: Any) -> None:
        self._level_up_timer = 3.0

    def _on_zone_entered(self, **kwargs: Any) -> None:
        zone = kwargs.get('zone')
        if zone:
            self._zone_label = zone.name
            self._zone_label_timer = 2.5

    def update(self, state: HUDState, dt: float) -> None:
        self._state = state
        self._vignette_timer = max(0.0, self._vignette_timer - dt)
        self._level_up_timer = max(0.0, self._level_up_timer - dt)
        self._zone_label_timer = max(0.0, self._zone_label_timer - dt)
        self._mini_map.update(state)

    def draw(self, surface: pygame.Surface) -> None:
        if self._state is None:
            return
        self._ensure_fonts()
        st = self._state

        # === Status panel (top-left) ===
        panel_rect = pygame.Rect(8, 8, 220, 100)
        pygame.draw.rect(surface, PANEL_BG, panel_rect, border_radius=4)
        pygame.draw.rect(surface, BORDER_DIM, panel_rect, 1, border_radius=4)

        # HP bar
        hp_label = self._font_sm.render(f"HP  {st.hp}/{st.max_hp}", True, HEALTH_COLOR)
        surface.blit(hp_label, (16, 16))
        hp_bar = ProgressBar(pygame.Rect(16, 30, 200, 10), color=HEALTH_COLOR)
        hp_bar.value = st.hp / max(1, st.max_hp)
        hp_bar.draw(surface)

        # Armor bar
        ar_label = self._font_sm.render(f"ARM {st.armor}/{st.max_armor}", True, ARMOR_COLOR)
        surface.blit(ar_label, (16, 44))
        ar_bar = ProgressBar(pygame.Rect(16, 58, 200, 8), color=ARMOR_COLOR)
        ar_bar.value = st.armor / max(1, st.max_armor)
        ar_bar.draw(surface)

        # XP bar
        xp_label = self._font_sm.render(f"LVL {st.level}  XP {st.xp}/{st.xp_to_next}", True, XP_COLOR)
        surface.blit(xp_label, (16, 70))
        xp_bar = ProgressBar(pygame.Rect(16, 84, 200, 6), color=XP_COLOR)
        xp_bar.value = st.xp / max(1, st.xp_to_next)
        xp_bar.draw(surface)

        # === Timer + Zone (top-center) ===
        mins = int(st.seconds_remaining) // 60
        secs = int(st.seconds_remaining) % 60
        timer_str = f"{mins:02d}:{secs:02d}"
        t_color = ACCENT_RED if st.seconds_remaining < 60 else TEXT_BRIGHT
        timer_surf = self._font_lg.render(timer_str, True, t_color)
        surface.blit(timer_surf, (SCREEN_W // 2 - timer_surf.get_width() // 2, 10))

        # === Mini-map (top-right) ===
        self._mini_map.draw(surface)

        # === Weapon info (bottom-left) ===
        if st.equipped_weapon:
            wep_rect = pygame.Rect(8, SCREEN_H - 70, 200, 60)
            pygame.draw.rect(surface, PANEL_BG, wep_rect, border_radius=4)
            pygame.draw.rect(surface, BORDER_DIM, wep_rect, 1, border_radius=4)
            wn = self._font_md.render(st.equipped_weapon.name, True, TEXT_BRIGHT)
            surface.blit(wn, (16, SCREEN_H - 62))
            ammo = self._font_sm.render(
                f"{st.equipped_weapon.ammo} / {st.equipped_weapon.max_ammo}", True, TEXT_DIM)
            surface.blit(ammo, (16, SCREEN_H - 44))

        # === Extraction prompt ===
        if st.in_extraction_zone:
            prompt_surf = self._font_md.render("Hold E to Extract", True, ACCENT_GREEN)
            px = SCREEN_W // 2 - prompt_surf.get_width() // 2
            surface.blit(prompt_surf, (px, SCREEN_H - 100))
            if st.extraction_progress > 0:
                bar = ProgressBar(pygame.Rect(px, SCREEN_H - 82, prompt_surf.get_width(), 8),
                                  color=ACCENT_GREEN)
                bar.value = st.extraction_progress
                bar.draw(surface)

        # === Zone label flash ===
        if self._zone_label_timer > 0:
            alpha = min(255, int(self._zone_label_timer / 2.5 * 255))
            zone_surf = self._font_lg.render(f"— {self._zone_label} —", True, ACCENT_CYAN)
            zx = SCREEN_W // 2 - zone_surf.get_width() // 2
            zy = SCREEN_H // 2 - 80
            zone_surf.set_alpha(alpha)
            surface.blit(zone_surf, (zx, zy))

        # === Level up banner ===
        if self._level_up_timer > 0:
            lu_surf = self._font_lg.render(f"LEVEL UP!  -> {st.level}", True, ACCENT_ORANGE)
            lx = SCREEN_W // 2 - lu_surf.get_width() // 2
            ly = SCREEN_H // 2 - 50
            surface.blit(lu_surf, (lx, ly))

        # === Vignette ===
        if self._vignette_timer > 0:
            alpha = int(self._vignette_timer / 0.5 * 100)
            vig = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            pygame.draw.rect(vig, (200, 0, 0, alpha), (0, 0, SCREEN_W, SCREEN_H))
            surface.blit(vig, (0, 0))
