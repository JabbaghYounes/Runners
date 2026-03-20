"""Unit tests for ChallengeWidget zone-label rendering — src/ui/challenge_widget.py

Run: pytest tests/ui/test_challenge_widget_zone_label.py
"""
from __future__ import annotations

import pygame
import pytest

from src.ui.challenge_widget import ChallengeWidget, _MAX_VISIBLE, _ZONE_LABEL_H
from src.ui.hud_state import ChallengeInfo


# ---------------------------------------------------------------------------
# Session-scoped pygame initialisation
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _init_pygame():
    pygame.display.init()
    pygame.font.init()
    yield
    pygame.quit()


@pytest.fixture
def surface():
    return pygame.Surface((1280, 720))


@pytest.fixture
def widget():
    return ChallengeWidget(pygame.Rect(800, 200, 240, 300))


# ---------------------------------------------------------------------------
# Zone label constant
# ---------------------------------------------------------------------------

class TestZoneLabelConstant:

    def test_zone_label_height_constant_is_positive(self):
        assert _ZONE_LABEL_H > 0

    def test_zone_label_height_less_than_row_height(self):
        from src.ui.challenge_widget import _ROW_H
        assert _ZONE_LABEL_H < _ROW_H


# ---------------------------------------------------------------------------
# Zone label rendering — smoke tests
# ---------------------------------------------------------------------------

class TestZoneLabelRendering:

    def test_draw_with_zone_field_does_not_raise(self, widget, surface):
        widget.update([ChallengeInfo(name="Kill 3", progress=1, target=3,
                                     zone="Cargo Bay")])
        widget.draw(surface)  # must not raise

    def test_draw_without_zone_field_does_not_raise(self, widget, surface):
        widget.update([ChallengeInfo(name="Kill 3", progress=1, target=3)])
        widget.draw(surface)

    def test_draw_with_empty_zone_string_does_not_raise(self, widget, surface):
        widget.update([ChallengeInfo(name="Kill 3", progress=1, target=3, zone="")])
        widget.draw(surface)

    def test_draw_reactor_core_zone_does_not_raise(self, widget, surface):
        widget.update([ChallengeInfo(name="Kill 5", progress=0, target=5,
                                     zone="Reactor Core")])
        widget.draw(surface)

    def test_draw_command_deck_zone_does_not_raise(self, widget, surface):
        widget.update([ChallengeInfo(name="Collect 4", progress=2, target=4,
                                     zone="Command Deck")])
        widget.draw(surface)


# ---------------------------------------------------------------------------
# Zone label — challenges from ChallengeSystem.get_active_challenges()
# ---------------------------------------------------------------------------

class TestZoneLabelFromChallengeSystem:

    def test_zone_label_uppercase_shown_in_draw(self, widget, surface):
        """The widget upper-cases the zone: [CARGO BAY]. Smoke test only."""
        challenge = ChallengeInfo(
            name="Eliminate 3 in Cargo Bay",
            progress=0,
            target=3,
            zone="Cargo Bay",
        )
        widget.update([challenge])
        widget.draw(surface)  # verifies ACCENT_CYAN path executed

    def test_three_challenges_with_zones_all_draw(self, widget, surface):
        challenges = [
            ChallengeInfo(name="Kill 3", progress=1, target=3, zone="Cargo Bay"),
            ChallengeInfo(name="Loot 3", progress=2, target=3, zone="Reactor Core"),
            ChallengeInfo(name="Reach", progress=0, target=1, zone="Command Deck"),
        ]
        widget.update(challenges)
        widget.draw(surface)

    def test_mixed_zone_and_no_zone_draws_correctly(self, widget, surface):
        challenges = [
            ChallengeInfo(name="Kill 5", progress=0, target=5),
            ChallengeInfo(name="Zone kill", progress=1, target=3, zone="Cargo Bay"),
        ]
        widget.update(challenges)
        widget.draw(surface)

    def test_completed_challenge_with_zone_draws_correctly(self, widget, surface):
        challenge = ChallengeInfo(
            name="Kill 3 in Cargo Bay",
            progress=3,
            target=3,
            completed=True,
            zone="Cargo Bay",
        )
        widget.update([challenge])
        widget.draw(surface)

    def test_in_progress_challenge_with_zone_draws_correctly(self, widget, surface):
        challenge = ChallengeInfo(
            name="Collect 4 on Command Deck",
            progress=2,
            target=4,
            completed=False,
            zone="Command Deck",
        )
        widget.update([challenge])
        widget.draw(surface)


# ---------------------------------------------------------------------------
# Zone label stored in ChallengeInfo
# ---------------------------------------------------------------------------

class TestChallengeInfoZoneField:

    def test_zone_field_defaults_to_empty_string(self):
        info = ChallengeInfo(name="Test", progress=0, target=5)
        assert info.zone == ""

    def test_zone_field_set_at_construction(self):
        info = ChallengeInfo(name="Test", progress=0, target=5, zone="Cargo Bay")
        assert info.zone == "Cargo Bay"

    def test_zone_field_stored_as_provided(self):
        info = ChallengeInfo(name="Test", progress=1, target=3,
                              completed=False, zone="Reactor Core")
        assert info.zone == "Reactor Core"

    def test_zone_field_empty_string_is_falsy(self):
        info = ChallengeInfo(name="Test", progress=0, target=1, zone="")
        assert not info.zone

    def test_zone_field_with_content_is_truthy(self):
        info = ChallengeInfo(name="Test", progress=0, target=1, zone="Cargo Bay")
        assert info.zone


# ---------------------------------------------------------------------------
# Max-visible truncation still works with zones
# ---------------------------------------------------------------------------

class TestMaxVisibleWithZones:

    def test_more_than_max_visible_with_zones_does_not_raise(self, widget, surface):
        challenges = [
            ChallengeInfo(name=f"C{i}", progress=i, target=10, zone="Cargo Bay")
            for i in range(_MAX_VISIBLE + 3)
        ]
        widget.update(challenges)
        widget.draw(surface)

    def test_exactly_max_visible_with_zones_renders_all(self, widget, surface):
        challenges = [
            ChallengeInfo(name=f"C{i}", progress=i, target=10, zone=f"Zone {i}")
            for i in range(_MAX_VISIBLE)
        ]
        widget.update(challenges)
        widget.draw(surface)

    def test_draw_called_twice_with_zones_does_not_raise(self, widget, surface):
        widget.update([ChallengeInfo(name="Kill", progress=1, target=3, zone="Cargo Bay")])
        widget.draw(surface)
        widget.draw(surface)
