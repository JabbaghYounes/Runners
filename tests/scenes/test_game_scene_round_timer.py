"""Unit and integration tests for the RoundTimer ↔ GameScene wiring.

Coverage matrix
---------------
Unit — stub-mode defaults
  - _round_timer is None when constructed without a SceneManager
  - _transitioning flag starts False
  - on_enter does not raise when timer is None
  - on_exit does not raise when timer is None
  - on_exit resets _transitioning to False regardless of its prior value
  - _build_hud_state returns 0 for seconds_remaining when timer is None

Unit — on_enter / on_exit lifecycle
  - on_enter starts the timer so manual timer.update() decrements it
  - on_enter resets the timer to its full duration on every call
  - on_exit resets the timer to its full duration
  - on_exit halts the timer so it no longer ticks
  - on_exit resets _transitioning even after a transition has occurred

Unit — HUDState seconds_remaining wiring
  - _build_hud_state reflects the live timer value
  - seconds_remaining decrements correctly after timer.update()
  - seconds_remaining is 0.0 once the timer has expired
  - each call returns a fresh HUDState snapshot (not a cached object)

Unit — _on_round_end handler and double-transition guard
  - _on_round_end sets _transitioning to True
  - _on_round_end calls sm.replace exactly once
  - second _on_round_end call is ignored by the transitioning guard
  - _on_extract_failed after _on_round_end is also ignored
  - on_exit clears _transitioning so the next round can transition
  - sm.replace receives the PostRound instance

Integration — EventBus → GameScene chain
  - round_end published via bus calls sm.replace
  - multiple round_end events on the bus cause only one sm.replace
  - round_warning is emitted when the timer crosses TIMER_WARN_SECS
  - timer decrements when GameScene.update() is called (_update_full path)
  - timer does not tick when update() is not called (pause simulation)

End-to-end — complete round timer flow
  - on_enter → tick → round_warning → round_end → sm.replace
  - timer resets and restarts cleanly on scene re-entry after expiry

# Run: pytest tests/scenes/test_game_scene_round_timer.py
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from src.core.constants import ROUND_DURATION_SECS, TIMER_WARN_SECS
from src.core.event_bus import EventBus
from src.core.settings import Settings
from src.scenes.game_scene import GameScene
from src.systems.round_timer import RoundTimer


# ---------------------------------------------------------------------------
# Patch paths (local imports inside _on_extract_failed use these modules)
# ---------------------------------------------------------------------------

_PATCH_POST_ROUND = "src.scenes.post_round.PostRound"
_PATCH_SAVE_MGR   = "src.save.save_manager.SaveManager"


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def _make_stub_scene(
    *,
    duration: float = 10.0,
    inject_timer: bool = False,
    sm: object = None,
) -> tuple[GameScene, EventBus, RoundTimer | None]:
    """Return *(scene, bus, timer)* in stub mode (no SceneManager).

    Stub mode is triggered by omitting the positional ``sm`` argument so
    ``GameScene._init_stub()`` is used — no map files, no full systems.
    When *inject_timer* is True, a real :class:`RoundTimer` is placed on
    the scene so lifecycle methods can be exercised.  *sm* is set directly
    on the scene to allow transition-handler tests without a full-init.
    """
    bus = EventBus()
    scene = GameScene(event_bus=bus, settings=Settings())  # no sm → stub mode
    timer: RoundTimer | None = None
    if inject_timer:
        timer = RoundTimer(bus, duration=duration)
        scene._round_timer = timer
    if sm is not None:
        scene._sm = sm
    return scene, bus, timer


def _make_ticking_scene(
    duration: float = 10.0,
    sm: object = None,
) -> tuple[GameScene, EventBus, RoundTimer]:
    """Like :func:`_make_stub_scene` with timer injection, but sets
    ``_full_init = True`` so ``GameScene.update()`` delegates to
    ``_update_full()`` and ticks the timer each frame.
    """
    scene, bus, timer = _make_stub_scene(duration=duration, inject_timer=True, sm=sm)
    # Enable the full update path (all subsystems guard with `if self._xxx:`)
    scene._full_init = True
    scene.player.alive = True
    return scene, bus, timer  # type: ignore[return-value]


# ===========================================================================
# Unit — stub-mode defaults
# ===========================================================================

class TestRoundTimerStubModeDefaults:
    """GameScene built without a SceneManager (stub mode) must initialise
    ``_round_timer`` as ``None`` and survive all lifecycle calls gracefully."""

    def test_round_timer_is_none_in_stub_mode(self):
        scene, _, _ = _make_stub_scene()
        assert scene._round_timer is None

    def test_transitioning_flag_starts_false(self):
        scene, _, _ = _make_stub_scene()
        assert scene._transitioning is False

    def test_on_enter_does_not_raise_when_timer_is_none(self):
        scene, _, _ = _make_stub_scene()
        scene.on_enter()  # must not raise

    def test_on_exit_does_not_raise_when_timer_is_none(self):
        scene, _, _ = _make_stub_scene()
        scene.on_exit()  # must not raise

    def test_on_exit_resets_transitioning_to_false_even_when_previously_true(self):
        """on_exit must clear the guard so the next round can also transition."""
        scene, _, _ = _make_stub_scene()
        scene._transitioning = True
        scene.on_exit()
        assert scene._transitioning is False

    def test_hud_state_seconds_remaining_zero_when_timer_is_none(self):
        """_build_hud_state must return 0 for seconds_remaining when there is no timer."""
        scene, _, _ = _make_stub_scene()
        state = scene._build_hud_state()
        assert state.seconds_remaining == 0


# ===========================================================================
# Unit — on_enter / on_exit lifecycle
# ===========================================================================

class TestRoundTimerLifecycle:
    """on_enter must reset + start the timer; on_exit must reset it and halt it."""

    def test_on_enter_starts_timer_so_manual_tick_decrements(self):
        """After on_enter the timer is running; advancing the timer should decrement."""
        scene, _, timer = _make_stub_scene(duration=10.0, inject_timer=True)
        scene.on_enter()
        timer.update(1.0)
        assert timer.seconds_remaining == pytest.approx(9.0)

    def test_on_enter_resets_timer_to_full_duration_on_each_call(self):
        """Calling on_enter a second time must restore the timer to its full duration."""
        scene, _, timer = _make_stub_scene(duration=10.0, inject_timer=True)
        scene.on_enter()
        timer.update(5.0)       # tick down to 5 s
        scene.on_enter()        # second entry — timer must be reset
        assert timer.seconds_remaining == pytest.approx(10.0)

    def test_on_exit_resets_timer_to_full_duration(self):
        scene, _, timer = _make_stub_scene(duration=10.0, inject_timer=True)
        scene.on_enter()
        timer.update(3.0)
        scene.on_exit()
        assert timer.seconds_remaining == pytest.approx(10.0)

    def test_on_exit_halts_timer_so_further_ticks_are_noops(self):
        """After on_exit, calling timer.update() must not decrement the timer."""
        scene, _, timer = _make_stub_scene(duration=10.0, inject_timer=True)
        scene.on_enter()
        scene.on_exit()
        timer.update(5.0)       # should be a no-op: timer is halted
        assert timer.seconds_remaining == pytest.approx(10.0)

    def test_on_exit_resets_transitioning_flag_after_transition_has_occurred(self):
        scene, _, _ = _make_stub_scene(inject_timer=True)
        scene._transitioning = True
        scene.on_exit()
        assert scene._transitioning is False


# ===========================================================================
# Unit — HUDState seconds_remaining wiring
# ===========================================================================

class TestHUDStateTimerWiring:
    """_build_hud_state must reflect the live timer value on each call."""

    def test_hud_state_seconds_remaining_reflects_injected_timer(self):
        scene, _, _ = _make_stub_scene(duration=300.0, inject_timer=True)
        state = scene._build_hud_state()
        assert state.seconds_remaining == pytest.approx(300.0)

    def test_hud_state_seconds_remaining_decrements_after_manual_timer_tick(self):
        """After advancing the timer, the next _build_hud_state call must report
        the updated value."""
        scene, _, timer = _make_stub_scene(duration=10.0, inject_timer=True)
        scene.on_enter()
        timer.update(4.0)
        state = scene._build_hud_state()
        assert state.seconds_remaining == pytest.approx(6.0)

    def test_hud_state_seconds_remaining_is_zero_when_timer_has_expired(self):
        scene, _, timer = _make_stub_scene(duration=1.0, inject_timer=True)
        scene.on_enter()
        timer.update(99.0)      # large overshoot
        state = scene._build_hud_state()
        assert state.seconds_remaining == pytest.approx(0.0)

    def test_hud_state_returns_fresh_snapshot_on_each_call(self):
        """Two consecutive calls must return independent HUDState objects."""
        scene, _, _ = _make_stub_scene(inject_timer=True)
        s1 = scene._build_hud_state()
        s2 = scene._build_hud_state()
        assert s1 is not s2


# ===========================================================================
# Unit — _on_round_end handler and double-transition guard
# ===========================================================================

class TestRoundEndHandler:
    """_on_round_end delegates to _on_extract_failed; the _transitioning guard
    prevents multiple simultaneous scene replacements."""

    @pytest.fixture
    def mock_sm(self):
        return MagicMock()

    def _scene_with_sm(self, mock_sm, duration: float = 5.0):
        scene, bus, timer = _make_stub_scene(
            duration=duration, inject_timer=True, sm=mock_sm
        )
        return scene, bus, timer

    def test_on_round_end_sets_transitioning_flag(self, mock_sm):
        scene, _, _ = self._scene_with_sm(mock_sm)
        with patch(_PATCH_POST_ROUND), patch(_PATCH_SAVE_MGR):
            scene._on_round_end()
        assert scene._transitioning is True

    def test_on_round_end_calls_scene_replace_exactly_once(self, mock_sm):
        scene, _, _ = self._scene_with_sm(mock_sm)
        with patch(_PATCH_POST_ROUND), patch(_PATCH_SAVE_MGR):
            scene._on_round_end()
        mock_sm.replace.assert_called_once()

    def test_second_round_end_call_is_ignored_by_transitioning_guard(self, mock_sm):
        """Once _transitioning is True the handler must be a no-op."""
        scene, _, _ = self._scene_with_sm(mock_sm)
        with patch(_PATCH_POST_ROUND), patch(_PATCH_SAVE_MGR):
            scene._on_round_end()   # first — sets guard
            scene._on_round_end()   # second — should be ignored
        mock_sm.replace.assert_called_once()

    def test_on_extract_failed_is_also_blocked_after_round_end(self, mock_sm):
        """A follow-up extraction_failed event must not trigger a second replace."""
        scene, _, _ = self._scene_with_sm(mock_sm)
        with patch(_PATCH_POST_ROUND), patch(_PATCH_SAVE_MGR):
            scene._on_round_end()
            scene._on_extract_failed()
        mock_sm.replace.assert_called_once()

    def test_on_player_dead_is_also_blocked_after_round_end(self, mock_sm):
        """Player-death handler must also be blocked once _transitioning is set."""
        scene, _, _ = self._scene_with_sm(mock_sm)
        with patch(_PATCH_POST_ROUND), patch(_PATCH_SAVE_MGR):
            scene._on_round_end()
            scene._on_player_dead()
        mock_sm.replace.assert_called_once()

    def test_on_exit_clears_transitioning_so_next_round_can_transition(self, mock_sm):
        scene, _, _ = self._scene_with_sm(mock_sm)
        with patch(_PATCH_POST_ROUND), patch(_PATCH_SAVE_MGR):
            scene._on_round_end()
        scene.on_exit()
        assert scene._transitioning is False

    def test_round_end_passes_a_post_round_instance_to_replace(self, mock_sm):
        scene, _, _ = self._scene_with_sm(mock_sm)
        with patch(_PATCH_POST_ROUND) as MockPR, patch(_PATCH_SAVE_MGR):
            scene._on_round_end()
        passed = mock_sm.replace.call_args[0][0]
        assert passed is MockPR.return_value


# ===========================================================================
# Integration — EventBus → GameScene chain
# ===========================================================================

class TestRoundTimerEventIntegration:
    """Verify that events flowing through the EventBus reach the correct
    GameScene handlers and produce the expected observable side-effects."""

    @pytest.fixture
    def mock_sm(self):
        return MagicMock()

    def test_round_end_published_via_bus_triggers_scene_replace(self, mock_sm):
        """Publishing 'round_end' on the shared bus must cause sm.replace."""
        scene, bus, _ = _make_stub_scene(inject_timer=True, sm=mock_sm)
        # In stub mode subscriptions aren't wired — wire them manually
        bus.subscribe("round_end", scene._on_round_end)
        with patch(_PATCH_POST_ROUND), patch(_PATCH_SAVE_MGR):
            bus.publish("round_end")
        mock_sm.replace.assert_called_once()

    def test_multiple_round_end_events_on_bus_cause_only_one_replace(self, mock_sm):
        """The double-transition guard must hold even when the bus fires twice."""
        scene, bus, _ = _make_stub_scene(inject_timer=True, sm=mock_sm)
        bus.subscribe("round_end", scene._on_round_end)
        with patch(_PATCH_POST_ROUND), patch(_PATCH_SAVE_MGR):
            bus.publish("round_end")
            bus.publish("round_end")
        mock_sm.replace.assert_called_once()

    def test_round_warning_event_emitted_when_timer_crosses_threshold(self):
        """When the timer's seconds_remaining drops to TIMER_WARN_SECS the bus
        must receive exactly one 'round_warning' event."""
        bus = EventBus()
        warnings: list[int] = []
        bus.subscribe(
            "round_warning",
            lambda seconds_remaining: warnings.append(seconds_remaining),
        )
        timer = RoundTimer(bus, duration=float(TIMER_WARN_SECS) + 5.0)
        timer.start()
        timer.update(10.0)      # crosses TIMER_WARN_SECS
        assert len(warnings) == 1

    def test_timer_decrements_when_update_called_through_update_full(self):
        """GameScene.update() must tick the round timer when _full_init is True."""
        scene, _, timer = _make_ticking_scene(duration=10.0)
        scene.on_enter()
        scene.update(2.0)
        assert timer.seconds_remaining == pytest.approx(8.0)

    def test_timer_does_not_tick_when_game_update_is_never_called(self):
        """Skipping update() (simulating a paused scene on the stack) must leave
        the timer unchanged."""
        scene, _, timer = _make_stub_scene(duration=10.0, inject_timer=True)
        scene.on_enter()
        # Two simulated frames where GameScene.update() is never invoked
        # (i.e. a PauseMenu is on top of the SceneStack)
        assert timer.seconds_remaining == pytest.approx(10.0)

    def test_timer_emits_round_end_when_fully_expired_via_update_full(self, mock_sm):
        """When _update_full ticks the timer to zero, 'round_end' must be published."""
        bus = EventBus()
        ends: list[bool] = []
        bus.subscribe("round_end", lambda **kw: ends.append(True))

        timer = RoundTimer(bus, duration=2.0)
        scene = GameScene(event_bus=bus, settings=Settings())
        scene._round_timer = timer
        scene._full_init = True
        scene.player.alive = True
        scene._sm = mock_sm

        scene.on_enter()
        with patch(_PATCH_POST_ROUND), patch(_PATCH_SAVE_MGR):
            scene.update(5.0)       # overshoot to zero
        assert len(ends) == 1


# ===========================================================================
# End-to-end — complete round timer flow
# ===========================================================================

class TestRoundTimerEndToEndFlow:
    """Trace the full lifecycle of one game round from scene entry to the
    forced-extraction transition at time-zero."""

    def test_complete_round_flow_enter_tick_warn_end_replace(self):
        """Simulate a full (abbreviated) round:
        1. on_enter resets + starts the timer.
        2. Partial updates do not fire round_warning while above the threshold.
        3. An update crossing TIMER_WARN_SECS fires exactly one round_warning.
        4. A final update that overshoots zero fires round_end.
        5. GameScene's _on_round_end calls sm.replace with a PostRound scene.
        """
        mock_sm = MagicMock()
        # Duration is 5 s above the warning threshold for a short test
        duration = float(TIMER_WARN_SECS) + 5.0
        scene, bus, timer = _make_ticking_scene(duration=duration, sm=mock_sm)

        warnings: list[int] = []
        ends: list[bool] = []
        bus.subscribe("round_warning", lambda seconds_remaining: warnings.append(seconds_remaining))
        bus.subscribe("round_end", lambda **kw: ends.append(True))
        # Wire the handler as _init_full would do in production
        bus.subscribe("round_end", scene._on_round_end)

        # ── Phase 1: enter ──────────────────────────────────────────────
        scene.on_enter()
        assert timer.seconds_remaining == pytest.approx(duration)
        assert not timer.is_expired

        # ── Phase 2: tick partway — still above threshold ───────────────
        scene.update(3.0)
        assert len(warnings) == 0

        # ── Phase 3: cross the warning threshold ────────────────────────
        scene.update(5.0)       # drops below TIMER_WARN_SECS
        assert len(warnings) == 1

        # ── Phase 4: overshoot to zero ──────────────────────────────────
        with patch(_PATCH_POST_ROUND), patch(_PATCH_SAVE_MGR):
            scene.update(float(TIMER_WARN_SECS) + 10.0)

        assert len(ends) == 1
        assert timer.is_expired
        mock_sm.replace.assert_called_once()

    def test_timer_resets_and_restarts_cleanly_on_scene_re_entry_after_expiry(self):
        """After on_exit + on_enter the timer is restored to full duration and
        running again so the next round behaves identically to the first."""
        duration = 5.0
        scene, _, timer = _make_stub_scene(duration=duration, inject_timer=True)

        # ── First round: expire the timer ───────────────────────────────
        scene.on_enter()
        timer.update(duration)      # expire
        assert timer.is_expired
        assert timer.seconds_remaining == pytest.approx(0.0)

        # ── Exit resets ─────────────────────────────────────────────────
        scene.on_exit()
        assert not timer.is_expired
        assert timer.seconds_remaining == pytest.approx(duration)

        # ── Second round: timer counts down from full duration again ────
        scene.on_enter()
        timer.update(1.0)
        assert timer.seconds_remaining == pytest.approx(duration - 1.0)
        assert not timer.is_expired
