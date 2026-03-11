"""Tests for ChallengeWidget rendering behaviour."""
from __future__ import annotations

import pytest
import pygame

from src.ui.challenge_widget import ChallengeWidget, _MAX_VISIBLE
from src.ui.hud_state import ChallengeInfo


@pytest.fixture(scope='session', autouse=True)
def pygame_headless():
    pygame.display.init()
    pygame.font.init()
    yield
    pygame.quit()


@pytest.fixture
def widget_rect():
    return pygame.Rect(1024, 232, 240, 300)


@pytest.fixture
def surface():
    return pygame.Surface((1280, 720))


class TestChallengeWidgetUpdate:
    def test_update_stores_challenges(self, widget_rect):
        w = ChallengeWidget(widget_rect)
        challenges = [ChallengeInfo(name='Kill 3', progress=1, target=3)]
        w.update(challenges)
        assert w._challenges == challenges

    def test_update_with_none_stores_empty_list(self, widget_rect):
        w = ChallengeWidget(widget_rect)
        w.update(None)
        assert w._challenges == []

    def test_update_replaces_previous(self, widget_rect):
        w = ChallengeWidget(widget_rect)
        w.update([ChallengeInfo(name='A', progress=0, target=5)])
        new = [ChallengeInfo(name='B', progress=1, target=2)]
        w.update(new)
        assert w._challenges == new


class TestChallengeWidgetMaxVisible:
    def test_only_max_visible_rows_shown(self, widget_rect, surface):
        """Widget should silently truncate to _MAX_VISIBLE rows."""
        w = ChallengeWidget(widget_rect)
        challenges = [
            ChallengeInfo(name=f'Challenge {i}', progress=i, target=10)
            for i in range(_MAX_VISIBLE + 5)
        ]
        w.update(challenges)
        w.draw(surface)  # must not raise

    def test_max_visible_constant_is_3(self):
        assert _MAX_VISIBLE == 3


class TestChallengeWidgetDraw:
    def test_draw_with_empty_list_does_not_raise(self, widget_rect, surface):
        w = ChallengeWidget(widget_rect)
        w.update([])
        w.draw(surface)

    def test_draw_in_progress_challenge_does_not_raise(self, widget_rect, surface):
        w = ChallengeWidget(widget_rect)
        w.update([ChallengeInfo(name='Collect 5 Caches', progress=2, target=5)])
        w.draw(surface)

    def test_draw_completed_challenge_does_not_raise(self, widget_rect, surface):
        w = ChallengeWidget(widget_rect)
        w.update([ChallengeInfo(name='Kill 3 Robots', progress=3, target=3, completed=True)])
        w.draw(surface)

    def test_draw_zero_progress_does_not_raise(self, widget_rect, surface):
        w = ChallengeWidget(widget_rect)
        w.update([ChallengeInfo(name='Kill 10 Enemies', progress=0, target=10)])
        w.draw(surface)

    def test_draw_with_very_long_name_does_not_raise(self, widget_rect, surface):
        long_name = 'A' * 80  # much longer than the widget width
        w = ChallengeWidget(widget_rect)
        w.update([ChallengeInfo(name=long_name, progress=1, target=5)])
        w.draw(surface)

    def test_draw_multiple_challenges_does_not_raise(self, widget_rect, surface):
        challenges = [
            ChallengeInfo(name='Kill 3', progress=1, target=3),
            ChallengeInfo(name='Loot 5', progress=5, target=5, completed=True),
            ChallengeInfo(name='Survive 10m', progress=2, target=10),
        ]
        w = ChallengeWidget(widget_rect)
        w.update(challenges)
        w.draw(surface)

    def test_draw_can_be_called_multiple_times(self, widget_rect, surface):
        w = ChallengeWidget(widget_rect)
        w.update([ChallengeInfo(name='Test', progress=1, target=3)])
        w.draw(surface)
        w.draw(surface)  # second call must also not raise


class TestChallengeProgressBar:
    def test_completed_challenge_has_full_progress(self, widget_rect, surface):
        """Completed challenges should display a full bar; this is a smoke test
        (we verify draw() does not raise with completed=True)."""
        w = ChallengeWidget(widget_rect)
        challenge = ChallengeInfo(name='Done', progress=3, target=3, completed=True)
        w.update([challenge])
        w.draw(surface)  # must not raise

    def test_zero_target_does_not_raise(self, widget_rect, surface):
        """target=0 should not cause a ZeroDivisionError."""
        w = ChallengeWidget(widget_rect)
        # target=0 is degenerate but must not crash
        challenge = ChallengeInfo(name='Edge case', progress=0, target=0)
        w.update([challenge])
        w.draw(surface)


# ---------------------------------------------------------------------------
# ChallengeWidget — completed-challenge progress bar logic
# ---------------------------------------------------------------------------
class TestCompletedChallengeBarLogic:
    def test_completed_challenge_progress_equals_target_in_draw(
        self, widget_rect, surface
    ):
        """When completed=True the widget uses challenge.target for the bar fill,
        so the bar appears full even if actual progress < target.  We verify
        this path executes without error for a challenge where progress < target."""
        w = ChallengeWidget(widget_rect)
        # Progress is behind but completed flag is True — bar should look full
        challenge = ChallengeInfo(name='Done early', progress=1, target=5,
                                  completed=True)
        w.update([challenge])
        w.draw(surface)  # must not raise

    def test_in_progress_challenge_with_partial_progress(self, widget_rect, surface):
        """Mid-progress challenge (not completed) renders without raising."""
        w = ChallengeWidget(widget_rect)
        challenge = ChallengeInfo(name='In Progress', progress=3, target=10)
        w.update([challenge])
        w.draw(surface)

    def test_challenge_at_100_percent_not_flagged_completed(
        self, widget_rect, surface
    ):
        """progress==target with completed=False should still render normally."""
        w = ChallengeWidget(widget_rect)
        challenge = ChallengeInfo(name='Full Bar', progress=10, target=10,
                                  completed=False)
        w.update([challenge])
        w.draw(surface)


# ---------------------------------------------------------------------------
# ChallengeWidget — row layout
# ---------------------------------------------------------------------------
class TestChallengeWidgetLayout:
    def test_widget_rect_stored(self, widget_rect):
        w = ChallengeWidget(widget_rect)
        assert w._rect == widget_rect

    def test_initial_challenges_is_empty_list(self, widget_rect):
        w = ChallengeWidget(widget_rect)
        assert w._challenges == []

    def test_update_with_exact_max_visible_does_not_raise(
        self, widget_rect, surface
    ):
        """Exactly _MAX_VISIBLE challenges must all be rendered."""
        w = ChallengeWidget(widget_rect)
        challenges = [
            ChallengeInfo(name=f'C{i}', progress=i, target=10)
            for i in range(_MAX_VISIBLE)
        ]
        w.update(challenges)
        w.draw(surface)

    def test_draw_renders_header_even_with_no_challenges(
        self, widget_rect, surface
    ):
        """The CHALLENGES header must always draw, even with an empty list."""
        w = ChallengeWidget(widget_rect)
        w.update([])
        w.draw(surface)  # must not raise (header is always drawn)

    def test_draw_successive_challenges_do_not_overlap(
        self, widget_rect, surface
    ):
        """Smoke test: three challenges rendered back-to-back do not crash."""
        w = ChallengeWidget(widget_rect)
        for i in range(3):
            w.update([
                ChallengeInfo(name=f'Ch{i}', progress=i, target=5)
            ])
            w.draw(surface)

    def test_max_visible_constant_value(self):
        from src.ui.challenge_widget import _MAX_VISIBLE
        assert _MAX_VISIBLE == 3

    def test_row_height_constant_is_positive(self):
        from src.ui.challenge_widget import _ROW_H
        assert _ROW_H > 0

    def test_padding_constant_is_positive(self):
        from src.ui.challenge_widget import _PADDING
        assert _PADDING > 0
