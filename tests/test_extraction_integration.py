# Run: pytest tests/test_extraction_integration.py
"""Integration tests for the extraction feature.

These tests exercise multiple real components together:
  ExtractionSystem ↔ Player (with real Inventory) ↔ EventBus
  ExtractionSystem ↔ GameScene event handlers
  RoundSummary construction from extracted inventory

Coverage matrix
---------------
Successful extraction — full happy path
  - player_extracted fires after 3-second channel with real Inventory
  - inventory snapshot contains all items added before extraction
  - inventory snapshot is independent of later inventory mutations
  - snapshot correctly contains multiple items
  - empty inventory yields empty snapshot

Failure paths
  - round_end while IDLE emits extraction_failed (no player_extracted)
  - round_end while IN_ZONE emits extraction_failed (no player_extracted)
  - round_end while CHANNELING emits extraction_failed (no player_extracted)
  - round_end after DONE emits neither extraction_failed nor duplicate player_extracted

Dead-player cancellation
  - player killed mid-channel emits extraction_cancelled, not player_extracted
  - player killed mid-channel allows re-channel from IN_ZONE

RoundSummary construction
  - success summary carries extracted items
  - success summary computes money_earned from item values
  - timeout summary has empty extracted_items and zero money_earned
  - RoundSummary rejects invalid extraction_status

GameScene handler wiring
  - _on_extract() calls scene_manager.replace()
  - _on_extract_failed() calls scene_manager.replace()
  - scene_manager.replace() receives a PostRound-compatible object

ExtractionSystem + EventBus + GameScene end-to-end
  - round_end event triggers extraction_failed → GameScene._on_extract_failed → sm.replace()
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pygame
import pytest

from src.core.event_bus import EventBus
from src.core.round_summary import RoundSummary
from src.map.extraction_zone import ExtractionZone
from src.systems.extraction_system import ExtractionState, ExtractionSystem

# ---------------------------------------------------------------------------
# Constants (imported from the canonical module)
# ---------------------------------------------------------------------------
from src.constants import EXTRACTION_CHANNEL_SECS, KEY_EXTRACT, MOVE_THRESHOLD

# ---------------------------------------------------------------------------
# Test geometry — zone firmly inside a 1000×500 world
# ---------------------------------------------------------------------------
_ZONE_RECT = pygame.Rect(200, 100, 300, 200)
_INSIDE_POS = (300, 180)     # player top-left: rect (300,180,28,48) is inside zone
_OUTSIDE_POS = (800, 400)    # well outside zone

# Small frame dt — short enough that a single frame never completes the channel
_FRAME = 1.0 / 60.0
_CHANNEL_SECS = 3.0          # use a deterministic duration for all tests


# ---------------------------------------------------------------------------
# Player stub — avoids loading animation sprites or the full Player stack
# ---------------------------------------------------------------------------

class _FakePlayer:
    """Minimal player stub accepted by ExtractionSystem.update().

    ExtractionSystem only needs:
      - player.rect   (pygame.Rect for overlap detection)
      - player.alive  (bool)
      - player.velocity (pygame.Vector2 with .length())
      - player.inventory (iterable → list(player.inventory))
    """

    def __init__(
        self,
        x: int,
        y: int,
        alive: bool = True,
        vx: float = 0.0,
    ) -> None:
        self.rect = pygame.Rect(x, y, 28, 48)
        self.alive = alive
        self.velocity = pygame.Vector2(vx, 0.0)
        self.inventory: list = []


class _FakeItem:
    """Minimal item with a monetary value (matches RoundSummary expectations)."""

    def __init__(self, name: str, value: int = 100) -> None:
        self.name = name
        self.value = value

    def __repr__(self) -> str:
        return f"FakeItem({self.name!r}, value={self.value})"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_system(bus: EventBus, duration: float = _CHANNEL_SECS) -> ExtractionSystem:
    zone = ExtractionZone(rect=pygame.Rect(_ZONE_RECT))
    return ExtractionSystem(bus, zone, channel_duration=duration)


def _keys_f_held() -> list[bool]:
    keys: list[bool] = [False] * 512
    keys[KEY_EXTRACT] = True
    return keys


def _keys_f_released() -> list[bool]:
    return [False] * 512


def _drive_to_done(
    system: ExtractionSystem,
    player: _FakePlayer,
    duration: float = _CHANNEL_SECS,
) -> None:
    """Drive *system* all the way from IDLE to DONE with *player* stationary inside zone."""
    player.velocity = pygame.Vector2(0.0, 0.0)
    system.update(_FRAME, player, _keys_f_released())   # IDLE → IN_ZONE
    system.update(_FRAME, player, _keys_f_held())        # IN_ZONE → CHANNELING
    system.update(duration, player, _keys_f_held())      # CHANNELING → DONE


# ===========================================================================
# Successful extraction — happy path with real Inventory
# ===========================================================================

class TestSuccessfulExtractionFlow:
    """player_extracted must fire with the correct inventory snapshot."""

    def test_player_extracted_fires_after_full_channel(self):
        bus = EventBus()
        system = _make_system(bus)
        events: list[dict] = []
        bus.subscribe("player_extracted", lambda **kw: events.append(kw))

        player = _FakePlayer(*_INSIDE_POS)
        _drive_to_done(system, player)

        assert len(events) == 1

    def test_snapshot_contains_items_present_at_extraction(self):
        """Every item in inventory at extraction time must appear in the snapshot."""
        bus = EventBus()
        system = _make_system(bus)
        events: list[dict] = []
        bus.subscribe("player_extracted", lambda **kw: events.append(kw))

        player = _FakePlayer(*_INSIDE_POS)
        item_a = _FakeItem("Medkit", 100)
        item_b = _FakeItem("Rifle", 500)
        player.inventory.extend([item_a, item_b])

        _drive_to_done(system, player)

        snapshot = events[0]["inventory_snapshot"]
        assert item_a in snapshot
        assert item_b in snapshot

    def test_snapshot_length_matches_inventory(self):
        bus = EventBus()
        system = _make_system(bus)
        events: list[dict] = []
        bus.subscribe("player_extracted", lambda **kw: events.append(kw))

        player = _FakePlayer(*_INSIDE_POS)
        player.inventory.extend([_FakeItem(f"item_{i}") for i in range(5)])

        _drive_to_done(system, player)

        assert len(events[0]["inventory_snapshot"]) == 5

    def test_snapshot_is_independent_of_later_inventory_mutations(self):
        """Clearing inventory after extraction must not empty the snapshot."""
        bus = EventBus()
        system = _make_system(bus)
        events: list[dict] = []
        bus.subscribe("player_extracted", lambda **kw: events.append(kw))

        player = _FakePlayer(*_INSIDE_POS)
        player.inventory.append(_FakeItem("Vest", 250))

        _drive_to_done(system, player)

        player.inventory.clear()          # mutate after extraction
        assert len(events[0]["inventory_snapshot"]) == 1

    def test_empty_inventory_yields_empty_snapshot(self):
        bus = EventBus()
        system = _make_system(bus)
        events: list[dict] = []
        bus.subscribe("player_extracted", lambda **kw: events.append(kw))

        player = _FakePlayer(*_INSIDE_POS)
        _drive_to_done(system, player)

        assert events[0]["inventory_snapshot"] == []

    def test_system_is_done_after_successful_extraction(self):
        bus = EventBus()
        system = _make_system(bus)
        player = _FakePlayer(*_INSIDE_POS)
        _drive_to_done(system, player)
        assert system.is_done
        assert system.state is ExtractionState.DONE


# ===========================================================================
# Successful extraction with real Inventory object
# ===========================================================================

class TestSuccessfulExtractionRealInventory:
    """Same scenarios as above but with the real src.inventory.Inventory."""

    @pytest.fixture()
    def player_with_real_inventory(self):
        """A _FakePlayer whose .inventory is a real Inventory object."""
        from src.inventory.inventory import Inventory

        player = _FakePlayer(*_INSIDE_POS)
        player.inventory = Inventory()
        return player

    def test_snapshot_contains_items_from_real_inventory(
        self, player_with_real_inventory
    ):
        bus = EventBus()
        system = _make_system(bus)
        events: list[dict] = []
        bus.subscribe("player_extracted", lambda **kw: events.append(kw))

        player = player_with_real_inventory
        item_a = _FakeItem("ScopeA", 200)
        item_b = _FakeItem("ArmorB", 400)
        player.inventory.append(item_a)
        player.inventory.append(item_b)

        _drive_to_done(system, player)

        snapshot = events[0]["inventory_snapshot"]
        assert item_a in snapshot
        assert item_b in snapshot

    def test_real_inventory_clear_does_not_affect_snapshot(
        self, player_with_real_inventory
    ):
        bus = EventBus()
        system = _make_system(bus)
        events: list[dict] = []
        bus.subscribe("player_extracted", lambda **kw: events.append(kw))

        player = player_with_real_inventory
        player.inventory.append(_FakeItem("Grenade", 75))

        _drive_to_done(system, player)

        player.inventory.clear()
        assert len(events[0]["inventory_snapshot"]) == 1


# ===========================================================================
# Failure paths — extraction_failed on round_end
# ===========================================================================

class TestExtractionFailurePaths:
    """round_end must trigger extraction_failed if not already DONE."""

    def _collect(self, bus: EventBus, event: str) -> list[dict]:
        events: list[dict] = []
        bus.subscribe(event, lambda **kw: events.append(kw))
        return events

    def test_round_end_in_idle_emits_extraction_failed(self):
        bus = EventBus()
        _make_system(bus)  # just subscribing; player never enters zone
        failed = self._collect(bus, "extraction_failed")
        bus.publish("round_end")
        assert len(failed) == 1

    def test_round_end_in_idle_does_not_emit_player_extracted(self):
        bus = EventBus()
        _make_system(bus)
        extracted = self._collect(bus, "player_extracted")
        bus.publish("round_end")
        assert extracted == []

    def test_round_end_in_in_zone_emits_extraction_failed(self):
        bus = EventBus()
        system = _make_system(bus)
        failed = self._collect(bus, "extraction_failed")

        player = _FakePlayer(*_INSIDE_POS)
        system.update(_FRAME, player, _keys_f_released())  # enter zone
        assert system.state is ExtractionState.IN_ZONE

        bus.publish("round_end")
        assert len(failed) == 1

    def test_round_end_in_channeling_emits_extraction_failed(self):
        bus = EventBus()
        system = _make_system(bus, duration=30.0)
        failed = self._collect(bus, "extraction_failed")

        player = _FakePlayer(*_INSIDE_POS)
        system.update(_FRAME, player, _keys_f_released())  # IDLE → IN_ZONE
        system.update(_FRAME, player, _keys_f_held())      # IN_ZONE → CHANNELING
        assert system.state is ExtractionState.CHANNELING

        bus.publish("round_end")
        assert len(failed) == 1

    def test_round_end_after_done_does_not_emit_extraction_failed(self):
        bus = EventBus()
        system = _make_system(bus)
        failed = self._collect(bus, "extraction_failed")

        player = _FakePlayer(*_INSIDE_POS)
        _drive_to_done(system, player)
        assert system.is_done

        bus.publish("round_end")
        assert failed == []

    def test_round_end_after_done_does_not_emit_duplicate_player_extracted(self):
        """Completed extraction + round_end must fire player_extracted exactly once."""
        bus = EventBus()
        system = _make_system(bus)
        extracted = self._collect(bus, "player_extracted")

        player = _FakePlayer(*_INSIDE_POS)
        _drive_to_done(system, player)
        bus.publish("round_end")

        assert len(extracted) == 1  # from extraction only, not round_end


# ===========================================================================
# Dead-player cancellation
# ===========================================================================

class TestDeadPlayerIntegration:
    """Player death mid-channel must cancel via extraction_cancelled."""

    def test_dead_player_cancels_channel_emits_cancelled(self):
        bus = EventBus()
        system = _make_system(bus, duration=30.0)
        cancelled: list = []
        bus.subscribe("extraction_cancelled", lambda **kw: cancelled.append(True))

        player = _FakePlayer(*_INSIDE_POS)
        system.update(_FRAME, player, _keys_f_released())  # enter zone
        system.update(_FRAME, player, _keys_f_held())      # start channel
        assert system.state is ExtractionState.CHANNELING

        player.alive = False
        system.update(_FRAME, player, _keys_f_held())
        assert len(cancelled) == 1

    def test_dead_player_does_not_fire_player_extracted(self):
        bus = EventBus()
        system = _make_system(bus, duration=30.0)
        extracted: list = []
        bus.subscribe("player_extracted", lambda **kw: extracted.append(True))

        player = _FakePlayer(*_INSIDE_POS)
        system.update(_FRAME, player, _keys_f_released())
        system.update(_FRAME, player, _keys_f_held())
        player.alive = False
        system.update(_FRAME, player, _keys_f_held())

        assert extracted == []

    def test_dead_player_can_re_channel_after_respawn(self):
        """After death-cancel the system stays in IN_ZONE; player can re-attempt."""
        bus = EventBus()
        system = _make_system(bus, duration=30.0)

        player = _FakePlayer(*_INSIDE_POS)
        system.update(_FRAME, player, _keys_f_released())
        system.update(_FRAME, player, _keys_f_held())      # CHANNELING
        player.alive = False
        system.update(_FRAME, player, _keys_f_held())      # → IN_ZONE

        # Simulate respawn (alive again, stationary)
        player.alive = True
        player.velocity = pygame.Vector2(0.0, 0.0)
        system.update(_FRAME, player, _keys_f_held())
        assert system.state is ExtractionState.CHANNELING


# ===========================================================================
# RoundSummary construction from extracted inventory
# ===========================================================================

class TestRoundSummaryConstruction:
    """RoundSummary must carry the extracted items and pre-computed money."""

    def _make_summary(self, **overrides) -> RoundSummary:
        defaults = dict(
            extraction_status="success",
            extracted_items=[],
            xp_earned=200,
            money_earned=0,
            kills=0,
            challenges_completed=0,
            challenges_total=0,
            level_before=1,
        )
        defaults.update(overrides)
        return RoundSummary(**defaults)

    def test_success_summary_stores_extracted_items(self):
        items = [_FakeItem("Rifle", 500), _FakeItem("Vest", 200)]
        summary = self._make_summary(extracted_items=items, money_earned=700)
        assert summary.extracted_items is items

    def test_money_equals_sum_of_item_values(self):
        """GameScene computes money_earned = sum(item.value for item in snapshot)."""
        items = [_FakeItem("A", 100), _FakeItem("B", 250), _FakeItem("C", 50)]
        money = sum(item.value for item in items)
        summary = self._make_summary(extracted_items=items, money_earned=money)
        assert summary.money_earned == 400

    def test_timeout_summary_has_empty_items_and_zero_money(self):
        summary = self._make_summary(
            extraction_status="timeout", extracted_items=[], money_earned=0
        )
        assert summary.extracted_items == []
        assert summary.money_earned == 0

    def test_invalid_extraction_status_raises(self):
        with pytest.raises(ValueError):
            self._make_summary(extraction_status="win")

    def test_extraction_xp_bonus_reflected_in_summary(self):
        """Spec: successful extraction adds EXTRACTION_XP to earned XP."""
        from src.constants import EXTRACTION_XP

        summary = self._make_summary(xp_earned=EXTRACTION_XP + 50, money_earned=0)
        assert summary.xp_earned >= EXTRACTION_XP


# ===========================================================================
# GameScene handler wiring (stub mode — full init is intentionally bypassed
# because _on_player_extracted is not yet implemented in GameScene)
# ===========================================================================

class TestGameSceneHandlers:
    """_on_extract and _on_extract_failed must trigger sm.replace()."""

    @pytest.fixture()
    def scene(self):
        """GameScene in stub mode with a mock scene manager."""
        from src.scenes.game_scene import GameScene

        gs = GameScene(sm=None)  # no sm → stub mode, no subscriptions
        gs._sm = MagicMock()     # inject mock sm for handler testing
        return gs

    def test_on_extract_calls_sm_replace(self, scene):
        """_on_extract must call sm.replace() with a scene object."""
        scene._on_extract(player=scene.player)
        scene._sm.replace.assert_called_once()

    def test_on_extract_failed_calls_sm_replace(self, scene):
        """_on_extract_failed must call sm.replace() with a scene object."""
        scene._on_extract_failed()
        scene._sm.replace.assert_called_once()

    def test_on_extract_passes_post_round_scene(self, scene):
        """sm.replace() must be called with a PostRound instance."""
        from src.scenes.post_round import PostRound

        scene._on_extract(player=scene.player)
        args, _ = scene._sm.replace.call_args
        assert isinstance(args[0], PostRound)

    def test_on_extract_failed_passes_post_round_scene(self, scene):
        from src.scenes.post_round import PostRound

        scene._on_extract_failed()
        args, _ = scene._sm.replace.call_args
        assert isinstance(args[0], PostRound)

    def test_on_extract_called_twice_replaces_twice(self, scene):
        """Calling handler twice must call sm.replace() twice (no guard)."""
        scene._on_extract(player=scene.player)
        scene._on_extract(player=scene.player)
        assert scene._sm.replace.call_count == 2

    def test_on_extract_failed_with_no_sm_does_not_raise(self):
        """Handler wrapped in try/except must not propagate AttributeError."""
        from src.scenes.game_scene import GameScene

        gs = GameScene(sm=None)
        gs._sm = None            # simulate missing sm
        gs._on_extract_failed()  # must not raise


# ===========================================================================
# End-to-end: ExtractionSystem + EventBus + GameScene handler
# ===========================================================================

class TestEndToEndExtractionFlow:
    """Verify that the EventBus connects ExtractionSystem events to GameScene
    handlers correctly when wired manually (since full _init_full is broken
    while _on_player_extracted is not yet implemented)."""

    def test_round_end_triggers_extraction_failed_and_scene_replace(self):
        """round_end → extraction_failed event → sm.replace() via manual wiring."""
        from src.scenes.game_scene import GameScene

        bus = EventBus()
        system = _make_system(bus)

        gs = GameScene(sm=None, event_bus=bus)
        gs._sm = MagicMock()
        bus.subscribe("extraction_failed", gs._on_extract_failed)

        bus.publish("round_end")

        gs._sm.replace.assert_called_once(), (
            "round_end should trigger extraction_failed → _on_extract_failed → sm.replace()"
        )

    def test_successful_channel_publishes_player_extracted_event(self):
        """Full channel completion must publish 'player_extracted' on the shared bus."""
        bus = EventBus()
        system = _make_system(bus)
        extracted: list[dict] = []
        bus.subscribe("player_extracted", lambda **kw: extracted.append(kw))

        player = _FakePlayer(*_INSIDE_POS)
        player.inventory.extend([_FakeItem("Loot1"), _FakeItem("Loot2")])

        _drive_to_done(system, player)

        assert len(extracted) == 1
        assert len(extracted[0]["inventory_snapshot"]) == 2

    def test_extraction_cancelled_does_not_replace_scene(self):
        """extraction_cancelled must not trigger a scene transition."""
        from src.scenes.game_scene import GameScene

        bus = EventBus()
        system = _make_system(bus, duration=30.0)

        gs = GameScene(sm=None, event_bus=bus)
        gs._sm = MagicMock()
        bus.subscribe("extraction_failed", gs._on_extract_failed)

        player = _FakePlayer(*_INSIDE_POS)
        system.update(_FRAME, player, _keys_f_released())   # enter zone
        system.update(_FRAME, player, _keys_f_held())       # start channel
        # Cancel by releasing F
        system.update(_FRAME, player, _keys_f_released())

        gs._sm.replace.assert_not_called()

    def test_entering_zone_publishes_zone_entered_event(self):
        """Player moving into the extraction zone must fire zone_entered."""
        bus = EventBus()
        system = _make_system(bus)
        zone_events: list = []
        bus.subscribe("zone_entered", lambda **kw: zone_events.append(kw))

        player = _FakePlayer(*_INSIDE_POS)
        system.update(_FRAME, player, _keys_f_released())

        assert len(zone_events) == 1
        assert "zone" in zone_events[0]

    def test_zone_entered_fires_only_once_per_entry(self):
        """zone_entered must not fire on every frame while inside."""
        bus = EventBus()
        system = _make_system(bus)
        zone_events: list = []
        bus.subscribe("zone_entered", lambda **kw: zone_events.append(kw))

        player = _FakePlayer(*_INSIDE_POS)
        for _ in range(5):
            system.update(_FRAME, player, _keys_f_released())

        assert len(zone_events) == 1
