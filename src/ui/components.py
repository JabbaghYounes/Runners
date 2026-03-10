"""Reusable UI widgets: bars, labels, buttons, timer, extraction progress."""

from __future__ import annotations

import math

import pygame

# Colours
TEXT_PRIMARY = (224, 224, 224)     # #E0E0E0
TEXT_SECONDARY = (158, 158, 158)  # #9E9E9E
ACCENT_CYAN = (0, 229, 255)       # #00E5FF
ACCENT_RED = (255, 23, 68)        # #FF1744
ACCENT_GREEN = (105, 240, 174)    # #69F0AE
ACCENT_GOLD = (255, 215, 64)      # #FFD740
BG_DARK = (10, 14, 23)
PANEL_BG = (18, 24, 38)
BAR_BG = (30, 38, 56)


class RoundTimer:
    """Displays the round countdown timer at the top-centre of the screen.

    Format: ``MM:SS``.  Pulses red when < 60 s, faster pulse when < 30 s.
    """

    def __init__(self, x: int = 640, y: int = 16) -> None:
        self.x = x
        self.y = y
        self._remaining = 900.0
        self._total = 900.0
        self._warning = False
        self._critical = False
        self._anim_time = 0.0

        # Font (lazy init)
        self._font: pygame.font.Font | None = None

    def _ensure_font(self) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 20, bold=True)

    def set_time(self, remaining: float, total: float) -> None:
        """Update the displayed time."""
        self._remaining = max(0.0, remaining)
        self._total = total
        self._warning = remaining < 60.0
        self._critical = remaining < 30.0

    def update(self, dt: float) -> None:
        self._anim_time += dt

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_font()

        minutes = int(self._remaining) // 60
        seconds = int(self._remaining) % 60
        text = f"{minutes:02d}:{seconds:02d}"

        # Determine colour and pulse
        if self._critical:
            # Fast pulse + scale throb at < 30s
            pulse = 0.5 + 0.5 * math.sin(self._anim_time * 8.0)
            color = ACCENT_RED
            alpha = int(160 + 95 * pulse)
            scale = 1.0 + 0.05 * pulse
        elif self._warning:
            # Slower pulse at < 60s
            pulse = 0.5 + 0.5 * math.sin(self._anim_time * 4.0)
            color = ACCENT_RED
            alpha = int(180 + 75 * pulse)
            scale = 1.0
        else:
            color = TEXT_PRIMARY
            alpha = 255
            scale = 1.0

        text_surface = self._font.render(text, True, color)

        if scale != 1.0:
            new_w = int(text_surface.get_width() * scale)
            new_h = int(text_surface.get_height() * scale)
            text_surface = pygame.transform.scale(text_surface, (new_w, new_h))

        # Apply alpha
        if alpha < 255:
            text_surface.set_alpha(alpha)

        # Centre horizontally
        draw_x = self.x - text_surface.get_width() // 2
        surface.blit(text_surface, (draw_x, self.y))


class ExtractionProgressBar:
    """Centred progress bar shown during the extraction channel.

    Dimensions: 300 x 24 px, fill colour accent-cyan.
    Label "EXTRACTING..." appears above the bar.
    """

    WIDTH = 300
    HEIGHT = 24

    def __init__(self, screen_width: int = 1280, screen_height: int = 720) -> None:
        self._screen_w = screen_width
        self._screen_h = screen_height
        self._progress = 0.0     # 0.0 to 1.0
        self._visible = False
        self._anim_time = 0.0

        # Font (lazy init)
        self._font: pygame.font.Font | None = None

    def _ensure_font(self) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 14, bold=True)

    def set_visible(self, visible: bool) -> None:
        self._visible = visible

    def set_progress(self, progress: float, duration: float) -> None:
        """Update progress (seconds elapsed / total duration)."""
        self._progress = min(progress / duration, 1.0) if duration > 0 else 0.0

    def update(self, dt: float) -> None:
        self._anim_time += dt

    def draw(self, surface: pygame.Surface) -> None:
        if not self._visible:
            return

        self._ensure_font()

        x = self._screen_w // 2 - self.WIDTH // 2
        y = self._screen_h // 2 + 60

        # "EXTRACTING..." label
        label = self._font.render("EXTRACTING...", True, ACCENT_CYAN)
        surface.blit(label, (x + self.WIDTH // 2 - label.get_width() // 2, y - 22))

        # Bar background
        pygame.draw.rect(surface, BAR_BG, (x, y, self.WIDTH, self.HEIGHT), border_radius=4)

        # Bar fill
        fill_w = int(self.WIDTH * self._progress)
        if fill_w > 0:
            # Slight shimmer effect
            pulse = 0.9 + 0.1 * math.sin(self._anim_time * 6.0)
            fill_color = tuple(int(c * pulse) for c in ACCENT_CYAN)
            pygame.draw.rect(
                surface, fill_color, (x, y, fill_w, self.HEIGHT), border_radius=4
            )

        # Border
        pygame.draw.rect(
            surface, ACCENT_CYAN, (x, y, self.WIDTH, self.HEIGHT), width=1, border_radius=4
        )


class ExtractionPrompt:
    """Floating "Press E - Extract" text that appears when near an extraction zone.

    Positioned at bottom-centre (y = screen_height - 200).
    Fades in and out smoothly.
    """

    FADE_SPEED = 4.0  # alpha units per second (0-1 scale)

    def __init__(self, screen_width: int = 1280, screen_height: int = 720) -> None:
        self._screen_w = screen_width
        self._screen_h = screen_height
        self._target_alpha = 0.0   # 0 = hidden, 1 = fully visible
        self._current_alpha = 0.0
        self._anim_time = 0.0

        self._font: pygame.font.Font | None = None

    def _ensure_font(self) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 18, bold=True)

    def set_visible(self, visible: bool) -> None:
        self._target_alpha = 1.0 if visible else 0.0

    def update(self, dt: float) -> None:
        self._anim_time += dt
        # Lerp toward target alpha
        if self._current_alpha < self._target_alpha:
            self._current_alpha = min(
                self._current_alpha + self.FADE_SPEED * dt, self._target_alpha
            )
        elif self._current_alpha > self._target_alpha:
            self._current_alpha = max(
                self._current_alpha - self.FADE_SPEED * dt, self._target_alpha
            )

    def draw(self, surface: pygame.Surface) -> None:
        if self._current_alpha <= 0.01:
            return

        self._ensure_font()

        text = "Press E \u2014 Extract"
        text_surface = self._font.render(text, True, ACCENT_CYAN)
        text_surface.set_alpha(int(self._current_alpha * 255))

        x = self._screen_w // 2 - text_surface.get_width() // 2
        y = self._screen_h - 200
        surface.blit(text_surface, (x, y))


class HealthBar:
    """Horizontal health bar at top-left.  Lerps smoothly on damage."""

    WIDTH = 200
    HEIGHT = 16

    def __init__(self, x: int = 16, y: int = 16) -> None:
        self.x = x
        self.y = y
        self._current = 1.0     # displayed ratio (lerps toward target)
        self._target = 1.0      # actual health ratio
        self._lerp_speed = 3.0

        self._font: pygame.font.Font | None = None

    def _ensure_font(self) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 12)

    def set_health(self, current: int, maximum: int) -> None:
        self._target = current / maximum if maximum > 0 else 0.0

    def update(self, dt: float) -> None:
        diff = self._target - self._current
        self._current += diff * min(self._lerp_speed * dt, 1.0)

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_font()

        # Background
        pygame.draw.rect(surface, BAR_BG, (self.x, self.y, self.WIDTH, self.HEIGHT), border_radius=3)

        # Fill
        fill_w = int(self.WIDTH * max(0, self._current))
        if fill_w > 0:
            color = ACCENT_GREEN if self._current > 0.3 else ACCENT_RED
            pygame.draw.rect(surface, color, (self.x, self.y, fill_w, self.HEIGHT), border_radius=3)

        # Border
        pygame.draw.rect(
            surface, TEXT_SECONDARY, (self.x, self.y, self.WIDTH, self.HEIGHT),
            width=1, border_radius=3,
        )


class XPBar:
    """XP progress bar below the health bar."""

    WIDTH = 200
    HEIGHT = 10

    def __init__(self, x: int = 16, y: int = 36) -> None:
        self.x = x
        self.y = y
        self._progress = 0.0
        self._level = 1

        self._font: pygame.font.Font | None = None

    def _ensure_font(self) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 11)

    def set_xp(self, progress: float, level: int) -> None:
        self._progress = max(0.0, min(1.0, progress))
        self._level = level

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_font()

        pygame.draw.rect(surface, BAR_BG, (self.x, self.y, self.WIDTH, self.HEIGHT), border_radius=2)

        fill_w = int(self.WIDTH * self._progress)
        if fill_w > 0:
            pygame.draw.rect(
                surface, ACCENT_GREEN, (self.x, self.y, fill_w, self.HEIGHT), border_radius=2
            )

        pygame.draw.rect(
            surface, TEXT_SECONDARY, (self.x, self.y, self.WIDTH, self.HEIGHT),
            width=1, border_radius=2,
        )

        label = self._font.render(f"Lv.{self._level}", True, TEXT_PRIMARY)
        surface.blit(label, (self.x + self.WIDTH + 6, self.y - 1))
