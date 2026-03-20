"""Tests for the ChallengeWidget HUD sub-renderer.

Covers:
  - ChallengeWidget initialises with a default and custom rect
  - update() replaces the internal challenge list
  - update(None) converts to an empty list without raising
  - draw() renders a header and zero-to-many challenge rows without crashing
  - Completed challenges are handled (completed=True)
  - Challenges with target=0 do not cause division by zero
  - Only up to _MAX_VISIBLE (3) challenges are rendered; extras are truncated
  - ChallengeSystem.get_active_challenges() returns ChallengeInfo objects
    that the ChallengeWidget accepts correctly (integration)

# Run: pytest tests/test_challenge_widget.py
"""
from __future__ import annotations

import pytest
import pygame

from src.ui.challenge_widget import ChallengeWidget, _MAX_VISIBLE
from src.ui.hud_state import ChallengeInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _surface() -> pygame.Surface:
    return pygame.Surface((400, 300))


def _rect() -> pygame.Rect:
    return pygame.Rect(1064, 212, 200, 200)


def _challenge(
    name: str = "Eliminate 5 enemies",
    progress: int = 0,
    target: int = 5,
    completed: bool = False,
) -> ChallengeInfo:
    return ChallengeInfo(name=name, progress=progress, target=target, completed=completed)


# ---------------------------------------------------------------------------
# Unit: initialisation
# ---------------------------------------------------------------------------

class TestChallengeWidgetInit:
    def test_default_rect_is_non_zero(self):
        cw = ChallengeWidget()
        assert cw._rect.width > 0
        assert cw._rect.height > 0

    def test_custom_rect_stored(self):
        r = _rect()
        cw = ChallengeWidget(r)
        assert cw._rect == r

    def test_initial_challenge_list_is_empty(self):
        cw = ChallengeWidget()
        assert cw._challenges == []

    def test_font_not_initialised_until_draw(self):
        cw = ChallengeWidget()
        assert cw._font is None


# ---------------------------------------------------------------------------
# Unit: update()
# ---------------------------------------------------------------------------

class TestChallengeWidgetUpdate:
    def test_update_with_empty_list_stores_empty_list(self):
        cw = ChallengeWidget()
        cw.update([])
        assert cw._challenges == []

    def test_update_with_none_stores_empty_list(self):
        cw = ChallengeWidget()
        cw.update(None)
        assert cw._challenges == []

    def test_update_with_one_challenge_stores_it(self):
        cw = ChallengeWidget()
        ch = _challenge()
        cw.update([ch])
        assert len(cw._challenges) == 1

    def test_update_with_three_challenges_stores_all(self):
        cw = ChallengeWidget()
        challenges = [_challenge(f"Challenge {i}", i, 5) for i in range(3)]
        cw.update(challenges)
        assert len(cw._challenges) == 3

    def test_update_replaces_previous_challenges(self):
        cw = ChallengeWidget()
        cw.update([_challenge("Old")])
        cw.update([_challenge("New A"), _challenge("New B")])
        assert len(cw._challenges) == 2
        assert cw._challenges[0].name == "New A"

    def test_update_makes_a_copy_not_a_reference(self):
        cw = ChallengeWidget()
        source = [_challenge()]
        cw.update(source)
        source.append(_challenge("Extra"))
        # Widget's internal list must not be affected by mutation of source
        assert len(cw._challenges) == 1


# ---------------------------------------------------------------------------
# Draw smoke tests
# ---------------------------------------------------------------------------

class TestChallengeWidgetDraw:
    def test_draw_with_no_challenges_does_not_crash(self):
        cw = ChallengeWidget(_rect())
        cw.update([])
        cw.draw(_surface())

    def test_draw_with_one_incomplete_challenge_does_not_crash(self):
        cw = ChallengeWidget(_rect())
        cw.update([_challenge("Kill 5 robots", progress=2, target=5)])
        cw.draw(_surface())

    def test_draw_with_max_visible_challenges_does_not_crash(self):
        cw = ChallengeWidget(_rect())
        challenges = [_challenge(f"Task {i}", i, 5) for i in range(_MAX_VISIBLE)]
        cw.update(challenges)
        cw.draw(_surface())

    def test_draw_with_more_than_max_visible_does_not_crash(self):
        """Extra challenges beyond _MAX_VISIBLE are silently truncated."""
        cw = ChallengeWidget(_rect())
        challenges = [_challenge(f"Task {i}", i, 5) for i in range(_MAX_VISIBLE + 3)]
        cw.update(challenges)
        cw.draw(_surface())

    def test_draw_with_completed_challenge_does_not_crash(self):
        cw = ChallengeWidget(_rect())
        cw.update([_challenge("Kill 5", progress=5, target=5, completed=True)])
        cw.draw(_surface())

    def test_draw_with_zero_target_does_not_crash(self):
        """target=0 must not cause division by zero in the progress bar logic."""
        cw = ChallengeWidget(_rect())
        cw.update([_challenge("Unknown goal", progress=0, target=0)])
        cw.draw(_surface())

    def test_draw_with_partial_progress_does_not_crash(self):
        cw = ChallengeWidget(_rect())
        cw.update([_challenge("Loot 3 items", progress=1, target=3)])
        cw.draw(_surface())

    def test_draw_initialises_font_lazily(self):
        cw = ChallengeWidget(_rect())
        assert cw._font is None
        cw.draw(_surface())
        assert cw._font is not None

    def test_draw_twice_does_not_crash(self):
        """Second draw call must be idempotent."""
        cw = ChallengeWidget(_rect())
        cw.update([_challenge()])
        surf = _surface()
        cw.draw(surf)
        cw.draw(surf)

    def test_draw_with_all_challenges_completed_does_not_crash(self):
        cw = ChallengeWidget(_rect())
        completed = [
            _challenge(f"Done {i}", target=5, progress=5, completed=True)
            for i in range(_MAX_VISIBLE)
        ]
        cw.update(completed)
        cw.draw(_surface())

    def test_draw_challenge_with_progress_equal_to_target_does_not_crash(self):
        cw = ChallengeWidget(_rect())
        cw.update([_challenge("Almost", progress=5, target=5, completed=False)])
        cw.draw(_surface())


# ---------------------------------------------------------------------------
# Unit: _MAX_VISIBLE constant
# ---------------------------------------------------------------------------

class TestMaxVisibleConstant:
    def test_max_visible_is_three(self):
        assert _MAX_VISIBLE == 3

    def test_exactly_max_visible_challenges_all_rendered_without_truncation(self):
        """A list of exactly _MAX_VISIBLE entries is fully displayed."""
        cw = ChallengeWidget(_rect())
        challenges = [_challenge(f"T{i}") for i in range(_MAX_VISIBLE)]
        cw.update(challenges)
        # Internal list stores all entries; draw slices to [:_MAX_VISIBLE]
        assert len(cw._challenges) == _MAX_VISIBLE


# ---------------------------------------------------------------------------
# Integration: ChallengeSystem → ChallengeInfo → ChallengeWidget
# ---------------------------------------------------------------------------

class TestChallengeSystemIntegration:
    def test_challenge_system_get_active_returns_challenge_info_list(self):
        from src.core.event_bus import EventBus
        from src.systems.challenge_system import ChallengeSystem

        bus = EventBus()
        pool = [
            {
                "id": "kill_5",
                "description": "Eliminate 5 robots",
                "criteria_type": "enemy_killed",
                "target": 5,
                "zone_filter": None,
                "reward_xp": 100,
                "reward_money": 50,
            }
        ]
        cs = ChallengeSystem(bus, challenges_per_round=1, rng_seed=42)
        cs.load_pool_from_list(pool)

        infos = cs.get_active_challenges()
        assert len(infos) == 1
        assert isinstance(infos[0], ChallengeInfo)

    def test_challenge_widget_accepts_challenge_system_output(self):
        from src.core.event_bus import EventBus
        from src.systems.challenge_system import ChallengeSystem

        bus = EventBus()
        pool = [
            {
                "id": "kill_3",
                "description": "Kill 3 enemies",
                "criteria_type": "enemy_killed",
                "target": 3,
                "zone_filter": None,
                "reward_xp": 60,
                "reward_money": 30,
            }
        ]
        cs = ChallengeSystem(bus, challenges_per_round=1, rng_seed=0)
        cs.load_pool_from_list(pool)

        # Simulate 2 kills
        bus.emit('enemy_killed')
        bus.emit('enemy_killed')

        infos = cs.get_active_challenges()
        cw = ChallengeWidget(_rect())
        cw.update(infos)
        cw.draw(_surface())   # must not crash

    def test_challenge_progress_reflected_in_challenge_info(self):
        from src.core.event_bus import EventBus
        from src.systems.challenge_system import ChallengeSystem

        bus = EventBus()
        pool = [
            {
                "id": "loot_2",
                "description": "Pick up 2 items",
                "criteria_type": "item_picked_up",
                "target": 2,
                "zone_filter": None,
                "reward_xp": 40,
                "reward_money": 20,
            }
        ]
        cs = ChallengeSystem(bus, challenges_per_round=1, rng_seed=0)
        cs.load_pool_from_list(pool)

        bus.emit('item_picked_up')
        infos = cs.get_active_challenges()
        assert infos[0].progress == 1
        assert infos[0].target == 2
        assert not infos[0].completed

    def test_completed_challenge_reflected_in_challenge_info(self):
        from src.core.event_bus import EventBus
        from src.systems.challenge_system import ChallengeSystem

        bus = EventBus()
        pool = [
            {
                "id": "kill_1",
                "description": "Kill 1 enemy",
                "criteria_type": "enemy_killed",
                "target": 1,
                "zone_filter": None,
                "reward_xp": 25,
                "reward_money": 10,
            }
        ]
        cs = ChallengeSystem(bus, challenges_per_round=1, rng_seed=0)
        cs.load_pool_from_list(pool)

        bus.emit('enemy_killed')
        infos = cs.get_active_challenges()
        assert infos[0].completed is True
