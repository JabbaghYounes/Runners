"""Unit tests for HUD widget primitives: Panel, ProgressBar, IconSlot, Label.

All rendering calls use a real pygame surface (1280×720 mode is initialised
once per session) so we exercise actual drawing code without needing a display.
"""
from __future__ import annotations

import pytest
import pygame


# ---------------------------------------------------------------------------
# Session-scoped pygame init (no display window)
# ---------------------------------------------------------------------------
@pytest.fixture(scope='session', autouse=True)
def pygame_headless():
    pygame.display.init()
    pygame.font.init()
    yield
    pygame.quit()


@pytest.fixture
def surface():
    """A 200×200 surface to draw onto."""
    return pygame.Surface((200, 200))


# ---------------------------------------------------------------------------
# ProgressBar
# ---------------------------------------------------------------------------
class TestProgressBar:
    def test_fill_ratio_at_full_value(self, surface):
        from src.ui.widgets import ProgressBar
        bar = ProgressBar(
            rect=pygame.Rect(0, 0, 100, 10),
            value=100,
            max_value=100,
            fill_color=(0, 255, 0),
            bg_color=(0, 0, 0),
        )
        assert bar.fill_ratio == pytest.approx(1.0)

    def test_fill_ratio_at_zero_value(self, surface):
        from src.ui.widgets import ProgressBar
        bar = ProgressBar(
            rect=pygame.Rect(0, 0, 100, 10),
            value=0,
            max_value=100,
            fill_color=(0, 255, 0),
            bg_color=(0, 0, 0),
        )
        assert bar.fill_ratio == pytest.approx(0.0)

    def test_fill_ratio_at_half_value(self, surface):
        from src.ui.widgets import ProgressBar
        bar = ProgressBar(
            rect=pygame.Rect(0, 0, 100, 10),
            value=50,
            max_value=100,
            fill_color=(0, 255, 0),
            bg_color=(0, 0, 0),
        )
        assert bar.fill_ratio == pytest.approx(0.5)

    def test_fill_ratio_clamped_above_max(self, surface):
        from src.ui.widgets import ProgressBar
        bar = ProgressBar(
            rect=pygame.Rect(0, 0, 100, 10),
            value=200,
            max_value=100,
            fill_color=(0, 255, 0),
            bg_color=(0, 0, 0),
        )
        assert bar.fill_ratio == pytest.approx(1.0)

    def test_fill_ratio_clamped_below_zero(self, surface):
        from src.ui.widgets import ProgressBar
        bar = ProgressBar(
            rect=pygame.Rect(0, 0, 100, 10),
            value=-10,
            max_value=100,
            fill_color=(0, 255, 0),
            bg_color=(0, 0, 0),
        )
        assert bar.fill_ratio == pytest.approx(0.0)

    def test_draw_does_not_raise(self, surface):
        from src.ui.widgets import ProgressBar
        bar = ProgressBar(
            rect=pygame.Rect(10, 10, 80, 12),
            value=60,
            max_value=100,
            fill_color=(57, 255, 20),
            bg_color=(20, 24, 38),
        )
        bar.draw(surface)  # must not raise

    def test_draw_with_text_does_not_raise(self, surface):
        from src.ui.widgets import ProgressBar
        font = pygame.font.SysFont('monospace', 11)
        bar = ProgressBar(
            rect=pygame.Rect(10, 10, 80, 14),
            value=75,
            max_value=100,
            fill_color=(0, 245, 255),
            bg_color=(30, 30, 30),
            show_text=True,
            font=font,
        )
        bar.draw(surface)

    def test_show_text_false_no_font_needed(self, surface):
        from src.ui.widgets import ProgressBar
        bar = ProgressBar(
            rect=pygame.Rect(0, 0, 50, 8),
            value=25,
            max_value=50,
            fill_color=(255, 184, 0),
            bg_color=(20, 20, 20),
            show_text=False,
            font=None,  # no font — should not crash
        )
        bar.draw(surface)


# ---------------------------------------------------------------------------
# IconSlot
# ---------------------------------------------------------------------------
class TestIconSlot:
    def test_draw_empty_slot_does_not_raise(self, surface):
        from src.ui.widgets import IconSlot
        slot = IconSlot(
            rect=pygame.Rect(0, 0, 48, 48),
            icon=None,
        )
        slot.draw(surface)

    def test_draw_with_hotkey_does_not_raise(self, surface):
        from src.ui.widgets import IconSlot
        font = pygame.font.SysFont('monospace', 11)
        slot = IconSlot(
            rect=pygame.Rect(0, 0, 48, 48),
            icon=None,
            hotkey='1',
            font=font,
        )
        slot.draw(surface)

    def test_draw_selected_slot_does_not_raise(self, surface):
        from src.ui.widgets import IconSlot
        slot = IconSlot(
            rect=pygame.Rect(0, 0, 48, 48),
            icon=None,
            selected=True,
        )
        slot.draw(surface)

    def test_empty_color_stored(self):
        from src.ui.widgets import IconSlot
        color = (55, 60, 80)
        slot = IconSlot(
            rect=pygame.Rect(0, 0, 48, 48),
            empty_color=color,
        )
        assert slot.empty_color == color

    def test_count_badge_draws_when_count_positive(self, surface):
        from src.ui.widgets import IconSlot
        font = pygame.font.SysFont('monospace', 11)
        slot = IconSlot(
            rect=pygame.Rect(0, 0, 48, 48),
            count=3,
            font=font,
        )
        slot.draw(surface)  # must not raise

    def test_rect_stored(self):
        from src.ui.widgets import IconSlot
        rect = pygame.Rect(10, 20, 48, 48)
        slot = IconSlot(rect=rect)
        assert slot.rect == rect

    def test_label_stored(self):
        from src.ui.widgets import IconSlot
        slot = IconSlot(rect=pygame.Rect(0, 0, 48, 48), label='MedKit')
        assert slot.label == 'MedKit'


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------
class TestPanel:
    def test_draw_does_not_raise(self, surface):
        from src.ui.widgets import Panel
        panel = Panel(rect=pygame.Rect(5, 5, 100, 60))
        panel.draw(surface)

    def test_bg_color_stored(self):
        from src.ui.widgets import Panel
        color = (10, 20, 30)
        panel = Panel(rect=pygame.Rect(0, 0, 50, 50), bg_color=color)
        assert panel.bg_color == color

    def test_border_color_stored(self):
        from src.ui.widgets import Panel
        color = (0, 255, 0)
        panel = Panel(rect=pygame.Rect(0, 0, 50, 50), border_color=color)
        assert panel.border_color == color

    def test_corner_radius_stored(self):
        from src.ui.widgets import Panel
        panel = Panel(rect=pygame.Rect(0, 0, 50, 50), corner_radius=10)
        assert panel.corner_radius == 10

    def test_draw_with_zero_border_does_not_raise(self, surface):
        from src.ui.widgets import Panel
        panel = Panel(
            rect=pygame.Rect(0, 0, 80, 40),
            border_width=0,
        )
        panel.draw(surface)


# ---------------------------------------------------------------------------
# Label
# ---------------------------------------------------------------------------
class TestLabel:
    def test_draw_does_not_raise(self, surface):
        from src.ui.widgets import Label
        font = pygame.font.SysFont('monospace', 14)
        label = Label(
            text='TEST',
            font=font,
            color=(255, 255, 255),
            pos=(10, 10),
        )
        label.draw(surface)

    def test_text_stored(self):
        from src.ui.widgets import Label
        font = pygame.font.SysFont('monospace', 14)
        label = Label(text='Hello', font=font, color=(255, 255, 255), pos=(0, 0))
        assert label.text == 'Hello'

    def test_color_stored(self):
        from src.ui.widgets import Label
        font = pygame.font.SysFont('monospace', 14)
        color = (255, 100, 0)
        label = Label(text='X', font=font, color=color, pos=(0, 0))
        assert label.color == color

    def test_anchor_center_does_not_raise(self, surface):
        from src.ui.widgets import Label
        font = pygame.font.SysFont('monospace', 14)
        label = Label(
            text='CENTERED',
            font=font,
            color=(0, 255, 255),
            pos=(100, 100),
            anchor='center',
        )
        label.draw(surface)

    def test_anchor_midright_does_not_raise(self, surface):
        from src.ui.widgets import Label
        font = pygame.font.SysFont('monospace', 12)
        label = Label(
            text='RIGHT',
            font=font,
            color=(255, 255, 0),
            pos=(190, 50),
            anchor='midright',
        )
        label.draw(surface)

    def test_anchor_bottomright_does_not_raise(self, surface):
        from src.ui.widgets import Label
        font = pygame.font.SysFont('monospace', 12)
        label = Label(
            text='BR',
            font=font,
            color=(0, 255, 0),
            pos=(190, 190),
            anchor='bottomright',
        )
        label.draw(surface)


# ---------------------------------------------------------------------------
# ProgressBar — additional edge cases
# ---------------------------------------------------------------------------
class TestProgressBarEdgeCases:
    def test_max_value_zero_does_not_raise_on_construction(self):
        """max_value=0 is clamped internally to a tiny epsilon; must not raise."""
        from src.ui.widgets import ProgressBar
        bar = ProgressBar(
            rect=pygame.Rect(0, 0, 100, 10),
            value=0,
            max_value=0,
            fill_color=(0, 255, 0),
            bg_color=(0, 0, 0),
        )
        assert 0.0 <= bar.fill_ratio <= 1.0

    def test_max_value_zero_draw_does_not_raise(self, surface):
        from src.ui.widgets import ProgressBar
        bar = ProgressBar(
            rect=pygame.Rect(0, 0, 100, 10),
            value=0,
            max_value=0,
            fill_color=(255, 0, 0),
            bg_color=(20, 20, 20),
        )
        bar.draw(surface)

    def test_fill_ratio_when_value_equals_max(self):
        from src.ui.widgets import ProgressBar
        bar = ProgressBar(
            rect=pygame.Rect(0, 0, 100, 10),
            value=77,
            max_value=77,
            fill_color=(0, 255, 0),
            bg_color=(0, 0, 0),
        )
        assert bar.fill_ratio == pytest.approx(1.0)

    def test_no_border_color_does_not_raise(self, surface):
        """border_color=None means no border is drawn; must not crash."""
        from src.ui.widgets import ProgressBar
        bar = ProgressBar(
            rect=pygame.Rect(0, 0, 100, 10),
            value=50,
            max_value=100,
            fill_color=(0, 255, 0),
            bg_color=(0, 0, 0),
            border_color=None,
        )
        bar.draw(surface)

    def test_value_exactly_half_gives_half_fill_ratio(self):
        from src.ui.widgets import ProgressBar
        bar = ProgressBar(
            rect=pygame.Rect(0, 0, 200, 12),
            value=50,
            max_value=100,
            fill_color=(0, 255, 255),
            bg_color=(0, 0, 0),
        )
        assert bar.fill_ratio == pytest.approx(0.5)

    def test_draw_with_all_anchors_for_rect_sizes_does_not_raise(self, surface):
        """Draw a bar at various rect sizes to exercise the fill_w=0 and
        full-width fill code paths."""
        from src.ui.widgets import ProgressBar
        for value, max_value in [(0, 100), (100, 100), (1, 100), (99, 100)]:
            bar = ProgressBar(
                rect=pygame.Rect(0, 0, 80, 8),
                value=value,
                max_value=max_value,
                fill_color=(57, 255, 20),
                bg_color=(20, 24, 38),
            )
            bar.draw(surface)


# ---------------------------------------------------------------------------
# IconSlot — additional attribute and rendering tests
# ---------------------------------------------------------------------------
class TestIconSlotAttributes:
    def test_selected_true_stored(self):
        from src.ui.widgets import IconSlot
        slot = IconSlot(rect=pygame.Rect(0, 0, 48, 48), selected=True)
        assert slot.selected is True

    def test_selected_false_is_default(self):
        from src.ui.widgets import IconSlot
        slot = IconSlot(rect=pygame.Rect(0, 0, 48, 48))
        assert slot.selected is False

    def test_hotkey_stored(self):
        from src.ui.widgets import IconSlot
        slot = IconSlot(rect=pygame.Rect(0, 0, 48, 48), hotkey='3')
        assert slot.hotkey == '3'

    def test_count_stored(self):
        from src.ui.widgets import IconSlot
        slot = IconSlot(rect=pygame.Rect(0, 0, 48, 48), count=5)
        assert slot.count == 5

    def test_icon_stored(self, surface):
        from src.ui.widgets import IconSlot
        icon = pygame.Surface((32, 32))
        slot = IconSlot(rect=pygame.Rect(0, 0, 48, 48), icon=icon)
        assert slot.icon is icon

    def test_draw_with_icon_surface_does_not_raise(self, surface):
        from src.ui.widgets import IconSlot
        icon = pygame.Surface((32, 32))
        icon.fill((200, 50, 50))
        slot = IconSlot(
            rect=pygame.Rect(0, 0, 48, 48),
            icon=icon,
        )
        slot.draw(surface)

    def test_draw_with_label_and_font_does_not_raise(self, surface):
        from src.ui.widgets import IconSlot
        font = pygame.font.SysFont('monospace', 10)
        slot = IconSlot(
            rect=pygame.Rect(0, 0, 48, 48),
            label='Med',
            font=font,
        )
        slot.draw(surface)

    def test_draw_with_all_features_does_not_raise(self, surface):
        from src.ui.widgets import IconSlot
        font = pygame.font.SysFont('monospace', 10)
        icon = pygame.Surface((32, 32))
        slot = IconSlot(
            rect=pygame.Rect(10, 10, 48, 48),
            icon=icon,
            label='Kit',
            hotkey='2',
            count=3,
            font=font,
            selected=True,
        )
        slot.draw(surface)


# ---------------------------------------------------------------------------
# Panel — additional attribute and alpha tests
# ---------------------------------------------------------------------------
class TestPanelAttributes:
    def test_alpha_stored(self):
        from src.ui.widgets import Panel
        panel = Panel(rect=pygame.Rect(0, 0, 50, 50), alpha=128)
        assert panel.alpha == 128

    def test_border_width_stored(self):
        from src.ui.widgets import Panel
        panel = Panel(rect=pygame.Rect(0, 0, 50, 50), border_width=3)
        assert panel.border_width == 3

    def test_draw_fully_transparent_does_not_raise(self, surface):
        from src.ui.widgets import Panel
        panel = Panel(rect=pygame.Rect(0, 0, 80, 40), alpha=0)
        panel.draw(surface)

    def test_draw_fully_opaque_does_not_raise(self, surface):
        from src.ui.widgets import Panel
        panel = Panel(rect=pygame.Rect(0, 0, 80, 40), alpha=255)
        panel.draw(surface)


# ---------------------------------------------------------------------------
# Slider
# ---------------------------------------------------------------------------
class TestSlider:
    """Tests for the pre-existing Slider widget."""

    def test_initial_value_is_clamped_to_min(self):
        from src.ui.widgets import Slider
        s = Slider(rect=(0, 0, 200, 20), min_val=10, max_val=100, initial=-50)
        assert s.value == pytest.approx(10.0)

    def test_initial_value_is_clamped_to_max(self):
        from src.ui.widgets import Slider
        s = Slider(rect=(0, 0, 200, 20), min_val=0, max_val=100, initial=200)
        assert s.value == pytest.approx(100.0)

    def test_initial_value_within_range_is_unchanged(self):
        from src.ui.widgets import Slider
        s = Slider(rect=(0, 0, 200, 20), min_val=0, max_val=1, initial=0.5)
        assert s.value == pytest.approx(0.5)

    def test_label_stored(self):
        from src.ui.widgets import Slider
        s = Slider(rect=(0, 0, 200, 20), min_val=0, max_val=100,
                   initial=50, label='Volume')
        assert s.label == 'Volume'

    def test_on_change_callback_stored(self):
        from src.ui.widgets import Slider
        cb = lambda v: None
        s = Slider(rect=(0, 0, 200, 20), min_val=0, max_val=1,
                   initial=0.5, on_change=cb)
        assert s.on_change is cb

    def test_value_to_px_at_min(self):
        from src.ui.widgets import Slider
        s = Slider(rect=(10, 0, 200, 20), min_val=0, max_val=100, initial=0)
        px = s._value_to_px()
        assert px == 10  # track_x + 0 * track_w

    def test_value_to_px_at_max(self):
        from src.ui.widgets import Slider
        s = Slider(rect=(10, 0, 200, 20), min_val=0, max_val=100, initial=100)
        px = s._value_to_px()
        assert px == 210  # track_x + 1.0 * track_w

    def test_px_to_value_at_left_edge(self):
        from src.ui.widgets import Slider
        s = Slider(rect=(0, 0, 200, 20), min_val=0, max_val=100, initial=50)
        val = s._px_to_value(0)
        assert val == pytest.approx(0.0)

    def test_px_to_value_at_right_edge(self):
        from src.ui.widgets import Slider
        s = Slider(rect=(0, 0, 200, 20), min_val=0, max_val=100, initial=50)
        val = s._px_to_value(200)
        assert val == pytest.approx(100.0)

    def test_px_to_value_clamped_below_track(self):
        from src.ui.widgets import Slider
        s = Slider(rect=(50, 0, 200, 20), min_val=0, max_val=100, initial=50)
        val = s._px_to_value(-999)
        assert val == pytest.approx(0.0)

    def test_px_to_value_clamped_above_track(self):
        from src.ui.widgets import Slider
        s = Slider(rect=(0, 0, 200, 20), min_val=0, max_val=100, initial=50)
        val = s._px_to_value(9999)
        assert val == pytest.approx(100.0)

    def test_render_does_not_raise(self, surface):
        from src.ui.widgets import Slider
        s = Slider(rect=(10, 10, 150, 16), min_val=0, max_val=100, initial=40)
        font = pygame.font.SysFont('monospace', 11)
        s.render(surface, font, pygame)

    def test_render_without_label_does_not_raise(self, surface):
        from src.ui.widgets import Slider
        s = Slider(rect=(10, 30, 150, 16), min_val=0, max_val=1, initial=0.8)
        s.render(surface, None, pygame)

    def test_on_change_fired_when_value_changes(self):
        from src.ui.widgets import Slider
        changed: list[float] = []
        s = Slider(rect=(0, 0, 200, 20), min_val=0, max_val=100,
                   initial=50, on_change=lambda v: changed.append(v))
        s._set_from_px(0)   # force to 0 — should fire callback
        assert len(changed) == 1
        assert changed[0] == pytest.approx(0.0)
