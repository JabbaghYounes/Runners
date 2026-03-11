"""Unit tests for src.ui.widgets — Panel, Label, Button, ProgressBar, Slider,
ConfirmDialog.

All tests require pygame to be initialised (conftest.py handles this).
"""
import pygame
import pytest

from src.ui.widgets import Button, ConfirmDialog, Label, Panel, ProgressBar, Slider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _font():
    return pygame.font.SysFont("monospace", 14)


def _click_at(x: int, y: int) -> list:
    """Return [MOUSEBUTTONDOWN, MOUSEBUTTONUP] events that simulate a left-click."""
    return [
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(x, y), button=1),
        pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(x, y), button=1),
    ]


def _motion_to(x: int, y: int) -> pygame.event.Event:
    return pygame.event.Event(
        pygame.MOUSEMOTION, pos=(x, y), rel=(0, 0), buttons=(0, 0, 0)
    )


# ===========================================================================
# Panel
# ===========================================================================

class TestPanel:
    def test_draw_does_not_raise(self, screen):
        panel = Panel(pygame.Rect(50, 50, 300, 200))
        panel.draw(screen)

    def test_custom_alpha_draws_without_error(self, screen):
        panel = Panel(pygame.Rect(0, 0, 100, 100), alpha=128)
        panel.draw(screen)

    def test_custom_radius_draws_without_error(self, screen):
        panel = Panel(pygame.Rect(0, 0, 100, 100), radius=12)
        panel.draw(screen)


# ===========================================================================
# Label
# ===========================================================================

class TestLabel:
    def test_draw_renders_without_error(self, screen):
        lbl = Label("Hello", _font(), (255, 255, 255), (100, 100))
        lbl.draw(screen)

    def test_draw_with_glow_does_not_raise(self, screen):
        lbl = Label("GLOW", _font(), (0, 245, 255), (200, 100), glow=True)
        lbl.draw(screen)

    def test_set_text_updates_text_and_clears_cache(self):
        lbl = Label("First", _font())
        _ = lbl._rendered()            # Populate cache
        lbl.set_text("Second")
        assert lbl.text == "Second"
        assert lbl._cached_surf is None

    def test_rendered_surface_cached_across_calls(self):
        lbl = Label("Stable", _font())
        s1 = lbl._rendered()
        s2 = lbl._rendered()
        assert s1 is s2

    def test_rendered_cache_invalidated_when_text_changes(self):
        lbl = Label("A", _font())
        s1 = lbl._rendered()
        lbl.set_text("B")
        s2 = lbl._rendered()
        assert s1 is not s2

    # Alignment -----------------------------------------------------------

    def test_align_center_places_center_at_pos(self):
        lbl = Label("Test", _font(), pos=(200, 100), align="center")
        r = lbl._place_rect(lbl._rendered())
        assert r.centerx == 200
        assert r.centery == 100

    def test_align_left_places_midleft_at_pos(self):
        lbl = Label("Test", _font(), pos=(50, 100), align="left")
        r = lbl._place_rect(lbl._rendered())
        assert r.midleft == (50, 100)

    def test_align_right_places_midright_at_pos(self):
        lbl = Label("Test", _font(), pos=(300, 100), align="right")
        r = lbl._place_rect(lbl._rendered())
        assert r.midright == (300, 100)


# ===========================================================================
# Button
# ===========================================================================

class TestButton:
    def test_click_returns_true(self):
        btn = Button(pygame.Rect(10, 10, 100, 40), "OK", _font(), "primary")
        result = False
        for ev in _click_at(60, 30):
            result = btn.handle_event(ev)
        assert result is True

    def test_click_invokes_on_click_callback(self):
        calls: list = []
        btn = Button(
            pygame.Rect(0, 0, 100, 40), "GO", _font(), "primary",
            lambda: calls.append(1),
        )
        for ev in _click_at(50, 20):
            btn.handle_event(ev)
        assert calls == [1]

    def test_click_outside_rect_does_not_trigger(self):
        calls: list = []
        btn = Button(
            pygame.Rect(10, 10, 100, 40), "OK", _font(), "primary",
            lambda: calls.append(1),
        )
        for ev in _click_at(300, 300):
            btn.handle_event(ev)
        assert calls == []

    def test_click_outside_returns_false(self):
        btn = Button(pygame.Rect(10, 10, 100, 40), "X", _font())
        result = False
        for ev in _click_at(300, 300):
            result = btn.handle_event(ev)
        assert result is False

    def test_mousebuttondown_alone_returns_false(self):
        btn = Button(pygame.Rect(0, 0, 100, 40), "X", _font())
        ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(50, 20), button=1)
        assert btn.handle_event(ev) is False

    def test_mousemotion_inside_sets_hovered_true(self):
        btn = Button(pygame.Rect(10, 10, 100, 40), "X", _font())
        btn.handle_event(_motion_to(60, 30))
        assert btn._hovered is True

    def test_mousemotion_outside_sets_hovered_false(self):
        btn = Button(pygame.Rect(10, 10, 100, 40), "X", _font())
        btn.handle_event(_motion_to(60, 30))   # inside
        btn.handle_event(_motion_to(300, 300)) # outside
        assert btn._hovered is False

    def test_mousebuttondown_inside_sets_pressed(self):
        btn = Button(pygame.Rect(0, 0, 100, 40), "X", _font())
        btn.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(50, 20), button=1))
        assert btn._pressed is True

    def test_mousebuttonup_clears_pressed(self):
        btn = Button(pygame.Rect(0, 0, 100, 40), "X", _font())
        for ev in _click_at(50, 20):
            btn.handle_event(ev)
        assert btn._pressed is False

    def test_no_callback_click_still_returns_true(self):
        btn = Button(pygame.Rect(0, 0, 100, 40), "X", _font())
        result = False
        for ev in _click_at(50, 20):
            result = btn.handle_event(ev)
        assert result is True

    # Styles ---------------------------------------------------------------

    def test_draw_primary_style(self, screen):
        btn = Button(pygame.Rect(10, 10, 120, 40), "START", _font(), "primary")
        btn.draw(screen)

    def test_draw_secondary_style(self, screen):
        btn = Button(pygame.Rect(10, 10, 120, 40), "BACK", _font(), "secondary")
        btn.draw(screen)

    def test_draw_danger_style(self, screen):
        btn = Button(pygame.Rect(10, 10, 120, 40), "EXIT", _font(), "danger")
        btn.draw(screen)

    def test_draw_hovered_state(self, screen):
        btn = Button(pygame.Rect(10, 10, 120, 40), "HOVER", _font(), "primary")
        btn._hovered = True
        btn.draw(screen)

    def test_draw_pressed_state(self, screen):
        btn = Button(pygame.Rect(10, 10, 120, 40), "PRESS", _font(), "primary")
        btn._pressed = True
        btn.draw(screen)

    def test_draw_focused_state(self, screen):
        btn = Button(pygame.Rect(10, 10, 120, 40), "FOCUS", _font(), "secondary")
        btn._focused = True
        btn.draw(screen)

    def test_unknown_style_falls_back_to_secondary(self, screen):
        btn = Button(pygame.Rect(0, 0, 100, 40), "X", _font(), "nonexistent_style")
        btn.draw(screen)   # Must not raise


# ===========================================================================
# ProgressBar
# ===========================================================================

class TestProgressBar:
    def test_value_clamped_above_one(self):
        pb = ProgressBar(pygame.Rect(0, 0, 100, 10), value=1.5)
        assert pb.value == pytest.approx(1.0)

    def test_value_clamped_below_zero(self):
        pb = ProgressBar(pygame.Rect(0, 0, 100, 10), value=-0.5)
        assert pb.value == pytest.approx(0.0)

    def test_valid_value_unchanged(self):
        pb = ProgressBar(pygame.Rect(0, 0, 100, 10), value=0.7)
        assert pb.value == pytest.approx(0.7)

    def test_zero_value_is_valid(self):
        pb = ProgressBar(pygame.Rect(0, 0, 100, 10), value=0.0)
        assert pb.value == pytest.approx(0.0)

    def test_full_value_is_valid(self):
        pb = ProgressBar(pygame.Rect(0, 0, 100, 10), value=1.0)
        assert pb.value == pytest.approx(1.0)

    def test_draw_mid_value(self, screen):
        pb = ProgressBar(pygame.Rect(50, 50, 200, 16), value=0.6)
        pb.draw(screen)

    def test_draw_zero_value(self, screen):
        pb = ProgressBar(pygame.Rect(50, 50, 200, 16), value=0.0)
        pb.draw(screen)

    def test_draw_full_value(self, screen):
        pb = ProgressBar(pygame.Rect(50, 50, 200, 16), value=1.0)
        pb.draw(screen)


# ===========================================================================
# Slider
# ===========================================================================

class TestSlider:
    def test_value_clamped_above_one(self):
        s = Slider(pygame.Rect(0, 0, 200, 20), value=2.5)
        assert s.value == pytest.approx(1.0)

    def test_value_clamped_below_zero(self):
        s = Slider(pygame.Rect(0, 0, 200, 20), value=-1.0)
        assert s.value == pytest.approx(0.0)

    def test_initial_value_preserved(self):
        s = Slider(pygame.Rect(0, 0, 200, 20), value=0.42)
        assert s.value == pytest.approx(0.42)

    def test_not_dragging_by_default(self):
        s = Slider(pygame.Rect(0, 0, 200, 20), value=0.5)
        assert s._dragging is False

    def test_mousedown_on_track_starts_drag(self):
        rect = pygame.Rect(100, 50, 200, 20)
        sl = Slider(rect, value=0.5)
        ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(200, 60), button=1)
        consumed = sl.handle_event(ev)
        assert consumed is True
        assert sl._dragging is True

    def test_mousedown_outside_track_does_not_start_drag(self):
        rect = pygame.Rect(100, 50, 200, 20)
        sl = Slider(rect, value=0.5)
        ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=1)
        sl.handle_event(ev)
        assert sl._dragging is False

    def test_mouseup_ends_drag(self):
        rect = pygame.Rect(0, 0, 200, 20)
        sl = Slider(rect, value=0.5)
        sl.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(100, 10), button=1))
        assert sl._dragging is True
        sl.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(100, 10), button=1))
        assert sl._dragging is False

    def test_mouseup_while_dragging_returns_true(self):
        rect = pygame.Rect(0, 0, 200, 20)
        sl = Slider(rect, value=0.5)
        sl.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(100, 10), button=1))
        result = sl.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(100, 10), button=1)
        )
        assert result is True

    def test_mousemotion_while_dragging_updates_value(self):
        rect = pygame.Rect(0, 50, 200, 20)
        sl = Slider(rect, value=0.0)
        # Start drag at the left edge
        sl.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(0, 60), button=1))
        # Drag to the 50% mark
        sl.handle_event(
            pygame.event.Event(pygame.MOUSEMOTION, pos=(100, 60), rel=(100, 0), buttons=(1, 0, 0))
        )
        assert sl.value == pytest.approx(0.5)

    def test_mousemotion_without_drag_does_not_change_value(self):
        rect = pygame.Rect(0, 0, 200, 20)
        sl = Slider(rect, value=0.5)
        sl.handle_event(
            pygame.event.Event(pygame.MOUSEMOTION, pos=(150, 10), rel=(10, 0), buttons=(0, 0, 0))
        )
        assert sl.value == pytest.approx(0.5)

    def test_on_change_callback_called_when_value_changes(self):
        changes: list = []
        rect = pygame.Rect(0, 0, 200, 20)
        sl = Slider(rect, value=0.0, on_change=lambda v: changes.append(v))
        # Clicking at x=100 (50% of 200) should change value from 0.0 → 0.5
        sl.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(100, 10), button=1))
        assert len(changes) >= 1
        assert all(0.0 <= c <= 1.0 for c in changes)

    def test_on_change_not_called_when_value_unchanged(self):
        changes: list = []
        rect = pygame.Rect(0, 0, 200, 20)
        sl = Slider(rect, value=1.0, on_change=lambda v: changes.append(v))
        # Click at the far right — value is already 1.0, no change expected.
        sl.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(200, 10), button=1))
        assert len(changes) == 0

    def test_value_clamped_to_zero_at_left_edge(self):
        rect = pygame.Rect(100, 0, 200, 20)
        sl = Slider(rect, value=0.5)
        sl.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(50, 10), button=1))
        assert sl.value == pytest.approx(0.0)

    def test_value_clamped_to_one_at_right_edge(self):
        rect = pygame.Rect(0, 0, 200, 20)
        sl = Slider(rect, value=0.0)
        sl.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(250, 10), button=1))
        assert sl.value == pytest.approx(1.0)

    def test_draw_does_not_raise(self, screen):
        sl = Slider(pygame.Rect(50, 50, 200, 20), value=0.5)
        sl.draw(screen)

    def test_draw_at_zero(self, screen):
        sl = Slider(pygame.Rect(50, 50, 200, 20), value=0.0)
        sl.draw(screen)

    def test_draw_at_full(self, screen):
        sl = Slider(pygame.Rect(50, 50, 200, 20), value=1.0)
        sl.draw(screen)


# ===========================================================================
# ConfirmDialog
# ===========================================================================

class TestConfirmDialog:

    # Screen 1280×720; dialog 360×180 centred at (640, 360).
    # rect after layout: left=460, top=270, right=820, bottom=450
    # btn_y = bottom - 52 = 398
    # CONFIRM: Rect(500, 398, 130, 38)  — centre (565, 417)
    # CANCEL : Rect(650, 398, 130, 38)  — centre (715, 417)

    _CONFIRM_POS = (565, 417)
    _CANCEL_POS = (715, 417)

    def _make(self, on_confirm=None, on_cancel=None):
        font = _font()
        return ConfirmDialog(
            "Are you sure?",
            "This cannot be undone.",
            font, font, font,
            on_confirm=on_confirm,
            on_cancel=on_cancel,
        )

    def test_inactive_by_default(self):
        dlg = self._make()
        assert dlg.active is False

    def test_show_activates(self):
        dlg = self._make()
        dlg.show((1280, 720))
        assert dlg.active is True

    def test_hide_deactivates(self):
        dlg = self._make()
        dlg.show((1280, 720))
        dlg.hide()
        assert dlg.active is False

    def test_handle_event_returns_false_when_inactive(self):
        dlg = self._make()
        ev = pygame.event.Event(pygame.USEREVENT)
        assert dlg.handle_event(ev) is False

    def test_handle_event_returns_true_when_active(self):
        dlg = self._make()
        dlg.show((1280, 720))
        ev = pygame.event.Event(pygame.USEREVENT)
        assert dlg.handle_event(ev) is True

    def test_handle_event_swallows_events_while_active(self):
        """While active the dialog returns True for every event type,
        preventing underlying widgets from receiving them."""
        dlg = self._make()
        dlg.show((1280, 720))
        for ev_type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION):
            ev = pygame.event.Event(ev_type)
            assert dlg.handle_event(ev) is True

    def test_confirm_callback_fires_on_confirm_click(self):
        calls: list = []
        dlg = self._make(on_confirm=lambda: calls.append("confirm"))
        dlg.show((1280, 720))
        for ev in _click_at(*self._CONFIRM_POS):
            dlg.handle_event(ev)
        assert "confirm" in calls

    def test_cancel_callback_fires_on_cancel_click(self):
        calls: list = []
        dlg = self._make(on_cancel=lambda: calls.append("cancel"))
        dlg.show((1280, 720))
        for ev in _click_at(*self._CANCEL_POS):
            dlg.handle_event(ev)
        assert "cancel" in calls

    def test_draw_when_inactive_is_noop(self, screen):
        dlg = self._make()
        dlg.draw(screen)              # Must not raise

    def test_draw_when_active_renders(self, screen):
        dlg = self._make()
        dlg.show((1280, 720))
        dlg.draw(screen)             # Must not raise

    def test_show_with_different_screen_sizes_does_not_raise(self, screen):
        dlg = self._make()
        for size in ((800, 600), (1280, 720), (1920, 1080)):
            dlg.show(size)
            dlg.draw(screen)

    def test_show_hide_toggle_multiple_times(self):
        dlg = self._make()
        for _ in range(5):
            dlg.show((1280, 720))
            assert dlg.active is True
            dlg.hide()
            assert dlg.active is False
