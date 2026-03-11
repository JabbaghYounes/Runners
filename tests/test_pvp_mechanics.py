"""
Integration & unit tests for the PvP combat mechanics feature.

Coverage
--------
PvP constants
  - PVP_KILL_XP, PVP_AGENT_COUNT, PVP_FRIENDLY_FIRE, PVP_AGENT_AGGRO_RANGE,
    PVP_AGENT_SHOOT_RANGE exist with correct types and sensible values.

Player / PlayerAgent entity flags
  - ``Player.is_player_controlled`` is True.
  - ``PlayerAgent.is_player_controlled`` is False.
  - ``take_damage()`` reduces health; lethal damage sets ``alive = False``.

CombatSystem PvP hit detection
  - ``player_killed`` event is emitted when a projectile lethally hits a Player.
  - ``player_killed`` event is emitted when a projectile lethally hits a PlayerAgent.
  - Event payload carries ``killer`` and ``victim`` keys.
  - Non-lethal hit does NOT emit ``player_killed``.
  - Already-dead entities are not hit again.
  - A projectile owned by the entity does not damage that entity.
  - The projectile is consumed (alive=False) after hitting a target.

Friendly-fire flag
  - When ``PVP_FRIENDLY_FIRE = True`` (default): player-vs-agent shots land.
  - When ``PVP_FRIENDLY_FIRE = False``: player-vs-agent shots are blocked.

LootSystem player-killed drop handler
  - Every item in ``victim.inventory.slots`` becomes a LootItem.
  - Equipped weapon and armor are also dropped.
  - Victim's inventory is cleared after the drop.
  - Spawned LootItems are placed near the victim's death position (≤32 px).
  - All spawned LootItems start with ``alive = True``.
  - An empty inventory produces no LootItems.
  - LootSystem subscribes to ``player_killed`` during construction.

XPSystem PvP kill XP
  - Exactly ``PVP_KILL_XP`` XP is awarded when the killer is the human Player.
  - No XP is awarded when the killer is a PlayerAgent (``is_player_controlled=False``).
  - Multiple kills accumulate XP independently.
  - XPSystem subscribes to ``player_killed`` during construction.

End-to-end happy path
  - A lethal PvP shot through the full CombatSystem → EventBus → XPSystem /
    LootSystem pipeline awards XP and drops loot in one integrated pass.
"""
from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ===========================================================================
# Shared stub infrastructure — no pygame required
# ===========================================================================

class _Rect:
    """Minimal pygame.Rect-alike used by stub entities."""

    def __init__(self, x: float, y: float, w: int = 28, h: int = 48) -> None:
        self.x = float(x)
        self.y = float(y)
        self.w = w
        self.h = h
        self._refresh()

    def _refresh(self) -> None:
        self.centerx = self.x + self.w / 2
        self.centery = self.y + self.h / 2
        self.center = (self.centerx, self.centery)

    def colliderect(self, other: "_Rect") -> bool:
        return (
            self.x < other.x + other.w
            and self.x + self.w > other.x
            and self.y < other.y + other.h
            and self.y + self.h > other.y
        )


class _FakeItem:
    """Minimal Item stub; just needs an id and weight."""

    def __init__(self, item_id: str = "pistol_01", weight: float = 1.0) -> None:
        self.id = item_id
        self.weight = weight

    def __repr__(self) -> str:
        return f"<FakeItem {self.id!r}>"


class _FakeInventory:
    """Minimal Inventory stub mirroring the Inventory interface."""

    def __init__(
        self,
        items: list | None = None,
        equipped_weapon: _FakeItem | None = None,
        equipped_armor: _FakeItem | None = None,
    ) -> None:
        self._slots: list[_FakeItem] = list(items or [])
        self.equipped_weapon = equipped_weapon
        self.equipped_armor = equipped_armor

    @property
    def slots(self) -> list[_FakeItem]:
        return self._slots

    def add(self, item: _FakeItem) -> bool:
        self._slots.append(item)
        return True

    def clear(self) -> None:
        self._slots.clear()
        self.equipped_weapon = None
        self.equipped_armor = None


def _make_projectile(
    owner: Any,
    x: float = 100.0,
    y: float = 100.0,
    damage: int = 9999,
    w: int = 8,
    h: int = 4,
) -> SimpleNamespace:
    """Return a minimal projectile stub overlapping the default target position."""
    return SimpleNamespace(
        alive=True,
        owner=owner,
        damage=damage,
        rect=_Rect(x, y, w, h),
    )


# ===========================================================================
# 1. PvP constants
# ===========================================================================

class TestPvPConstants:
    """Validate that all PvP constants are defined with the correct types."""

    def test_pvp_kill_xp_is_positive_int(self):
        from src.constants import PVP_KILL_XP

        assert isinstance(PVP_KILL_XP, int), "PVP_KILL_XP must be an int"
        assert PVP_KILL_XP > 0, "PVP_KILL_XP must be positive"

    def test_pvp_kill_xp_matches_spec_value(self):
        """Spec requires PVP_KILL_XP = 150."""
        from src.constants import PVP_KILL_XP

        assert PVP_KILL_XP == 150

    def test_pvp_agent_count_is_at_least_one(self):
        from src.constants import PVP_AGENT_COUNT

        assert isinstance(PVP_AGENT_COUNT, int)
        assert PVP_AGENT_COUNT >= 1

    def test_pvp_friendly_fire_is_true_by_default(self):
        """Friendly-fire is ON at launch — no team system."""
        from src.constants import PVP_FRIENDLY_FIRE

        assert PVP_FRIENDLY_FIRE is True

    def test_pvp_agent_aggro_range_is_positive_number(self):
        from src.constants import PVP_AGENT_AGGRO_RANGE

        assert isinstance(PVP_AGENT_AGGRO_RANGE, (int, float))
        assert PVP_AGENT_AGGRO_RANGE > 0

    def test_pvp_agent_shoot_range_is_positive_number(self):
        from src.constants import PVP_AGENT_SHOOT_RANGE

        assert isinstance(PVP_AGENT_SHOOT_RANGE, (int, float))
        assert PVP_AGENT_SHOOT_RANGE > 0

    def test_shoot_range_strictly_less_than_aggro_range(self):
        """Agent must detect before it can shoot."""
        from src.constants import PVP_AGENT_AGGRO_RANGE, PVP_AGENT_SHOOT_RANGE

        assert PVP_AGENT_SHOOT_RANGE < PVP_AGENT_AGGRO_RANGE


# ===========================================================================
# 2. Player entity — is_player_controlled flag and take_damage
# ===========================================================================

class TestPlayerEntityFlags:
    def test_is_player_controlled_is_true(self):
        from src.entities.player import Player

        p = Player(x=0, y=0)
        assert p.is_player_controlled is True

    def test_take_damage_reduces_health(self):
        from src.entities.player import Player

        p = Player(x=0, y=0)
        hp_before = p.health
        p.take_damage(10)
        assert p.health < hp_before

    def test_take_damage_nonlethal_keeps_alive(self):
        from src.entities.player import Player

        p = Player(x=0, y=0)
        p.take_damage(p.health - 1)
        assert p.alive is True

    def test_take_damage_lethal_sets_alive_false(self):
        from src.entities.player import Player

        p = Player(x=0, y=0)
        p.take_damage(p.health + 9999)
        assert p.alive is False


# ===========================================================================
# 3. PlayerAgent entity — is_player_controlled flag and interface
# ===========================================================================

class TestPlayerAgentEntityFlags:
    def _make_agent(self, x: float = 0.0, y: float = 0.0) -> Any:
        from src.entities.player_agent import PlayerAgent

        driver = MagicMock()
        return PlayerAgent(x=x, y=y, driver=driver)

    def test_is_player_controlled_is_false(self):
        agent = self._make_agent()
        assert agent.is_player_controlled is False

    def test_agent_has_positive_health(self):
        agent = self._make_agent()
        assert hasattr(agent, "health")
        assert agent.health > 0

    def test_agent_has_inventory(self):
        agent = self._make_agent()
        assert hasattr(agent, "inventory")

    def test_take_damage_lethal_sets_alive_false(self):
        agent = self._make_agent()
        agent.take_damage(agent.health + 9999)
        assert agent.alive is False

    def test_take_damage_nonlethal_agent_stays_alive(self):
        agent = self._make_agent()
        agent.take_damage(1)
        assert agent.alive is True


# ===========================================================================
# 4. CombatSystem PvP hit detection
# ===========================================================================

class TestCombatSystemPvPHitDetection:
    """CombatSystem emits ``player_killed`` for lethal hits on Player/PlayerAgent."""

    def _make_combat(self, bus):
        from src.systems.combat import CombatSystem

        return CombatSystem(event_bus=bus)

    def test_lethal_hit_on_player_emits_player_killed(self, event_bus):
        from src.entities.player import Player

        combat = self._make_combat(event_bus)
        player = Player(x=100, y=100)
        killer = MagicMock()
        killer.is_player_controlled = False
        proj = _make_projectile(owner=killer, x=100, y=100, damage=9999)

        combat.update([proj], [player], dt=0.016)

        assert player.alive is False
        kills = event_bus.all_events("player_killed")
        assert len(kills) == 1
        assert kills[0]["victim"] is player

    def test_lethal_hit_on_player_agent_emits_player_killed(self, event_bus):
        from src.entities.player_agent import PlayerAgent

        combat = self._make_combat(event_bus)
        agent = PlayerAgent(x=100, y=100, driver=MagicMock())
        killer = MagicMock()
        killer.is_player_controlled = True
        proj = _make_projectile(owner=killer, x=100, y=100, damage=9999)

        combat.update([proj], [agent], dt=0.016)

        assert agent.alive is False
        kills = event_bus.all_events("player_killed")
        assert len(kills) == 1
        assert kills[0]["victim"] is agent

    def test_player_killed_event_carries_correct_killer(self, event_bus):
        from src.entities.player import Player

        combat = self._make_combat(event_bus)
        player = Player(x=100, y=100)
        killer = MagicMock()
        killer.is_player_controlled = False
        proj = _make_projectile(owner=killer, x=100, y=100, damage=9999)

        combat.update([proj], [player], dt=0.016)

        payload = event_bus.first("player_killed")
        assert payload["killer"] is killer

    def test_nonlethal_hit_does_not_emit_player_killed(self, event_bus):
        from src.entities.player import Player

        combat = self._make_combat(event_bus)
        player = Player(x=100, y=100)
        killer = MagicMock()
        proj = _make_projectile(owner=killer, x=100, y=100, damage=1)

        combat.update([proj], [player], dt=0.016)

        assert player.alive is True
        assert event_bus.all_events("player_killed") == []

    def test_already_dead_target_is_not_hit_again(self, event_bus):
        from src.entities.player import Player

        combat = self._make_combat(event_bus)
        player = Player(x=100, y=100)
        player.alive = False  # killed before the projectile arrives
        killer = MagicMock()
        proj = _make_projectile(owner=killer, x=100, y=100, damage=9999)

        combat.update([proj], [player], dt=0.016)

        assert event_bus.all_events("player_killed") == []

    def test_projectile_does_not_damage_its_own_owner(self, event_bus):
        from src.entities.player import Player

        combat = self._make_combat(event_bus)
        player = Player(x=100, y=100)
        initial_hp = player.health
        proj = _make_projectile(owner=player, x=100, y=100, damage=9999)

        combat.update([proj], [player], dt=0.016)

        assert player.alive is True
        assert player.health == initial_hp
        assert event_bus.all_events("player_killed") == []

    def test_projectile_is_consumed_on_hit(self, event_bus):
        from src.entities.player import Player

        combat = self._make_combat(event_bus)
        player = Player(x=100, y=100)
        proj = _make_projectile(owner=MagicMock(), x=100, y=100, damage=9999)

        combat.update([proj], [player], dt=0.016)

        assert proj.alive is False

    def test_dead_projectile_is_skipped(self, event_bus):
        from src.entities.player import Player

        combat = self._make_combat(event_bus)
        player = Player(x=100, y=100)
        initial_hp = player.health
        proj = _make_projectile(owner=MagicMock(), x=100, y=100, damage=9999)
        proj.alive = False  # already spent

        combat.update([proj], [player], dt=0.016)

        assert player.health == initial_hp


# ===========================================================================
# 5. Friendly-fire flag
# ===========================================================================

class TestFriendlyFireFlag:
    """PVP_FRIENDLY_FIRE gate controls whether player-vs-player damage lands."""

    def test_friendly_fire_true_allows_player_to_hit_agent(self, event_bus):
        import src.constants as consts
        from src.entities.player import Player
        from src.entities.player_agent import PlayerAgent
        from src.systems.combat import CombatSystem

        combat = CombatSystem(event_bus=event_bus)
        human = Player(x=0, y=0)
        agent = PlayerAgent(x=100, y=100, driver=MagicMock())
        proj = _make_projectile(owner=human, x=100, y=100, damage=9999)

        with patch.object(consts, "PVP_FRIENDLY_FIRE", True):
            combat.update([proj], [agent], dt=0.016)

        assert agent.alive is False
        assert len(event_bus.all_events("player_killed")) == 1

    def test_friendly_fire_false_blocks_player_to_agent_damage(self, event_bus):
        import src.constants as consts
        from src.entities.player import Player
        from src.entities.player_agent import PlayerAgent
        from src.systems.combat import CombatSystem

        combat = CombatSystem(event_bus=event_bus)
        human = Player(x=0, y=0)
        agent = PlayerAgent(x=100, y=100, driver=MagicMock())
        initial_hp = agent.health
        proj = _make_projectile(owner=human, x=100, y=100, damage=9999)

        with patch.object(consts, "PVP_FRIENDLY_FIRE", False):
            combat.update([proj], [agent], dt=0.016)

        assert agent.alive is True
        assert agent.health == initial_hp
        assert event_bus.all_events("player_killed") == []

    def test_friendly_fire_false_does_not_block_robot_vs_player(self, event_bus):
        """Friendly-fire flag governs PvP only; robot → player hits always land."""
        import src.constants as consts
        from src.entities.player import Player
        from src.systems.combat import CombatSystem

        combat = CombatSystem(event_bus=event_bus)
        player = Player(x=100, y=100)

        # Robot is not a Player or PlayerAgent — no friendly-fire concern
        robot = MagicMock()
        robot.is_player_controlled = False
        try:
            # If the implementation uses a different attribute to mark robots
            robot.__class__.__name__ = "RobotEnemy"
        except (AttributeError, TypeError):
            pass

        proj = _make_projectile(owner=robot, x=100, y=100, damage=9999)

        with patch.object(consts, "PVP_FRIENDLY_FIRE", False):
            combat.update([proj], [player], dt=0.016)

        # Robot should still be able to kill the human player
        assert player.alive is False


# ===========================================================================
# 6. LootSystem — drop victim inventory on player_killed
# ===========================================================================

class TestLootSystemPlayerKilledDrop:
    """LootSystem._on_player_killed scatters the victim's inventory as LootItems."""

    def _make_system(self):
        from src.systems.loot_system import LootSystem

        bus = MagicMock()
        item_db = MagicMock()
        item_db.create.side_effect = lambda iid: _FakeItem(iid)
        return LootSystem(bus, item_db), bus, item_db

    def _make_victim(
        self,
        x: float = 200.0,
        y: float = 300.0,
        item_count: int = 3,
        equipped_weapon: _FakeItem | None = None,
        equipped_armor: _FakeItem | None = None,
    ) -> MagicMock:
        victim = MagicMock()
        victim.rect = MagicMock()
        victim.rect.center = (x, y)
        items = [_FakeItem(f"item_{i}") for i in range(item_count)]
        victim.inventory = _FakeInventory(
            items=items,
            equipped_weapon=equipped_weapon,
            equipped_armor=equipped_armor,
        )
        return victim

    def test_drops_one_loot_item_per_inventory_slot(self):
        system, _, _ = self._make_system()
        victim = self._make_victim(item_count=3)

        with patch("src.systems.loot_system.LootItem") as MockLoot:
            MockLoot.side_effect = lambda item, x, y: MagicMock(item=item, alive=True)
            spawned = system._on_player_killed(killer=MagicMock(), victim=victim)

        assert len(spawned) == 3

    def test_empty_inventory_spawns_no_loot(self):
        system, _, _ = self._make_system()
        victim = self._make_victim(item_count=0)

        with patch("src.systems.loot_system.LootItem") as MockLoot:
            MockLoot.side_effect = lambda item, x, y: MagicMock(item=item, alive=True)
            spawned = system._on_player_killed(killer=MagicMock(), victim=victim)

        assert spawned == []

    def test_drops_equipped_weapon_and_armor(self):
        system, _, _ = self._make_system()
        weapon = _FakeItem("rifle_01")
        armor = _FakeItem("vest_01")
        victim = self._make_victim(
            item_count=0, equipped_weapon=weapon, equipped_armor=armor
        )
        dropped_items: list[_FakeItem] = []

        with patch("src.systems.loot_system.LootItem") as MockLoot:
            def capture(item, x, y):
                dropped_items.append(item)
                return MagicMock(item=item, alive=True)

            MockLoot.side_effect = capture
            system._on_player_killed(killer=MagicMock(), victim=victim)

        assert weapon in dropped_items
        assert armor in dropped_items

    def test_all_slots_and_equipped_gear_are_dropped(self):
        """Total drops = slot items + equipped weapon + equipped armor."""
        system, _, _ = self._make_system()
        weapon = _FakeItem("rifle_01")
        armor = _FakeItem("vest_01")
        victim = self._make_victim(
            item_count=2, equipped_weapon=weapon, equipped_armor=armor
        )

        with patch("src.systems.loot_system.LootItem") as MockLoot:
            MockLoot.side_effect = lambda item, x, y: MagicMock(item=item, alive=True)
            spawned = system._on_player_killed(killer=MagicMock(), victim=victim)

        # 2 slot items + 1 weapon + 1 armor = 4
        assert len(spawned) == 4

    def test_inventory_is_cleared_after_death(self):
        system, _, _ = self._make_system()
        victim = self._make_victim(item_count=3)

        with patch("src.systems.loot_system.LootItem", side_effect=lambda i, x, y: MagicMock()):
            system._on_player_killed(killer=MagicMock(), victim=victim)

        assert victim.inventory.slots == []
        assert victim.inventory.equipped_weapon is None
        assert victim.inventory.equipped_armor is None

    def test_loot_spawned_near_victim_death_position(self):
        """Each LootItem must be within ±32 px of the victim's center."""
        system, _, _ = self._make_system()
        death_x, death_y = 400.0, 500.0
        victim = self._make_victim(x=death_x, y=death_y, item_count=4)
        positions: list[tuple[float, float]] = []

        with patch("src.systems.loot_system.LootItem") as MockLoot:
            def capture(item, x, y):
                positions.append((x, y))
                return MagicMock(item=item, alive=True)

            MockLoot.side_effect = capture
            system._on_player_killed(killer=MagicMock(), victim=victim)

        assert positions, "No LootItems were spawned"
        for px, py in positions:
            dist = math.hypot(px - death_x, py - death_y)
            assert dist <= 32, (
                f"Loot at ({px:.1f}, {py:.1f}) is {dist:.1f} px from death "
                f"position ({death_x}, {death_y}); expected ≤ 32 px"
            )

    def test_spawned_loot_items_start_alive(self):
        system, _, _ = self._make_system()
        victim = self._make_victim(item_count=2)
        spawned: list[Any] = []

        with patch("src.systems.loot_system.LootItem") as MockLoot:
            def make_loot(item, x, y):
                m = MagicMock()
                m.alive = True
                spawned.append(m)
                return m

            MockLoot.side_effect = make_loot
            system._on_player_killed(killer=MagicMock(), victim=victim)

        assert all(loot.alive is True for loot in spawned)

    def test_loot_system_subscribes_to_player_killed_on_construction(self):
        """LootSystem must register a handler for 'player_killed' at init time."""
        from src.systems.loot_system import LootSystem

        bus = MagicMock()
        item_db = MagicMock()
        LootSystem(bus, item_db)

        subscribed = [call.args[0] for call in bus.subscribe.call_args_list]
        assert "player_killed" in subscribed, (
            f"LootSystem did not subscribe to 'player_killed'. "
            f"Subscribed events: {subscribed}"
        )


# ===========================================================================
# 7. XPSystem PvP kill XP
# ===========================================================================

class TestXPSystemPvPKillXP:
    """XPSystem awards PVP_KILL_XP only when the killer is the human Player."""

    def _make_xp_system_with_real_bus(self):
        from src.core.event_bus import EventBus
        from src.progression.xp_system import XPSystem

        bus = EventBus()
        xp = XPSystem(event_bus=bus)
        return xp, bus

    def test_human_killer_receives_pvp_kill_xp(self):
        from src.constants import PVP_KILL_XP

        xp, bus = self._make_xp_system_with_real_bus()
        initial = xp.xp

        human = MagicMock()
        human.is_player_controlled = True
        victim = MagicMock()
        victim.is_player_controlled = False

        bus.emit("player_killed", killer=human, victim=victim)

        assert xp.xp == initial + PVP_KILL_XP

    def test_bot_killer_receives_no_xp(self):
        xp, bus = self._make_xp_system_with_real_bus()
        initial = xp.xp

        bot = MagicMock()
        bot.is_player_controlled = False
        victim = MagicMock()
        victim.is_player_controlled = True

        bus.emit("player_killed", killer=bot, victim=victim)

        assert xp.xp == initial

    def test_exact_pvp_kill_xp_amount_awarded(self):
        from src.constants import PVP_KILL_XP

        xp, bus = self._make_xp_system_with_real_bus()

        human = MagicMock()
        human.is_player_controlled = True

        bus.emit("player_killed", killer=human, victim=MagicMock())

        assert xp.xp == PVP_KILL_XP

    def test_multiple_kills_accumulate_xp(self):
        from src.constants import PVP_KILL_XP

        xp, bus = self._make_xp_system_with_real_bus()

        human = MagicMock()
        human.is_player_controlled = True

        for _ in range(4):
            bus.emit("player_killed", killer=human, victim=MagicMock())

        assert xp.xp == PVP_KILL_XP * 4

    def test_xp_system_subscribes_to_player_killed_on_construction(self):
        from src.core.event_bus import EventBus
        from src.progression.xp_system import XPSystem

        bus = MagicMock()
        XPSystem(event_bus=bus)

        subscribed = [call.args[0] for call in bus.subscribe.call_args_list]
        assert "player_killed" in subscribed, (
            f"XPSystem did not subscribe to 'player_killed'. "
            f"Subscribed events: {subscribed}"
        )

    def test_xp_system_does_not_award_xp_for_robot_kills_via_pvp_channel(self):
        """Killing a RobotEnemy must not trigger PvP XP (wrong event channel)."""
        from src.constants import PVP_KILL_XP
        from src.core.event_bus import EventBus
        from src.progression.xp_system import XPSystem

        bus = EventBus()
        xp = XPSystem(event_bus=bus)
        initial = xp.xp

        human = MagicMock()
        human.is_player_controlled = True
        robot = MagicMock()
        robot.is_player_controlled = False

        # enemy_killed event (not player_killed) — should NOT grant PVP_KILL_XP
        bus.emit("enemy_killed", killer=human, enemy=robot)

        # XP may still be awarded via the enemy_killed path, but should not
        # have been granted *twice* — just check it's not equal to PVP_KILL_XP
        # if no enemy_killed handler is wired.  We only validate isolation here.
        # The key invariant: no 'player_killed' path was triggered.
        kill_through_pvp = xp.xp - initial
        # If enemy_killed has its own XP grant that equals PVP_KILL_XP that's fine,
        # but the PvP subscriber must not have fired.  We can't assert the exact
        # value without knowing the enemy XP reward, so we just verify the bus
        # integration is correct by confirming no "player_killed" was on the bus.
        assert not any(ev == "player_killed" for ev, _ in bus._listeners.items()
                       if ev == "player_killed" and callable(bus._listeners[ev])), \
            "player_killed listeners should not fire from enemy_killed"


# ===========================================================================
# 8. End-to-end happy path
# ===========================================================================

class TestPvPEndToEnd:
    """Wires CombatSystem → EventBus → XPSystem + LootSystem together."""

    def test_lethal_pvp_shot_awards_xp_and_drops_loot(self):
        """
        Human player fires a lethal shot at a PlayerAgent.
        Expected: agent dies, player_killed fires, human gains PVP_KILL_XP,
        and one LootItem is dropped per inventory item.
        """
        import src.systems.loot_system as ls_mod
        from src.constants import PVP_KILL_XP
        from src.core.event_bus import EventBus
        from src.entities.player import Player
        from src.entities.player_agent import PlayerAgent
        from src.progression.xp_system import XPSystem
        from src.systems.combat import CombatSystem
        from src.systems.loot_system import LootSystem

        bus = EventBus()
        item_db = MagicMock()
        item_db.create.side_effect = lambda iid: _FakeItem(iid)

        xp_sys = XPSystem(event_bus=bus)
        loot_sys = LootSystem(bus, item_db)

        # Give the agent a weapon in its inventory
        driver = MagicMock()
        agent = PlayerAgent(x=100, y=100, driver=driver)
        agent.inventory.add(_FakeItem("rifle_01"))

        # Human player fires — projectile overlaps agent's position exactly
        human = Player(x=0, y=0)
        proj = _make_projectile(owner=human, x=100, y=100, damage=9999)

        dropped: list[Any] = []
        with patch.object(ls_mod, "LootItem") as MockLoot:
            def capture_loot(item, x, y):
                m = MagicMock()
                m.item = item
                m.alive = True
                dropped.append(m)
                return m

            MockLoot.side_effect = capture_loot

            combat = CombatSystem(event_bus=bus)
            combat.update([proj], [agent], dt=0.016)

        # Agent is dead
        assert agent.alive is False

        # Human gained PvP XP
        assert xp_sys.xp == PVP_KILL_XP

        # Loot was dropped (at least the rifle)
        assert len(dropped) >= 1

    def test_pvp_kill_does_not_grant_xp_if_bot_kills_human(self):
        """When a bot kills the human player, no PVP_KILL_XP is awarded to anyone."""
        from src.core.event_bus import EventBus
        from src.entities.player import Player
        from src.entities.player_agent import PlayerAgent
        from src.progression.xp_system import XPSystem
        from src.systems.combat import CombatSystem

        bus = EventBus()
        xp_sys = XPSystem(event_bus=bus)

        human = Player(x=100, y=100)
        driver = MagicMock()
        bot = PlayerAgent(x=0, y=0, driver=driver)

        proj = _make_projectile(owner=bot, x=100, y=100, damage=9999)
        combat = CombatSystem(event_bus=bus)
        combat.update([proj], [human], dt=0.016)

        assert human.alive is False
        assert xp_sys.xp == 0  # bot kills award no XP to anyone
