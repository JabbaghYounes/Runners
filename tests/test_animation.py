"""Tests for AnimationController (src/utils/animation.py).

Covers:
  - Initialisation and default-state selection
  - set_state: no-op on same state, reset on change, silently ignores unknown states
  - update: frame-advancement timing, looping wrap, non-loop clamp, single-frame edge case
  - get_current_frame: always returns a pygame.Surface of the correct dimensions
  - Fallback: missing asset files produce placeholder coloured surfaces, never crash
  - Strip loading: frames correctly sliced from a real Surface
"""
import pytest
import pygame

from src.utils.animation import (
    AnimationController,
    _make_fallback_frame,
    _FALLBACK_W,
    _FALLBACK_H,
    _DEFAULT_FALLBACK_COLOR,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FallbackAM:
    """Asset manager that always returns None → triggers fallback frames."""
    def load_image(self, path: str):
        return None


class _StripAM:
    """Asset manager that returns a pre-built Surface for any path."""
    def __init__(self, surface: pygame.Surface):
        self._surface = surface

    def load_image(self, path: str):
        return self._surface


def _make_strip(frame_count: int, frame_w: int = 48, frame_h: int = 64) -> pygame.Surface:
    """Horizontal strip where each frame is a distinct solid colour."""
    surf = pygame.Surface((frame_w * frame_count, frame_h))
    for i in range(frame_count):
        surf.fill((i * 40 % 200 + 20, 100, 200), (i * frame_w, 0, frame_w, frame_h))
    return surf


_FOUR_STATE_SPEC = {
    "idle":   ("assets/sprites/player/idle.png",   4, 8.0),
    "run":    ("assets/sprites/player/run.png",    6, 12.0),
    "crouch": ("assets/sprites/player/crouch.png", 2, 6.0),
    "slide":  ("assets/sprites/player/slide.png",  3, 10.0),
}


@pytest.fixture()
def ctrl():
    return AnimationController(_FOUR_STATE_SPEC, _FallbackAM())


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestInit:
    def test_default_state_is_first_key(self, ctrl):
        assert ctrl.current_state == "idle"

    def test_explicit_default_state(self):
        c = AnimationController(_FOUR_STATE_SPEC, _FallbackAM(), default_state="run")
        assert c.current_state == "run"

    def test_frame_index_starts_at_zero(self, ctrl):
        assert ctrl._frame_index == 0

    def test_frame_timer_starts_at_zero(self, ctrl):
        assert ctrl._frame_timer == 0.0

    def test_all_states_have_at_least_one_frame(self, ctrl):
        for state in _FOUR_STATE_SPEC:
            assert len(ctrl._frames[state]) >= 1

    def test_fps_stored_per_state(self, ctrl):
        assert ctrl._fps["idle"] == pytest.approx(8.0)
        assert ctrl._fps["run"] == pytest.approx(12.0)

    def test_fps_clamped_to_minimum_one(self):
        c = AnimationController({"idle": ("x.png", 2, 0.0)}, _FallbackAM())
        assert c._fps["idle"] >= 1.0

    def test_empty_states_dict_does_not_crash(self):
        c = AnimationController({}, _FallbackAM())
        assert c.current_state == ""


# ---------------------------------------------------------------------------
# set_state
# ---------------------------------------------------------------------------

class TestSetState:
    def test_switches_to_valid_state(self, ctrl):
        ctrl.set_state("run")
        assert ctrl.current_state == "run"

    def test_same_state_preserves_frame_index(self, ctrl):
        ctrl.update(0.2)              # advance to frame 1
        idx = ctrl._frame_index
        ctrl.set_state("idle")        # no-op
        assert ctrl._frame_index == idx

    def test_same_state_preserves_timer(self, ctrl):
        ctrl.update(0.05)
        timer = ctrl._frame_timer
        ctrl.set_state("idle")
        assert abs(ctrl._frame_timer - timer) < 1e-9

    def test_new_state_resets_frame_index(self, ctrl):
        ctrl.update(0.2)              # advance so index > 0
        ctrl.set_state("run")
        assert ctrl._frame_index == 0

    def test_new_state_resets_timer(self, ctrl):
        ctrl.update(0.05)
        ctrl.set_state("run")
        assert ctrl._frame_timer == 0.0

    def test_unknown_state_is_silently_ignored(self, ctrl):
        ctrl.set_state("fly")
        assert ctrl.current_state == "idle"

    def test_can_cycle_all_four_states(self, ctrl):
        for state in _FOUR_STATE_SPEC:
            ctrl.set_state(state)
            assert ctrl.current_state == state


# ---------------------------------------------------------------------------
# update — frame-advancement timing
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_no_advance_before_frame_duration(self):
        # idle @ 8 fps → frame_duration = 0.125 s
        c = AnimationController({"idle": ("x.png", 4, 8.0)}, _FallbackAM())
        c.update(0.10)
        assert c._frame_index == 0

    def test_advances_one_frame_past_duration(self):
        c = AnimationController({"idle": ("x.png", 4, 8.0)}, _FallbackAM())
        c.update(0.13)   # 0.13 > 0.125
        assert c._frame_index == 1

    def test_large_dt_advances_multiple_frames(self):
        c = AnimationController({"idle": ("x.png", 4, 8.0)}, _FallbackAM())
        c.update(0.4)    # 0.4 / 0.125 = 3.2 → 3 advances
        assert c._frame_index == 3

    def test_loop_wraps_at_end(self):
        # 2 frames @ 8 fps, loop=True; 3 advances: 0→1→0→1
        c = AnimationController({"idle": ("x.png", 2, 8.0)}, _FallbackAM(), loop=True)
        c.update(0.13 * 3)
        assert c._frame_index == 1

    def test_non_loop_clamps_at_last_frame(self):
        c = AnimationController({"idle": ("x.png", 2, 8.0)}, _FallbackAM(), loop=False)
        c.update(5.0)
        assert c._frame_index == 1   # last index of a 2-frame strip

    def test_single_frame_never_advances(self):
        c = AnimationController({"idle": ("x.png", 1, 8.0)}, _FallbackAM())
        c.update(10.0)
        assert c._frame_index == 0

    def test_timer_remainder_carries_over(self):
        c = AnimationController({"idle": ("x.png", 4, 8.0)}, _FallbackAM())
        c.update(0.13)   # advances once; remainder ≈ 0.005
        assert c._frame_timer < 0.125


# ---------------------------------------------------------------------------
# get_current_frame
# ---------------------------------------------------------------------------

class TestGetCurrentFrame:
    def test_returns_surface(self, ctrl):
        assert isinstance(ctrl.get_current_frame(), pygame.Surface)

    def test_default_frame_width(self, ctrl):
        assert ctrl.get_current_frame().get_width() == 48

    def test_default_frame_height(self, ctrl):
        assert ctrl.get_current_frame().get_height() == 64

    def test_custom_frame_dimensions(self):
        c = AnimationController({"idle": ("x.png", 2, 8.0)}, _FallbackAM(),
                                frame_w=32, frame_h=48)
        f = c.get_current_frame()
        assert f.get_width() == 32
        assert f.get_height() == 48

    def test_empty_controller_returns_surface(self):
        c = AnimationController({}, _FallbackAM())
        assert isinstance(c.get_current_frame(), pygame.Surface)

    def test_different_surface_returned_after_state_advance(self):
        strip = _make_strip(4)
        c = AnimationController({"idle": ("x.png", 4, 8.0)}, _StripAM(strip))
        f0 = c.get_current_frame()
        c.update(0.13)
        f1 = c.get_current_frame()
        assert f0 is not f1


# ---------------------------------------------------------------------------
# Fallback frames
# ---------------------------------------------------------------------------

class TestFallbackFrame:
    def test_returns_surface(self):
        assert isinstance(_make_fallback_frame("idle"), pygame.Surface)

    def test_default_dimensions(self):
        s = _make_fallback_frame("idle")
        assert s.get_width() == _FALLBACK_W
        assert s.get_height() == _FALLBACK_H

    def test_custom_dimensions(self):
        s = _make_fallback_frame("run", w=32, h=48)
        assert s.get_width() == 32
        assert s.get_height() == 48

    def test_known_states_produce_distinct_colours(self):
        colours = set()
        for state in ("idle", "run", "crouch", "slide"):
            s = _make_fallback_frame(state)
            cx, cy = s.get_width() // 2, s.get_height() // 2
            colours.add(s.get_at((cx, cy))[:3])
        assert len(colours) == 4

    def test_unknown_state_uses_default_colour(self):
        s = _make_fallback_frame("unknown_xyz")
        cx, cy = s.get_width() // 2, s.get_height() // 2
        assert s.get_at((cx, cy))[:3] == _DEFAULT_FALLBACK_COLOR


# ---------------------------------------------------------------------------
# Strip loading from real Surfaces
# ---------------------------------------------------------------------------

class TestStripLoading:
    def test_frames_sliced_to_correct_size(self):
        strip = _make_strip(4, frame_w=48, frame_h=64)
        c = AnimationController({"idle": ("x.png", 4, 8.0)}, _StripAM(strip),
                                frame_w=48, frame_h=64)
        f = c.get_current_frame()
        assert f.get_width() == 48
        assert f.get_height() == 64

    def test_all_sliced_frames_accessible_without_error(self):
        strip = _make_strip(4, frame_w=48, frame_h=64)
        c = AnimationController({"idle": ("x.png", 4, 8.0)}, _StripAM(strip),
                                frame_w=48, frame_h=64)
        for _ in range(4):
            assert isinstance(c.get_current_frame(), pygame.Surface)
            c.update(0.13)

    def test_undersized_strip_falls_back_gracefully(self):
        # Strip is only 1 frame wide; frames 1-3 become fallbacks.
        strip = _make_strip(1, frame_w=48, frame_h=64)
        c = AnimationController({"idle": ("x.png", 4, 8.0)}, _StripAM(strip),
                                frame_w=48, frame_h=64)
        for _ in range(4):
            assert isinstance(c.get_current_frame(), pygame.Surface)
            c.update(0.13)
