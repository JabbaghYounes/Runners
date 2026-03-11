import pygame
from typing import Optional, Callable, List, Tuple
from src.constants import (PANEL_BG, BORDER_DIM, BORDER_BRIGHT, TEXT_BRIGHT,
                            TEXT_DIM, ACCENT_CYAN, ACCENT_GREEN, ACCENT_RED)

class Panel:
    def __init__(self, rect: pygame.Rect, bg_color=PANEL_BG,
                 border_color=BORDER_DIM, border_radius: int = 4):
        self.rect = rect
        self.bg_color = bg_color
        self.border_color = border_color
        self.border_radius = border_radius

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, self.bg_color, self.rect, border_radius=self.border_radius)
        pygame.draw.rect(surface, self.border_color, self.rect, 1, border_radius=self.border_radius)

class Label:
    def __init__(self, text: str, x: int, y: int, font: Optional[pygame.font.Font] = None,
                 color=TEXT_BRIGHT, center: bool = False):
        self.text = text
        self.x = x
        self.y = y
        self.font = font or pygame.font.Font(None, 20)
        self.color = color
        self.center = center

    def draw(self, surface: pygame.Surface) -> None:
        surf = self.font.render(self.text, True, self.color)
        if self.center:
            surface.blit(surf, (self.x - surf.get_width() // 2, self.y))
        else:
            surface.blit(surf, (self.x, self.y))

class Button:
    STYLES = {
        'primary':   {'bg': (20, 80, 140),  'hover': (30, 120, 200), 'text': TEXT_BRIGHT},
        'secondary': {'bg': (30, 40, 60),   'hover': (50, 70, 100),  'text': TEXT_BRIGHT},
        'danger':    {'bg': (140, 30, 30),  'hover': (200, 50, 50),  'text': TEXT_BRIGHT},
        'ghost':     {'bg': (0, 0, 0, 0),   'hover': (40, 60, 80),   'text': ACCENT_CYAN},
    }

    def __init__(self, rect: pygame.Rect, text: str, style: str = 'primary',
                 on_click: Optional[Callable] = None,
                 font: Optional[pygame.font.Font] = None):
        self.rect = rect
        self.text = text
        self.style = self.STYLES.get(style, self.STYLES['primary'])
        self.on_click = on_click
        self.font = font or pygame.font.Font(None, 22)
        self._hovered = False
        self._pressed = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._pressed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._pressed and self.rect.collidepoint(event.pos):
                self._pressed = False
                if self.on_click:
                    self.on_click()
                return True
            self._pressed = False
        return False

    def draw(self, surface: pygame.Surface) -> None:
        color = self.style['hover'] if self._hovered else self.style['bg']
        if isinstance(color, tuple) and len(color) == 4 and color[3] == 0:
            pass
        else:
            pygame.draw.rect(surface, color, self.rect, border_radius=4)
        if self._hovered:
            pygame.draw.rect(surface, BORDER_BRIGHT, self.rect, 1, border_radius=4)
        text_surf = self.font.render(self.text, True, self.style['text'])
        tx = self.rect.x + self.rect.w // 2 - text_surf.get_width() // 2
        ty = self.rect.y + self.rect.h // 2 - text_surf.get_height() // 2
        surface.blit(text_surf, (tx, ty))

class ProgressBar:
    def __init__(self, rect: pygame.Rect, color=ACCENT_GREEN,
                 bg_color=(30, 40, 50), border_color=BORDER_DIM):
        self.rect = rect
        self.color = color
        self.bg_color = bg_color
        self.border_color = border_color
        self.value: float = 1.0  # 0-1

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, self.bg_color, self.rect)
        fill_w = int(self.rect.w * max(0.0, min(1.0, self.value)))
        if fill_w > 0:
            fill_rect = pygame.Rect(self.rect.x, self.rect.y, fill_w, self.rect.h)
            pygame.draw.rect(surface, self.color, fill_rect)
        pygame.draw.rect(surface, self.border_color, self.rect, 1)

class Slider:
    def __init__(self, rect: pygame.Rect, min_val: float = 0.0, max_val: float = 1.0,
                 value: float = 0.5, on_change: Optional[Callable] = None):
        self.rect = rect
        self.min_val = min_val
        self.max_val = max_val
        self.value = value
        self.on_change = on_change
        self._dragging = False

    @property
    def normalized(self) -> float:
        return (self.value - self.min_val) / max(0.001, self.max_val - self.min_val)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._dragging = True
                self._update_value(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._dragging = False
        elif event.type == pygame.MOUSEMOTION and self._dragging:
            self._update_value(event.pos[0])

    def _update_value(self, mx: int) -> None:
        pct = (mx - self.rect.x) / max(1, self.rect.w)
        pct = max(0.0, min(1.0, pct))
        self.value = self.min_val + pct * (self.max_val - self.min_val)
        if self.on_change:
            self.on_change(self.value)

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, (30, 40, 50), self.rect)
        knob_x = self.rect.x + int(self.normalized * self.rect.w)
        knob_rect = pygame.Rect(knob_x - 6, self.rect.y - 4, 12, self.rect.h + 8)
        pygame.draw.rect(surface, ACCENT_CYAN, knob_rect, border_radius=3)
        pygame.draw.rect(surface, BORDER_DIM, self.rect, 1)

class ConfirmDialog:
    def __init__(self, message: str, on_confirm: Callable, on_cancel: Callable,
                 screen_w: int = 1280, screen_h: int = 720):
        self.message = message
        self._font = None
        w, h = 400, 200
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.rect = pygame.Rect(x, y, w, h)
        self.confirm_btn = Button(
            pygame.Rect(x + 40, y + 130, 140, 44), "CONFIRM", 'danger', on_confirm
        )
        self.cancel_btn = Button(
            pygame.Rect(x + 220, y + 130, 140, 44), "CANCEL", 'secondary', on_cancel
        )

    def handle_event(self, event: pygame.event.Event) -> bool:
        self.confirm_btn.handle_event(event)
        self.cancel_btn.handle_event(event)
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if self._font is None:
            self._font = pygame.font.Font(None, 22)
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))
        pygame.draw.rect(surface, PANEL_BG, self.rect, border_radius=8)
        pygame.draw.rect(surface, BORDER_BRIGHT, self.rect, 2, border_radius=8)
        msg_surf = self._font.render(self.message, True, TEXT_BRIGHT)
        surface.blit(msg_surf, (self.rect.centerx - msg_surf.get_width() // 2,
                                self.rect.y + 60))
        self.confirm_btn.draw(surface)
        self.cancel_btn.draw(surface)
