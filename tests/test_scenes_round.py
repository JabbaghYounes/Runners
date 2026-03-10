"""Tests for ExtractionSummaryScene and GameOverScene."""

from __future__ import annotations

import pygame
import pytest

from src.scenes.extraction_summary import ExtractionSummaryScene
from src.scenes.game_over import GameOverScene


# ======================================================================
# Mock Game object
# ======================================================================


class MockGame:
    """Minimal Game stub for scene tests."""

    def __init__(self) -> None:
        self.screen_width = 1280
        self.screen_height = 720
        self._replaced_scene = None

    def replace_scene(self, scene) -> None:
        self._replaced_scene = scene

    @property
    def last_scene(self):
        return self._replaced_scene


# ======================================================================
# ExtractionSummaryScene tests
# ======================================================================


class TestExtractionSummaryScene:
    @pytest.fixture
    def game(self):
        return MockGame()

    @pytest.fixture
    def result_data(self, sample_success_result):
        return sample_success_result

    def test_init_with_result_data(self, game, result_data):
        scene = ExtractionSummaryScene(game, result_data)
        assert scene.total_value == 400
        assert scene.money_gained == 400
        assert len(scene.items) == 2

    def test_init_with_empty_data(self, game):
        scene = ExtractionSummaryScene(game, {})
        assert scene.total_value == 0
        assert scene.items == []
        assert scene.money_gained == 0

    def test_update_advances_elapsed(self, game, result_data):
        scene = ExtractionSummaryScene(game, result_data)
        scene.update(1.0)
        assert scene._elapsed == pytest.approx(1.0)

    def test_draw_without_crash(self, game, result_data):
        surface = pygame.Surface((1280, 720))
        scene = ExtractionSummaryScene(game, result_data)
        scene.update(0.5)
        # Should not raise
        scene.draw(surface)

    def test_draw_with_empty_data(self, game):
        surface = pygame.Surface((1280, 720))
        scene = ExtractionSummaryScene(game, {})
        scene.update(0.5)
        scene.draw(surface)

    def test_staggered_animation_timing(self, game, result_data):
        scene = ExtractionSummaryScene(game, result_data)

        # At t=0, first section visible, others not
        assert scene._section_visible(0)
        assert not scene._section_visible(1)

        # At t=0.3, first two visible
        scene._elapsed = 0.3
        assert scene._section_visible(0)
        assert scene._section_visible(1)
        assert not scene._section_visible(2)

        # At t=0.9, first four visible
        scene._elapsed = 0.9
        assert scene._section_visible(0)
        assert scene._section_visible(1)
        assert scene._section_visible(2)
        assert scene._section_visible(3)

    def test_count_up_value(self, game, result_data):
        scene = ExtractionSummaryScene(game, result_data)
        scene._elapsed = 0.0

        # Before section delay, value is 0
        assert scene._count_up_value(400, 0) == 0

        # Halfway through count-up
        scene._elapsed = 0.25  # section_index=0 → 0.25s into section
        val = scene._count_up_value(400, 0)
        assert 0 < val < 400

        # After full count-up duration
        scene._elapsed = 0.6
        val = scene._count_up_value(400, 0)
        assert val == 400

    def test_continue_keypress(self, game, result_data):
        scene = ExtractionSummaryScene(game, result_data)
        scene.update(1.0)

        # Simulate Enter key
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        scene.handle_events([event])
        scene.update(0.016)

        # Scene should attempt a transition (may or may not succeed
        # depending on whether HomeBase/MainMenu scenes exist)
        assert scene._continue_pressed

    def test_level_up_detected(self, game):
        data = {
            "items": [],
            "total_value": 0,
            "xp_earned": {},
            "money_gained": 0,
            "level_before": 3,
            "level_after": 4,
        }
        scene = ExtractionSummaryScene(game, data)
        assert scene.level_after > scene.level_before

    def test_no_level_up_when_same_level(self, game, result_data):
        scene = ExtractionSummaryScene(game, result_data)
        assert scene.level_before == scene.level_after

    def test_space_bar_triggers_continue(self, game, result_data):
        scene = ExtractionSummaryScene(game, result_data)
        scene.update(1.0)

        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
        scene.handle_events([event])
        assert scene._continue_pressed

    def test_section_delay_is_0_3_seconds(self, game, result_data):
        scene = ExtractionSummaryScene(game, result_data)
        assert scene.SECTION_DELAY == 0.3

    def test_count_up_duration_is_0_5_seconds(self, game, result_data):
        scene = ExtractionSummaryScene(game, result_data)
        assert scene.COUNT_UP_DURATION == 0.5

    def test_count_up_at_full_returns_target(self, game, result_data):
        scene = ExtractionSummaryScene(game, result_data)
        scene._elapsed = 10.0  # well past all animations
        val = scene._count_up_value(1000, 0)
        assert val == 1000

    def test_draw_with_level_up(self, game):
        surface = pygame.Surface((1280, 720))
        data = {
            "items": [{"name": "Rifle", "rarity": "rare", "value": 500}],
            "total_value": 500,
            "xp_earned": {"bonus": 100},
            "money_gained": 500,
            "level_before": 3,
            "level_after": 4,
        }
        scene = ExtractionSummaryScene(game, data)
        scene.update(2.0)  # all sections visible
        scene.draw(surface)

    def test_draw_with_many_items(self, game):
        surface = pygame.Surface((1280, 720))
        items = [
            {"name": f"Item {i}", "rarity": "common", "value": i * 10}
            for i in range(20)
        ]
        data = {
            "items": items,
            "total_value": sum(i["value"] for i in items),
            "xp_earned": {"test": 50},
            "money_gained": 1000,
            "level_before": 1,
            "level_after": 1,
        }
        scene = ExtractionSummaryScene(game, data)
        scene.update(2.0)
        scene.draw(surface)

    def test_result_data_stored(self, game, result_data):
        scene = ExtractionSummaryScene(game, result_data)
        assert scene.result_data is result_data

    def test_xp_earned_unpacked(self, game, result_data):
        scene = ExtractionSummaryScene(game, result_data)
        assert scene.xp_earned == {"extraction_bonus": 50, "survival": 25}


# ======================================================================
# GameOverScene tests
# ======================================================================


class TestGameOverScene:
    @pytest.fixture
    def game(self):
        return MockGame()

    @pytest.fixture
    def result_data(self, sample_failure_result):
        return sample_failure_result

    def test_init_with_result_data(self, game, result_data):
        scene = GameOverScene(game, result_data)
        assert scene.cause == "eliminated"
        assert len(scene.loot_lost) == 1
        assert scene.xp_retained == 10

    def test_init_with_timeout_cause(self, game):
        data = {
            "cause": "timeout",
            "loot_lost": [],
            "total_lost": 0,
            "xp_retained": 10,
        }
        scene = GameOverScene(game, data)
        assert scene.cause == "timeout"
        assert scene._cause_text == "Time expired"

    def test_init_with_eliminated_cause(self, game, result_data):
        scene = GameOverScene(game, result_data)
        assert scene._cause_text == "You were eliminated"

    def test_draw_without_crash(self, game, result_data):
        surface = pygame.Surface((1280, 720))
        scene = GameOverScene(game, result_data)
        scene.update(2.0)  # Allow fade-in and typing to complete
        scene.draw(surface)

    def test_draw_with_empty_data(self, game):
        surface = pygame.Surface((1280, 720))
        scene = GameOverScene(game, {})
        scene.update(2.0)
        scene.draw(surface)

    def test_fade_in_animation(self, game, result_data):
        scene = GameOverScene(game, result_data)
        assert scene._fade_alpha == 255  # starts fully black

        scene.update(1.0)
        assert scene._fade_alpha < 255  # should have faded

    def test_typewriter_effect(self, game, result_data):
        scene = GameOverScene(game, result_data)

        scene.update(0.0)
        assert scene._cause_chars_shown == 0

        # After enough time for some characters
        scene.update(0.2)  # 0.2s / 0.04s per char = 5 chars
        assert scene._cause_chars_shown == 5

    def test_typewriter_caps_at_text_length(self, game, result_data):
        scene = GameOverScene(game, result_data)
        text_len = len(scene._cause_text)

        # Advance well past typing duration
        scene.update(10.0)
        assert scene._cause_chars_shown == text_len

    def test_retry_button_keypress(self, game, result_data):
        scene = GameOverScene(game, result_data)
        scene.update(1.0)

        # R key triggers retry
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)
        scene.handle_events([event])
        # Should attempt transition (no crash)

    def test_menu_button_keypress(self, game, result_data):
        scene = GameOverScene(game, result_data)
        scene.update(1.0)

        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        scene.handle_events([event])

    def test_three_buttons_created_during_draw(self, game, result_data):
        surface = pygame.Surface((1280, 720))
        scene = GameOverScene(game, result_data)
        scene.update(2.0)
        scene.draw(surface)

        # After draw, button rects should be set
        assert scene._btn_retry_rect is not None
        assert scene._btn_home_rect is not None
        assert scene._btn_menu_rect is not None

    def test_init_with_empty_data_defaults(self, game):
        scene = GameOverScene(game, {})
        assert scene.cause == "eliminated"
        assert scene.loot_lost == []
        assert scene.total_lost == 0
        assert scene.xp_retained == 0

    def test_unknown_cause_uses_fallback_text(self, game):
        scene = GameOverScene(game, {"cause": "unknown_cause"})
        assert scene._cause_text == "Mission failed"

    def test_fade_completes_to_zero(self, game, result_data):
        scene = GameOverScene(game, result_data)
        # Update for long enough that fade should complete
        for _ in range(100):
            scene.update(0.05)
        assert scene._fade_alpha == 0

    def test_elapsed_accumulates(self, game, result_data):
        scene = GameOverScene(game, result_data)
        scene.update(0.5)
        scene.update(0.3)
        assert scene._elapsed == pytest.approx(0.8)

    def test_loot_lost_items_stored(self, game, result_data):
        scene = GameOverScene(game, result_data)
        assert len(scene.loot_lost) == 1
        assert scene.loot_lost[0]["name"] == "Rifle Mk-II"

    def test_draw_with_no_loot_lost(self, game):
        surface = pygame.Surface((1280, 720))
        data = {
            "cause": "timeout",
            "loot_lost": [],
            "total_lost": 0,
            "xp_retained": 0,
        }
        scene = GameOverScene(game, data)
        scene.update(2.0)
        scene.draw(surface)

    def test_draw_with_many_lost_items(self, game):
        surface = pygame.Surface((1280, 720))
        items = [
            {"name": f"Item {i}", "rarity": "common", "value": i * 10}
            for i in range(20)
        ]
        data = {
            "cause": "eliminated",
            "loot_lost": items,
            "total_lost": sum(i["value"] for i in items),
            "xp_retained": 50,
        }
        scene = GameOverScene(game, data)
        scene.update(2.0)
        scene.draw(surface)

    def test_type_speed_is_0_04(self, game, result_data):
        scene = GameOverScene(game, result_data)
        assert scene.TYPE_SPEED == 0.04


# ======================================================================
# Integration: RoundManager → Scene transition
# ======================================================================


class TestRoundToSceneIntegration:
    def test_extracted_produces_valid_scene_data(self):
        """Verify that RoundManager result_data works with ExtractionSummaryScene."""
        from src.events import EventBus
        from src.entities.base import Entity
        from src.map import Zone
        from src.round import RoundManager
        from tests.conftest import MockTileMap

        bus = EventBus()
        rm = RoundManager(bus, extraction_duration=0.1)
        zone = Zone(
            name="extract_a",
            zone_type="extraction",
            rect=pygame.Rect(200, 200, 128, 128),
        )
        spawn = Zone(
            name="spawn_a",
            zone_type="spawn",
            rect=pygame.Rect(64, 64, 128, 128),
        )
        player = Entity(x=264.0, y=264.0, health=100)
        tilemap = MockTileMap([spawn, zone])

        rm.start_round(player, tilemap)
        # Reposition player inside extraction zone after start_round
        # (start_round moves player to spawn zone)
        player.pos.x = float(zone.rect.centerx)
        player.pos.y = float(zone.rect.centery)
        rm.begin_extraction(zone)
        rm.update(0.2, player)
        rm.update(0.016, player)

        result = rm.result_data
        game = MockGame()
        scene = ExtractionSummaryScene(game, result)
        assert scene.result_data["outcome"] == "extracted"

    def test_failed_produces_valid_scene_data(self):
        """Verify that RoundManager failure data works with GameOverScene."""
        from src.events import EventBus
        from src.entities.base import Entity
        from src.map import Zone
        from src.round import RoundManager
        from tests.conftest import MockTileMap

        bus = EventBus()
        rm = RoundManager(bus, round_duration=0.1)
        spawn = Zone(
            name="spawn_a",
            zone_type="spawn",
            rect=pygame.Rect(64, 64, 128, 128),
        )
        player = Entity(x=128.0, y=128.0, health=100)
        tilemap = MockTileMap([spawn])

        rm.start_round(player, tilemap)
        rm.update(0.2, player)
        rm.update(0.016, player)

        result = rm.result_data
        game = MockGame()
        scene = GameOverScene(game, result)
        assert scene.cause == "timeout"
