"""Integration tests — GameScene HUD wiring.

These tests verify that ``GameScene._build_hud_state()`` assembles a correct
``HUDState`` snapshot from the in-round player and zone data, and that the
``update`` / ``render`` frame cycle does not raise.

A real Pygame surface is used for rendering; a ``MagicMock`` stands in for
``AudioSystem`` and ``Settings`` so the test has no external dependencies.
"""
from __future__ import annotations

import pytest
import pygame
from unittest.mock import MagicMock

from src.core.event_bus import EventBus
from src.ui.hud_state import HUDState


# ---------------------------------------------------------------------------
# Session-scoped Pygame initialisation (headless, no display window)
# ---------------------------------------------------------------------------
@pytest.fixture(scope='session', autouse=True)
def pygame_headless():
    pygame.display.init()
    pygame.font.init()
    yield
    pygame.quit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_audio():
    audio = MagicMock()
    # audio.update() is called with keyword args — MagicMock handles this
    return audio


@pytest.fixture
def mock_settings():
    return MagicMock()


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def scene(bus, mock_audio, mock_settings):
    from src.scenes.game_scene import GameScene
    return GameScene(event_bus=bus, audio=mock_audio, settings=mock_settings)


@pytest.fixture
def screen():
    return pygame.Surface((1280, 720))


# ---------------------------------------------------------------------------
# _build_hud_state — return type and field correctness
# ---------------------------------------------------------------------------
class TestBuildHUDState:
    def test_returns_hud_state_instance(self, scene):
        state = scene._build_hud_state()
        assert isinstance(state, HUDState)

    def test_hp_matches_player_health(self, scene):
        scene._player.health = 75
        state = scene._build_hud_state()
        assert state.hp == pytest.approx(75.0)

    def test_max_hp_matches_player_max_health(self, scene):
        scene._player.max_health = 150
        state = scene._build_hud_state()
        assert state.max_hp == pytest.approx(150.0)

    def test_armor_matches_player_armor(self, scene):
        scene._player.armor = 50
        state = scene._build_hud_state()
        assert state.armor == pytest.approx(50.0)

    def test_max_armor_matches_player_max_armor(self, scene):
        scene._player.max_armor = 80
        state = scene._build_hud_state()
        assert state.max_armor == pytest.approx(80.0)

    def test_zones_count_equals_scene_zone_count(self, scene):
        state = scene._build_hud_state()
        assert len(state.zones) == len(scene._zones)

    def test_zone_names_match_scene_zone_names(self, scene):
        state = scene._build_hud_state()
        state_names = {z.name for z in state.zones}
        scene_names = {z.name for z in scene._zones}
        assert state_names == scene_names

    def test_map_world_rect_is_not_none(self, scene):
        state = scene._build_hud_state()
        assert state.map_world_rect is not None

    def test_player_world_pos_is_2_tuple(self, scene):
        state = scene._build_hud_state()
        assert isinstance(state.player_world_pos, tuple)
        assert len(state.player_world_pos) == 2

    def test_player_world_pos_matches_player_rect_center(self, scene):
        # The stub player starts at rect (0, 0, 32, 48) → center (16, 24)
        state = scene._build_hud_state()
        expected = tuple(scene._player.rect.center)
        assert state.player_world_pos == expected

    def test_hp_is_float(self, scene):
        scene._player.health = 90
        state = scene._build_hud_state()
        assert isinstance(state.hp, float)

    def test_max_hp_is_float(self, scene):
        state = scene._build_hud_state()
        assert isinstance(state.max_hp, float)

    def test_returns_new_snapshot_each_call(self, scene):
        """Each call must return a fresh HUDState (not a cached singleton)."""
        s1 = scene._build_hud_state()
        s2 = scene._build_hud_state()
        assert s1 is not s2

    def test_active_buffs_is_list(self, scene):
        state = scene._build_hud_state()
        assert isinstance(state.active_buffs, list)

    def test_active_challenges_is_list(self, scene):
        state = scene._build_hud_state()
        assert isinstance(state.active_challenges, list)

    def test_consumable_slots_is_list(self, scene):
        state = scene._build_hud_state()
        assert isinstance(state.consumable_slots, list)


# ---------------------------------------------------------------------------
# _build_hud_state — map_world_rect covers all zones
# ---------------------------------------------------------------------------
class TestBuildHUDStateMapRect:
    def test_map_rect_width_covers_all_default_zones(self, scene):
        """Default three zones span 0–1280px; map rect must be at least that wide."""
        state = scene._build_hud_state()
        total_width = sum(z.rect.width for z in scene._zones)
        assert state.map_world_rect.width >= total_width

    def test_map_rect_x_starts_at_leftmost_zone(self, scene):
        state = scene._build_hud_state()
        leftmost = min(z.rect.left for z in scene._zones)
        assert state.map_world_rect.left == leftmost


# ---------------------------------------------------------------------------
# GameScene.update — per-frame tick
# ---------------------------------------------------------------------------
class TestGameSceneUpdate:
    def test_update_does_not_raise(self, scene):
        scene.update(0.016)

    def test_multiple_updates_do_not_raise(self, scene):
        for _ in range(10):
            scene.update(0.016)

    def test_update_calls_audio_system(self, scene, mock_audio):
        scene.update(0.016)
        mock_audio.update.assert_called()

    def test_first_update_fires_zone_entered_when_player_in_zone(
        self, bus, mock_audio, mock_settings
    ):
        """Player starts inside zone_alpha; the first update must emit zone_entered."""
        from src.scenes.game_scene import GameScene

        events_received: list[dict] = []
        bus.subscribe('zone_entered', lambda **kw: events_received.append(kw))
        s = GameScene(event_bus=bus, audio=mock_audio, settings=mock_settings)
        s.update(0.016)
        assert len(events_received) == 1

    def test_second_update_without_movement_does_not_re_fire_zone_entered(
        self, bus, mock_audio, mock_settings
    ):
        """Zone-entered fires only on zone *change*, not every frame."""
        from src.scenes.game_scene import GameScene

        events_received: list[dict] = []
        bus.subscribe('zone_entered', lambda **kw: events_received.append(kw))
        s = GameScene(event_bus=bus, audio=mock_audio, settings=mock_settings)
        s.update(0.016)
        s.update(0.016)
        # Still only one event — player hasn't moved to a new zone
        assert len(events_received) == 1


# ---------------------------------------------------------------------------
# GameScene.render — full draw pass (HUD included)
# ---------------------------------------------------------------------------
class TestGameSceneRender:
    def test_render_does_not_raise(self, scene, screen):
        scene.render(screen)

    def test_render_after_update_does_not_raise(self, scene, screen):
        scene.update(0.016)
        scene.render(screen)

    def test_multiple_render_calls_do_not_raise(self, scene, screen):
        for _ in range(5):
            scene.update(0.016)
            scene.render(screen)


# ---------------------------------------------------------------------------
# GameScene with home_base bonuses
# ---------------------------------------------------------------------------
class TestGameSceneHomeBaseBonuses:
    def test_home_base_extra_hp_applied_to_player(
        self, bus, mock_audio, mock_settings
    ):
        from src.scenes.game_scene import GameScene

        home_base = MagicMock()
        home_base.get_round_bonuses.return_value = {
            'extra_hp': 25,
            'extra_slots': 0,
            'loot_value_bonus': 0.0,
        }
        s = GameScene(
            event_bus=bus, audio=mock_audio,
            settings=mock_settings, home_base=home_base,
        )
        # Default health is 100; +25 → 125
        assert s._player.health == 125
        assert s._player.max_health == 125

    def test_home_base_loot_value_bonus_stored(
        self, bus, mock_audio, mock_settings
    ):
        from src.scenes.game_scene import GameScene

        home_base = MagicMock()
        home_base.get_round_bonuses.return_value = {
            'extra_hp': 0,
            'extra_slots': 0,
            'loot_value_bonus': 0.15,
        }
        s = GameScene(
            event_bus=bus, audio=mock_audio,
            settings=mock_settings, home_base=home_base,
        )
        assert s.loot_value_bonus == pytest.approx(0.15)

    def test_home_base_extra_slots_expand_inventory(
        self, bus, mock_audio, mock_settings
    ):
        from src.scenes.game_scene import GameScene

        home_base = MagicMock()
        home_base.get_round_bonuses.return_value = {
            'extra_hp': 0,
            'extra_slots': 4,
            'loot_value_bonus': 0.0,
        }
        s = GameScene(
            event_bus=bus, audio=mock_audio,
            settings=mock_settings, home_base=home_base,
        )
        # Default capacity is 24; +4 → 28
        assert s._player.inventory.capacity == 28
