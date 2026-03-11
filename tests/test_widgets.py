"""Tests for Slider widget — value conversion, clamping, and callbacks.

All tests exercise the pure-Python logic (value_to_px, px_to_value,
set_from_px, callback wiring).  Rendering and pygame-dependent event
handling are excluded because they require a display surface.
"""
import pytest
from unittest.mock import MagicMock

from src.ui.widgets import Slider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_slider(
    rect=(0, 0, 200, 20),
    min_val=0.0,
    max_val=1.0,
    initial=0.5,
    label="Test",
    on_change=None,
) -> Slider:
    return Slider(
        rect=rect,
        min_val=min_val,
        max_val=max_val,
        initial=initial,
        label=label,
        on_change=on_change,
    )


# ---------------------------------------------------------------------------
# Initialisation — value clamping
# ---------------------------------------------------------------------------

class TestInitialValue:
    def test_value_within_range_stored_as_is(self):
        s = make_slider(initial=0.7)
        assert s.value == pytest.approx(0.7)

    def test_value_above_max_clamped_to_max(self):
        s = make_slider(initial=2.0, max_val=1.0)
        assert s.value == pytest.approx(1.0)

    def test_value_below_min_clamped_to_min(self):
        s = make_slider(initial=-0.5, min_val=0.0)
        assert s.value == pytest.approx(0.0)

    def test_value_exactly_at_min(self):
        s = make_slider(initial=0.0)
        assert s.value == pytest.approx(0.0)

    def test_value_exactly_at_max(self):
        s = make_slider(initial=1.0)
        assert s.value == pytest.approx(1.0)

    def test_not_dragging_by_default(self):
        s = make_slider()
        assert s._dragging is False

    def test_label_stored(self):
        s = make_slider(label="Master Volume")
        assert s.label == "Master Volume"

    def test_rect_stored(self):
        rect = (10, 20, 300, 15)
        s = make_slider(rect=rect)
        assert s.rect == rect


# ---------------------------------------------------------------------------
# Value-to-pixel conversion
# ---------------------------------------------------------------------------

class TestValueToPx:
    def test_min_value_maps_to_track_left(self):
        s = make_slider(rect=(50, 0, 200, 20), initial=0.0)
        assert s._value_to_px() == 50   # track_x + 0

    def test_max_value_maps_to_track_right(self):
        s = make_slider(rect=(50, 0, 200, 20), initial=1.0)
        assert s._value_to_px() == 250   # track_x + track_w

    def test_midpoint_value_maps_to_centre(self):
        s = make_slider(rect=(0, 0, 200, 20), initial=0.5)
        assert s._value_to_px() == 100

    def test_quarter_value(self):
        s = make_slider(rect=(0, 0, 200, 20), initial=0.25)
        assert s._value_to_px() == 50

    def test_non_zero_origin(self):
        """Track starting at x=100 with initial=0.5 → px = 100 + 100 = 200."""
        s = make_slider(rect=(100, 0, 200, 20), initial=0.5)
        assert s._value_to_px() == 200


# ---------------------------------------------------------------------------
# Pixel-to-value conversion
# ---------------------------------------------------------------------------

class TestPxToValue:
    def test_left_edge_gives_min(self):
        s = make_slider(rect=(0, 0, 200, 20))
        assert s._px_to_value(0) == pytest.approx(0.0)

    def test_right_edge_gives_max(self):
        s = make_slider(rect=(0, 0, 200, 20))
        assert s._px_to_value(200) == pytest.approx(1.0)

    def test_midpoint_pixel_gives_half(self):
        s = make_slider(rect=(0, 0, 200, 20))
        assert s._px_to_value(100) == pytest.approx(0.5)

    def test_pixel_below_track_clamped_to_min(self):
        s = make_slider(rect=(50, 0, 200, 20))
        assert s._px_to_value(0) == pytest.approx(0.0)

    def test_pixel_beyond_track_clamped_to_max(self):
        s = make_slider(rect=(0, 0, 200, 20))
        assert s._px_to_value(9999) == pytest.approx(1.0)

    def test_custom_range(self):
        s = make_slider(rect=(0, 0, 100, 20), min_val=0.0, max_val=2.0, initial=1.0)
        assert s._px_to_value(50) == pytest.approx(1.0)   # midpoint → 1.0


# ---------------------------------------------------------------------------
# _set_from_px — mutation and callback
# ---------------------------------------------------------------------------

class TestSetFromPx:
    def test_callback_called_with_new_value(self):
        cb = MagicMock()
        s = make_slider(rect=(0, 0, 200, 20), initial=0.0, on_change=cb)
        s._set_from_px(100)   # → 0.5
        cb.assert_called_once()
        assert cb.call_args[0][0] == pytest.approx(0.5)

    def test_callback_not_called_when_value_unchanged(self):
        cb = MagicMock()
        # initial=0.5 on a 200px track → px 100 maps back to 0.5
        s = make_slider(rect=(0, 0, 200, 20), initial=0.5, on_change=cb)
        s._set_from_px(100)
        cb.assert_not_called()

    def test_no_callback_does_not_raise(self):
        s = make_slider(on_change=None)
        s._set_from_px(50)   # must not raise AttributeError

    def test_value_updated_after_set(self):
        s = make_slider(rect=(0, 0, 200, 20), initial=0.0)
        s._set_from_px(100)
        assert s.value == pytest.approx(0.5)

    def test_callback_receives_clamped_value(self):
        cb = MagicMock()
        s = make_slider(rect=(0, 0, 200, 20), initial=0.5, on_change=cb)
        s._set_from_px(9999)   # past the end → clamped to max
        cb.assert_called_once()
        assert cb.call_args[0][0] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Slider properties
# ---------------------------------------------------------------------------

class TestSliderProperties:
    def test_track_x_matches_rect(self):
        s = make_slider(rect=(42, 10, 150, 18))
        assert s._track_x == 42

    def test_track_y_matches_rect(self):
        s = make_slider(rect=(42, 10, 150, 18))
        assert s._track_y == 10

    def test_track_w_matches_rect(self):
        s = make_slider(rect=(42, 10, 150, 18))
        assert s._track_w == 150

    def test_track_h_matches_rect(self):
        s = make_slider(rect=(42, 10, 150, 18))
        assert s._track_h == 18
