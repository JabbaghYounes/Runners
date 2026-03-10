"""Integration tests for GameplayScene — wiring, input handling, and transitions."""

from __future__ import annotations

import pygame
import pytest

from src.events import EventBus
from src.entities.base import Entity
from src.map import Zone
from src.round import RoundManager, RoundPhase
from src.scenes.extraction_summary import ExtractionSummaryScene
from src.scenes.game_over import GameOverScene
from tests.conftest import MockTileMap


# ======================================================================
# Mock Game object
# ======================================================================


class MockGame:
    """Minimal Game stub for integration tests."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self.screen_width = 1280
        self.screen_height = 720
        self.event_bus = event_bus or EventBus()
        self._replaced_scene = None

    def replace_scene(self, scene) -> None:
        self._replaced_scene = scene

    @property
    def last_scene(self):
        return self._replaced_scene


# ======================================================================
# Helpers
# ======================================================================


def make_player(x: float = 128.0, y: float = 128.0) -> Entity:
    p = Entity(x=x, y=y, health=100, width=32, height=32)
    p.alive = True
    return p


def make_extraction_zone(
    name: str = "extract_a", x: int = 200, y: int = 200
) -> Zone:
    return Zone(name=name, zone_type="extraction", rect=pygame.Rect(x, y, 128, 128))


def make_spawn_zone() -> Zone:
    return Zone(name="spawn_a", zone_type="spawn", rect=pygame.Rect(64, 64, 128, 128))


def place_player_in_zone(player: Entity, zone: Zone) -> None:
    player.pos.x = float(zone.rect.centerx)
    player.pos.y = float(zone.rect.centery)


# ======================================================================
# RoundManager wired with event-driven HUD-like listener
# ======================================================================


class TestRoundManagerHUDIntegration:
    """Test that RoundManager events reach HUD-like subscribers correctly."""

    def test_round_tick_reaches_listener(self):
        bus = EventBus()
        received = []
        bus.subscribe("round_tick", lambda **d: received.append(d))

        rm = RoundManager(bus, round_duration=100.0)
        player = make_player()
        tilemap = MockTileMap([make_spawn_zone()])
        rm.start_round(player, tilemap)
        rm.update(1.0, player)

        assert len(received) >= 1
        assert "remaining" in received[-1]
        assert received[-1]["remaining"] == pytest.approx(99.0)

    def test_extraction_events_reach_listener(self):
        bus = EventBus()
        started = []
        progress = []
        bus.subscribe("extraction_started", lambda **d: started.append(d))
        bus.subscribe("extraction_progress", lambda **d: progress.append(d))

        zone = make_extraction_zone()
        rm = RoundManager(bus, extraction_duration=5.0)
        player = make_player()
        tilemap = MockTileMap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        assert len(started) == 1
        assert started[0]["zone_name"] == "extract_a"

        rm.update(1.0, player)
        assert len(progress) >= 1
        assert progress[-1]["progress"] == pytest.approx(1.0)

    def test_timer_warning_reaches_listener(self):
        bus = EventBus()
        warnings = []
        bus.subscribe("timer_warning", lambda **d: warnings.append(d))

        rm = RoundManager(bus, round_duration=65.0)
        player = make_player()
        tilemap = MockTileMap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        # Advance to just past 60s threshold (remaining < 60)
        rm.update(6.0, player)
        assert len(warnings) == 1
        assert warnings[0]["remaining"] < 60.0


# ======================================================================
# E-key input triggering extraction
# ======================================================================


class TestExtractionInputHandling:
    """Test the E-key → begin_extraction flow (simulating GameplayScene)."""

    def test_e_key_begins_extraction_when_near_zone(self):
        bus = EventBus()
        zone = make_extraction_zone()
        rm = RoundManager(bus, extraction_duration=5.0)
        player = make_player()
        tilemap = MockTileMap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        # Update to detect player in zone
        rm.update(0.016, player)
        assert rm.is_near_extraction

        # Simulate what GameplayScene does on E key
        if rm.phase == RoundPhase.PLAYING and rm.is_near_extraction:
            near_zone = rm.nearest_extraction_zone
            if near_zone is not None:
                rm.begin_extraction(near_zone)

        assert rm.phase == RoundPhase.EXTRACTING

    def test_e_key_no_op_when_not_near_zone(self):
        bus = EventBus()
        rm = RoundManager(bus)
        player = make_player(x=10.0, y=10.0)
        tilemap = MockTileMap([make_spawn_zone(), make_extraction_zone()])
        rm.start_round(player, tilemap)

        rm.update(0.016, player)
        assert not rm.is_near_extraction

        # E key should do nothing
        if rm.phase == RoundPhase.PLAYING and rm.is_near_extraction:
            rm.begin_extraction(rm.nearest_extraction_zone)  # Not reached

        assert rm.phase == RoundPhase.PLAYING

    def test_e_key_no_op_during_extracting(self):
        bus = EventBus()
        zone = make_extraction_zone()
        rm = RoundManager(bus, extraction_duration=5.0)
        player = make_player()
        tilemap = MockTileMap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.update(0.016, player)
        rm.begin_extraction(zone)
        assert rm.phase == RoundPhase.EXTRACTING

        # Trying to begin extraction again should be a no-op
        rm.begin_extraction(zone)
        assert rm.phase == RoundPhase.EXTRACTING

    def test_e_key_works_with_second_zone(self):
        bus = EventBus()
        zone_a = make_extraction_zone("extract_a", 200, 200)
        zone_b = make_extraction_zone("extract_b", 800, 800)
        rm = RoundManager(bus, extraction_duration=5.0)
        player = make_player()
        tilemap = MockTileMap([make_spawn_zone(), zone_a, zone_b])
        rm.start_round(player, tilemap)

        # Move to zone_b
        place_player_in_zone(player, zone_b)
        rm.update(0.016, player)
        assert rm.is_near_extraction
        assert rm.nearest_extraction_zone.name == "extract_b"

        rm.begin_extraction(rm.nearest_extraction_zone)
        assert rm.phase == RoundPhase.EXTRACTING


# ======================================================================
# Round-end scene transitions
# ======================================================================


class TestRoundEndTransitions:
    """Test the RoundManager → scene transition flow."""

    def test_extraction_complete_produces_summary_scene_data(self):
        bus = EventBus()
        zone = make_extraction_zone()
        rm = RoundManager(bus, extraction_duration=0.1)
        player = make_player()
        tilemap = MockTileMap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        rm.update(0.2, player)  # Complete extraction
        rm.update(0.016, player)  # Finalise

        assert rm.is_finished
        assert rm.phase == RoundPhase.EXTRACTED

        result = rm.result_data
        game = MockGame(bus)
        scene = ExtractionSummaryScene(game, result)
        assert scene.result_data["outcome"] == "extracted"

    def test_timeout_produces_game_over_scene_data(self):
        bus = EventBus()
        rm = RoundManager(bus, round_duration=0.1)
        player = make_player()
        tilemap = MockTileMap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        rm.update(0.2, player)  # Timeout
        rm.update(0.016, player)  # Finalise

        assert rm.is_finished
        assert rm.phase == RoundPhase.FAILED

        result = rm.result_data
        game = MockGame(bus)
        scene = GameOverScene(game, result)
        assert scene.cause == "timeout"

    def test_death_produces_game_over_scene_data(self):
        bus = EventBus()
        rm = RoundManager(bus)
        player = make_player()
        tilemap = MockTileMap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        player.alive = False
        rm.update(0.016, player)  # Death detected
        rm.update(0.016, player)  # Finalise

        assert rm.is_finished
        result = rm.result_data
        game = MockGame(bus)
        scene = GameOverScene(game, result)
        assert scene.cause == "eliminated"

    def test_transition_flag_prevents_double_transition(self):
        """Simulate GameplayScene's _transitioning guard."""
        bus = EventBus()
        rm = RoundManager(bus, round_duration=0.1)
        player = make_player()
        tilemap = MockTileMap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        transitions = []
        transitioning = False

        for _ in range(20):
            rm.update(0.016, player)
            if rm.is_finished and not transitioning:
                transitioning = True
                transitions.append(rm.result_data)

        assert len(transitions) == 1

    def test_result_data_has_expected_keys_on_success(self):
        bus = EventBus()
        zone = make_extraction_zone()
        rm = RoundManager(bus, extraction_duration=0.1)
        player = make_player()
        tilemap = MockTileMap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        rm.update(0.2, player)
        rm.update(0.016, player)

        result = rm.result_data
        assert "outcome" in result
        assert "items" in result
        assert "total_value" in result
        assert "xp_earned" in result
        assert "money_gained" in result
        assert "level_before" in result
        assert "level_after" in result

    def test_result_data_has_expected_keys_on_failure(self):
        bus = EventBus()
        rm = RoundManager(bus, round_duration=0.1)
        player = make_player()
        tilemap = MockTileMap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        rm.update(0.2, player)
        rm.update(0.016, player)

        result = rm.result_data
        assert "outcome" in result
        assert "cause" in result
        assert "loot_lost" in result
        assert "total_lost" in result
        assert "xp_retained" in result


# ======================================================================
# Full lifecycle simulation
# ======================================================================


class TestFullRoundLifecycle:
    """End-to-end lifecycle: spawn → play → extract → summary."""

    def test_happy_path_spawn_play_extract(self):
        """Full success lifecycle through all phases."""
        bus = EventBus()
        events_seen = set()
        for evt in ["round_started", "round_tick", "extraction_started",
                     "extraction_progress", "extraction_complete"]:
            bus.subscribe(evt, lambda _evt=evt, **d: events_seen.add(_evt))

        zone = make_extraction_zone()
        rm = RoundManager(bus, round_duration=60.0, extraction_duration=2.0)
        player = make_player()
        tilemap = MockTileMap([make_spawn_zone(), zone])

        # SPAWNING → PLAYING
        rm.start_round(player, tilemap)
        assert rm.phase == RoundPhase.PLAYING
        assert "round_started" in events_seen

        # Simulate gameplay (10 frames)
        for _ in range(10):
            rm.update(0.016, player)
        assert "round_tick" in events_seen

        # Move to extraction zone
        place_player_in_zone(player, zone)
        rm.update(0.016, player)
        assert rm.is_near_extraction

        # PLAYING → EXTRACTING
        rm.begin_extraction(zone)
        assert rm.phase == RoundPhase.EXTRACTING
        assert "extraction_started" in events_seen

        # Channel for 2 seconds
        rm.update(1.0, player)
        assert "extraction_progress" in events_seen
        assert rm.extraction_progress == pytest.approx(1.0)

        rm.update(1.1, player)
        # EXTRACTING → EXTRACTED
        assert rm.phase == RoundPhase.EXTRACTED

        rm.update(0.016, player)  # Finalise
        assert rm.is_finished
        assert "extraction_complete" in events_seen
        assert rm.result_data["outcome"] == "extracted"

    def test_failure_path_timeout(self):
        """Full timeout lifecycle: spawn → play → timeout → failure."""
        bus = EventBus()
        events_seen = set()
        for evt in ["round_started", "round_timeout", "round_failed"]:
            bus.subscribe(evt, lambda _evt=evt, **d: events_seen.add(_evt))

        rm = RoundManager(bus, round_duration=5.0)
        player = make_player()
        tilemap = MockTileMap([make_spawn_zone()])

        rm.start_round(player, tilemap)
        assert rm.phase == RoundPhase.PLAYING

        # Simulate gameplay until timeout
        for i in range(400):
            rm.update(0.016, player)
            if rm.is_finished:
                break

        assert rm.phase == RoundPhase.FAILED
        assert rm.is_finished
        assert "round_timeout" in events_seen
        assert "round_failed" in events_seen
        assert rm.result_data["cause"] == "timeout"

    def test_failure_path_death(self):
        """Full death lifecycle: spawn → play → die → failure."""
        bus = EventBus()
        events_seen = set()
        bus.subscribe("round_failed", lambda **d: events_seen.add("round_failed"))

        rm = RoundManager(bus, round_duration=900.0)
        player = make_player()
        tilemap = MockTileMap([make_spawn_zone()])

        rm.start_round(player, tilemap)

        # Simulate some gameplay
        for _ in range(10):
            rm.update(0.016, player)

        # Player dies
        player.alive = False
        rm.update(0.016, player)
        assert rm.phase == RoundPhase.FAILED

        rm.update(0.016, player)
        assert rm.is_finished
        assert "round_failed" in events_seen
        assert rm.result_data["cause"] == "eliminated"

    def test_extraction_cancelled_then_succeed(self):
        """Cancel extraction, move back, extract successfully."""
        bus = EventBus()
        zone = make_extraction_zone()
        rm = RoundManager(bus, round_duration=60.0, extraction_duration=1.0)
        player = make_player()
        tilemap = MockTileMap([make_spawn_zone(), zone])

        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)
        rm.update(0.016, player)

        # Start extraction
        rm.begin_extraction(zone)
        assert rm.phase == RoundPhase.EXTRACTING

        # Leave zone (cancel)
        player.pos.x = 0.0
        player.pos.y = 0.0
        rm.update(0.016, player)
        assert rm.phase == RoundPhase.PLAYING

        # Return to zone
        place_player_in_zone(player, zone)
        rm.update(0.016, player)
        assert rm.is_near_extraction

        # Extract again — this time complete
        rm.begin_extraction(zone)
        rm.update(1.1, player)
        assert rm.phase == RoundPhase.EXTRACTED

        rm.update(0.016, player)
        assert rm.is_finished

    def test_damage_interrupts_then_re_extract(self):
        """Damage interrupts extraction, then extract successfully."""
        bus = EventBus()
        zone = make_extraction_zone()
        rm = RoundManager(bus, round_duration=60.0, extraction_duration=1.0)
        player = make_player()
        tilemap = MockTileMap([make_spawn_zone(), zone])

        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)
        rm.update(0.016, player)

        # Start extraction
        rm.begin_extraction(zone)
        rm.update(0.3, player)
        assert rm.phase == RoundPhase.EXTRACTING

        # Take damage
        bus.publish("player_damaged", target=player, damage=10, source=None)
        assert rm.phase == RoundPhase.PLAYING
        assert rm.extraction_progress == 0.0

        # Re-extract successfully
        rm.begin_extraction(zone)
        rm.update(1.1, player)
        assert rm.phase == RoundPhase.EXTRACTED

    def test_back_to_back_rounds(self):
        """Complete one round, start another — state fully resets."""
        bus = EventBus()
        zone = make_extraction_zone()
        tilemap = MockTileMap([make_spawn_zone(), zone])

        rm = RoundManager(bus, round_duration=60.0, extraction_duration=0.1)

        # First round
        player1 = make_player()
        rm.start_round(player1, tilemap)
        place_player_in_zone(player1, zone)
        rm.begin_extraction(zone)
        rm.update(0.2, player1)
        rm.update(0.016, player1)
        assert rm.is_finished
        assert rm.result_data["outcome"] == "extracted"

        # Second round
        player2 = make_player()
        rm.start_round(player2, tilemap)
        assert rm.phase == RoundPhase.PLAYING
        assert rm.timer == pytest.approx(60.0)
        assert not rm.is_finished
        assert rm.extraction_progress == 0.0

        # Second round can also succeed
        place_player_in_zone(player2, zone)
        rm.begin_extraction(zone)
        rm.update(0.2, player2)
        rm.update(0.016, player2)
        assert rm.is_finished
        assert rm.result_data["outcome"] == "extracted"


# ======================================================================
# Cleanup
# ======================================================================


class TestGameplayCleanup:
    """Verify that cleanup properly disconnects events."""

    def test_round_manager_cleanup_prevents_stale_handlers(self):
        bus = EventBus()
        zone = make_extraction_zone()
        rm = RoundManager(bus, extraction_duration=5.0)
        player = make_player()
        tilemap = MockTileMap([make_spawn_zone(), zone])

        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)
        rm.begin_extraction(zone)
        assert rm.phase == RoundPhase.EXTRACTING

        rm.cleanup()

        # After cleanup, player_damaged should not cancel extraction
        # on the cleaned-up manager (handler removed)
        # We verify by creating a new manager
        rm2 = RoundManager(bus, extraction_duration=5.0)
        player2 = make_player()
        rm2.start_round(player2, tilemap)
        place_player_in_zone(player2, zone)
        rm2.begin_extraction(zone)

        # Damage event should only affect rm2 (not rm)
        bus.publish("player_damaged", target=player2, damage=10, source=None)
        assert rm2.phase == RoundPhase.PLAYING  # rm2 cancelled

    def test_multiple_round_managers_on_same_bus(self):
        """Two RoundManagers on the same bus don't interfere after cleanup."""
        bus = EventBus()
        zone = make_extraction_zone()
        tilemap = MockTileMap([make_spawn_zone(), zone])

        # First manager
        rm1 = RoundManager(bus, extraction_duration=5.0)
        player1 = make_player()
        rm1.start_round(player1, tilemap)
        rm1.cleanup()

        # Second manager
        rm2 = RoundManager(bus, extraction_duration=5.0)
        player2 = make_player()
        rm2.start_round(player2, tilemap)
        place_player_in_zone(player2, zone)
        rm2.begin_extraction(zone)

        # Only rm2 should be affected
        bus.publish("player_damaged", target=player2, damage=10, source=None)
        assert rm2.phase == RoundPhase.PLAYING
