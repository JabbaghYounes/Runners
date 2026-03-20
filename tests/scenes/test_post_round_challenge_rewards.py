"""Unit tests for PostRound challenge reward integration — src/scenes/post_round.py

Tests that challenge bonus XP, money, and item rewards are applied correctly
by PostRound when a challenge_system is provided.

Run: pytest tests/scenes/test_post_round_challenge_rewards.py
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from src.core.round_summary import RoundSummary
from src.scenes.post_round import PostRound


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _summary(**overrides) -> RoundSummary:
    defaults = dict(
        extraction_status="success",
        extracted_items=[],
        xp_earned=0,
        money_earned=0,
        kills=2,
        challenges_completed=0,
        challenges_total=3,
        level_before=1,
    )
    defaults.update(overrides)
    return RoundSummary(**defaults)


def _active_challenge(
    id: str = "ch1",
    description: str = "Kill 3 enemies",
    reward_xp: int = 100,
    reward_money: int = 150,
    reward_item_id: str | None = None,
) -> object:
    """Create a minimal stub object that looks like an _ActiveChallenge."""
    ch = MagicMock()
    ch.id = id
    ch.description = description
    ch.reward_xp = reward_xp
    ch.reward_money = reward_money
    ch.reward_item_id = reward_item_id
    ch.completed = True
    return ch


def _make_challenge_system(completed: list = None) -> MagicMock:
    cs = MagicMock()
    cs.get_completed_challenges.return_value = list(completed or [])
    return cs


def _make_xp_system(level: int = 2) -> MagicMock:
    xs = MagicMock()
    xs.level = level
    return xs


def _make_currency() -> MagicMock:
    return MagicMock()


def _build_post_round(
    summary: RoundSummary,
    challenge_system=None,
    xp_system=None,
    currency=None,
    save_manager=None,
    audio_system=None,
) -> PostRound:
    return PostRound(
        summary=summary,
        xp_system=xp_system or _make_xp_system(),
        currency=currency or _make_currency(),
        save_manager=save_manager or MagicMock(),
        scene_manager=MagicMock(),
        audio_system=audio_system or MagicMock(),
        challenge_system=challenge_system,
    )


# ---------------------------------------------------------------------------
# No challenge_system provided
# ---------------------------------------------------------------------------

class TestNoChallengeSystem:

    def test_no_challenge_system_does_not_raise(self):
        s = _summary()
        _build_post_round(s, challenge_system=None)  # must not raise

    def test_no_challenge_system_bonus_xp_stays_zero(self):
        s = _summary()
        _build_post_round(s, challenge_system=None)
        assert s.challenge_bonus_xp == 0

    def test_no_challenge_system_bonus_money_stays_zero(self):
        s = _summary()
        _build_post_round(s, challenge_system=None)
        assert s.challenge_bonus_money == 0

    def test_no_challenge_system_bonus_items_stays_empty(self):
        s = _summary()
        _build_post_round(s, challenge_system=None)
        assert s.challenge_bonus_items == []

    def test_no_challenge_system_base_xp_still_awarded(self):
        xs = _make_xp_system()
        s = _summary(xp_earned=300)
        _build_post_round(s, challenge_system=None, xp_system=xs)
        xs.award.assert_called_once_with(300)

    def test_no_challenge_system_base_money_still_added(self):
        cur = _make_currency()
        s = _summary(money_earned=500)
        _build_post_round(s, challenge_system=None, currency=cur)
        cur.add.assert_called_once_with(500)


# ---------------------------------------------------------------------------
# challenge_system provided — XP rewards
# ---------------------------------------------------------------------------

class TestChallengeRewardXp:

    def test_single_completed_challenge_xp_awarded(self):
        xs = _make_xp_system()
        s = _summary()
        cs = _make_challenge_system([_active_challenge(reward_xp=200)])
        _build_post_round(s, challenge_system=cs, xp_system=xs)
        # award called for base xp (0) + challenge xp (200)
        assert call(200) in xs.award.call_args_list

    def test_two_completed_challenges_each_xp_awarded(self):
        xs = _make_xp_system()
        s = _summary()
        cs = _make_challenge_system([
            _active_challenge(id="c1", reward_xp=100),
            _active_challenge(id="c2", reward_xp=150),
        ])
        _build_post_round(s, challenge_system=cs, xp_system=xs)
        assert call(100) in xs.award.call_args_list
        assert call(150) in xs.award.call_args_list

    def test_challenge_bonus_xp_accumulated_in_summary(self):
        s = _summary()
        cs = _make_challenge_system([
            _active_challenge(id="c1", reward_xp=100),
            _active_challenge(id="c2", reward_xp=75),
        ])
        _build_post_round(s, challenge_system=cs)
        assert s.challenge_bonus_xp == 175

    def test_challenge_bonus_xp_single_challenge(self):
        s = _summary()
        cs = _make_challenge_system([_active_challenge(reward_xp=300)])
        _build_post_round(s, challenge_system=cs)
        assert s.challenge_bonus_xp == 300

    def test_zero_reward_xp_adds_nothing(self):
        xs = _make_xp_system()
        s = _summary()
        cs = _make_challenge_system([_active_challenge(reward_xp=0)])
        _build_post_round(s, challenge_system=cs, xp_system=xs)
        assert s.challenge_bonus_xp == 0

    def test_no_completed_challenges_no_bonus_xp(self):
        s = _summary()
        cs = _make_challenge_system([])
        _build_post_round(s, challenge_system=cs)
        assert s.challenge_bonus_xp == 0


# ---------------------------------------------------------------------------
# challenge_system provided — money rewards
# ---------------------------------------------------------------------------

class TestChallengeRewardMoney:

    def test_single_completed_challenge_money_added(self):
        cur = _make_currency()
        s = _summary()
        cs = _make_challenge_system([_active_challenge(reward_money=350)])
        _build_post_round(s, challenge_system=cs, currency=cur)
        assert call(350) in cur.add.call_args_list

    def test_two_completed_challenges_each_money_added(self):
        cur = _make_currency()
        s = _summary()
        cs = _make_challenge_system([
            _active_challenge(id="c1", reward_money=200),
            _active_challenge(id="c2", reward_money=300),
        ])
        _build_post_round(s, challenge_system=cs, currency=cur)
        assert call(200) in cur.add.call_args_list
        assert call(300) in cur.add.call_args_list

    def test_challenge_bonus_money_accumulated_in_summary(self):
        s = _summary()
        cs = _make_challenge_system([
            _active_challenge(id="c1", reward_money=100),
            _active_challenge(id="c2", reward_money=250),
        ])
        _build_post_round(s, challenge_system=cs)
        assert s.challenge_bonus_money == 350

    def test_zero_reward_money_adds_nothing(self):
        cur = _make_currency()
        s = _summary()
        cs = _make_challenge_system([_active_challenge(reward_money=0)])
        _build_post_round(s, challenge_system=cs, currency=cur)
        assert s.challenge_bonus_money == 0

    def test_no_completed_challenges_no_bonus_money(self):
        s = _summary()
        cs = _make_challenge_system([])
        _build_post_round(s, challenge_system=cs)
        assert s.challenge_bonus_money == 0


# ---------------------------------------------------------------------------
# challenge_system provided — item rewards
# ---------------------------------------------------------------------------

class TestChallengeRewardItems:

    _ITEM_DB_PATH = "src.inventory.item_database.ItemDatabase"

    def _fake_item_db(self, item_id: str):
        """Return a (mock_db, fake_item) pair for patching ItemDatabase."""
        fake_item = MagicMock()
        fake_item.item_id = item_id
        fake_item.monetary_value = 100
        fake_item.name = item_id

        mock_db = MagicMock()
        mock_db.create.return_value = fake_item
        return mock_db, fake_item

    def test_reward_item_appended_to_challenge_bonus_items(self):
        mock_db, fake_item = self._fake_item_db("medkit_basic")
        s = _summary()
        cs = _make_challenge_system([
            _active_challenge(reward_item_id="medkit_basic")
        ])
        with patch(self._ITEM_DB_PATH) as MockDB:
            MockDB.instance.return_value = mock_db
            _build_post_round(s, challenge_system=cs)
        assert "medkit_basic" in s.challenge_bonus_items

    def test_reward_item_appended_to_extracted_items(self):
        mock_db, fake_item = self._fake_item_db("scope_red_dot")
        s = _summary()
        cs = _make_challenge_system([
            _active_challenge(reward_item_id="scope_red_dot")
        ])
        with patch(self._ITEM_DB_PATH) as MockDB:
            MockDB.instance.return_value = mock_db
            _build_post_round(s, challenge_system=cs)
        assert fake_item in s.extracted_items

    def test_two_item_rewards_both_appended(self):
        items = {}
        for item_id in ("medkit_basic", "ammo_rifle"):
            fake = MagicMock()
            fake.item_id = item_id
            fake.name = item_id
            items[item_id] = fake

        mock_db = MagicMock()
        mock_db.create.side_effect = lambda iid: items[iid]

        s = _summary()
        cs = _make_challenge_system([
            _active_challenge(id="c1", reward_item_id="medkit_basic"),
            _active_challenge(id="c2", reward_item_id="ammo_rifle"),
        ])
        with patch(self._ITEM_DB_PATH) as MockDB:
            MockDB.instance.return_value = mock_db
            _build_post_round(s, challenge_system=cs)
        assert "medkit_basic" in s.challenge_bonus_items
        assert "ammo_rifle" in s.challenge_bonus_items

    def test_null_reward_item_id_does_not_append_to_items(self):
        s = _summary()
        cs = _make_challenge_system([
            _active_challenge(reward_item_id=None)
        ])
        _build_post_round(s, challenge_system=cs)
        assert s.challenge_bonus_items == []
        assert s.extracted_items == []

    def test_unknown_item_id_grants_fallback_money(self):
        """When ItemDatabase cannot resolve reward_item_id, a fallback of 50 cr is granted."""
        mock_db = MagicMock()
        mock_db.create.side_effect = Exception("Unknown item")
        cur = _make_currency()
        s = _summary()
        cs = _make_challenge_system([
            _active_challenge(reward_item_id="nonexistent_item")
        ])
        with patch(self._ITEM_DB_PATH) as MockDB:
            MockDB.instance.return_value = mock_db
            _build_post_round(s, challenge_system=cs, currency=cur)
        # Fallback money should have been added
        _FALLBACK_MONEY = 50
        assert call(_FALLBACK_MONEY) in cur.add.call_args_list

    def test_unknown_item_id_increments_challenge_bonus_money(self):
        mock_db = MagicMock()
        mock_db.create.side_effect = Exception("Unknown item")
        s = _summary()
        cs = _make_challenge_system([
            _active_challenge(reward_item_id="bad_item_id")
        ])
        with patch(self._ITEM_DB_PATH) as MockDB:
            MockDB.instance.return_value = mock_db
            _build_post_round(s, challenge_system=cs)
        _FALLBACK_MONEY = 50
        assert s.challenge_bonus_money >= _FALLBACK_MONEY

    def test_unknown_item_id_does_not_append_to_challenge_bonus_items(self):
        mock_db = MagicMock()
        mock_db.create.side_effect = Exception("Unknown item")
        s = _summary()
        cs = _make_challenge_system([
            _active_challenge(reward_item_id="bad_id")
        ])
        with patch(self._ITEM_DB_PATH) as MockDB:
            MockDB.instance.return_value = mock_db
            _build_post_round(s, challenge_system=cs)
        assert s.challenge_bonus_items == []


# ---------------------------------------------------------------------------
# Idempotency — rewards applied once only
# ---------------------------------------------------------------------------

class TestRewardIdempotency:

    def test_xp_not_re_awarded_after_update_calls(self):
        xs = _make_xp_system()
        s = _summary()
        cs = _make_challenge_system([_active_challenge(reward_xp=200)])
        pr = _build_post_round(s, challenge_system=cs, xp_system=xs)
        pr.update(0.016)
        pr.update(0.016)
        # award(200) should appear exactly once in the call list
        xp_200_calls = [c for c in xs.award.call_args_list if c == call(200)]
        assert len(xp_200_calls) == 1

    def test_money_not_re_added_after_update_calls(self):
        cur = _make_currency()
        s = _summary()
        cs = _make_challenge_system([_active_challenge(reward_money=300)])
        pr = _build_post_round(s, challenge_system=cs, currency=cur)
        pr.update(0.016)
        pr.update(0.016)
        money_300_calls = [c for c in cur.add.call_args_list if c == call(300)]
        assert len(money_300_calls) == 1

    def test_challenge_bonus_xp_not_doubled_by_updates(self):
        s = _summary()
        cs = _make_challenge_system([_active_challenge(reward_xp=100)])
        pr = _build_post_round(s, challenge_system=cs)
        pr.update(0.016)
        pr.update(0.016)
        assert s.challenge_bonus_xp == 100

    def test_challenge_bonus_money_not_doubled_by_updates(self):
        s = _summary()
        cs = _make_challenge_system([_active_challenge(reward_money=150)])
        pr = _build_post_round(s, challenge_system=cs)
        pr.update(0.016)
        assert s.challenge_bonus_money == 150


# ---------------------------------------------------------------------------
# Completed challenges stored for render
# ---------------------------------------------------------------------------

class TestCompletedChallengesStoredForRender:

    def test_completed_challenges_stored_on_scene(self):
        ch = _active_challenge(id="my_challenge")
        cs = _make_challenge_system([ch])
        s = _summary()
        pr = _build_post_round(s, challenge_system=cs)
        assert len(pr._completed_challenges) == 1

    def test_completed_challenge_id_accessible_on_scene(self):
        ch = _active_challenge(id="kill_zone_ch")
        cs = _make_challenge_system([ch])
        s = _summary()
        pr = _build_post_round(s, challenge_system=cs)
        assert pr._completed_challenges[0].id == "kill_zone_ch"

    def test_no_completed_challenges_list_is_empty(self):
        cs = _make_challenge_system([])
        s = _summary()
        pr = _build_post_round(s, challenge_system=cs)
        assert pr._completed_challenges == []

    def test_no_challenge_system_completed_list_is_empty(self):
        s = _summary()
        pr = _build_post_round(s, challenge_system=None)
        assert pr._completed_challenges == []


# ---------------------------------------------------------------------------
# get_completed_challenges() raises — graceful recovery
# ---------------------------------------------------------------------------

class TestGetCompletedChallengesRaisesGracefully:

    def test_exception_in_get_completed_challenges_does_not_crash_post_round(self):
        cs = MagicMock()
        cs.get_completed_challenges.side_effect = RuntimeError("Broken!")
        s = _summary()
        # Must not raise
        pr = _build_post_round(s, challenge_system=cs)

    def test_exception_leaves_bonus_xp_at_zero(self):
        cs = MagicMock()
        cs.get_completed_challenges.side_effect = RuntimeError("Broken!")
        s = _summary()
        _build_post_round(s, challenge_system=cs)
        assert s.challenge_bonus_xp == 0

    def test_exception_leaves_completed_list_empty(self):
        cs = MagicMock()
        cs.get_completed_challenges.side_effect = RuntimeError("Broken!")
        s = _summary()
        pr = _build_post_round(s, challenge_system=cs)
        assert pr._completed_challenges == []


# ---------------------------------------------------------------------------
# level_after includes challenge XP
# ---------------------------------------------------------------------------

class TestLevelAfterIncludesChallengeXp:

    def test_level_after_set_after_challenge_xp_applied(self):
        xs = _make_xp_system(level=5)
        s = _summary()
        cs = _make_challenge_system([_active_challenge(reward_xp=500)])
        pr = _build_post_round(s, challenge_system=cs, xp_system=xs)
        # level_after must be read AFTER all XP (including challenge bonus) applied
        assert s.level_after == 5

    def test_save_called_after_challenge_rewards_applied(self):
        save_mgr = MagicMock()
        s = _summary()
        cs = _make_challenge_system([_active_challenge(reward_xp=100, reward_money=200)])
        _build_post_round(s, challenge_system=cs, save_manager=save_mgr)
        save_mgr.save.assert_called_once()


# ---------------------------------------------------------------------------
# Render smoke test — challenge breakdown in PostRound
# ---------------------------------------------------------------------------

class TestPostRoundRenderWithChallengeBreakdown:

    @pytest.fixture(autouse=True)
    def _init_pygame(self):
        pygame = pytest.importorskip("pygame")
        pygame.display.init()
        pygame.font.init()
        yield
        pygame.quit()

    def test_render_with_completed_challenges_does_not_raise(self):
        import pygame
        screen = pygame.Surface((1280, 720))
        ch = _active_challenge(
            description="Kill 3 in Cargo Bay",
            reward_xp=120,
            reward_money=175,
            reward_item_id=None,
        )
        cs = _make_challenge_system([ch])
        s = _summary(challenges_completed=1, challenges_total=3,
                      challenge_bonus_xp=120, challenge_bonus_money=175)
        pr = _build_post_round(s, challenge_system=cs)
        pr.render(screen)  # must not raise

    def test_render_with_item_reward_listed_does_not_raise(self):
        import pygame
        screen = pygame.Surface((1280, 720))
        ch = _active_challenge(
            description="Collect 3 in Cargo Bay",
            reward_xp=100,
            reward_money=150,
            reward_item_id="medkit_basic",
        )
        cs = _make_challenge_system([ch])
        s = _summary(challenges_completed=1, challenges_total=3)
        with patch("src.inventory.item_database.ItemDatabase") as MockDB:
            fake_item = MagicMock()
            fake_item.item_id = "medkit_basic"
            fake_item.monetary_value = 0
            MockDB.instance.return_value.create.return_value = fake_item
            pr = _build_post_round(s, challenge_system=cs)
        pr.render(screen)

    def test_render_no_challenge_bonus_shows_zero_bonus_lines(self):
        import pygame
        screen = pygame.Surface((1280, 720))
        s = _summary(challenge_bonus_xp=0, challenge_bonus_money=0)
        pr = _build_post_round(s, challenge_system=None)
        pr.render(screen)  # must not raise
