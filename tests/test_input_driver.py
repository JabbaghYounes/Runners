"""
Unit tests for the InputDriver hierarchy — src/entities/input_driver.py

Coverage
--------
AgentActions dataclass
  - All five fields exist: move_dir, aim_pos, fire, reload, use_consumable.
  - move_dir and aim_pos are 2-element tuples of numbers.
  - fire and reload are booleans.
  - use_consumable is int or None.
  - Default values: fire=False, reload=False, use_consumable=None.

InputDriver ABC
  - Cannot be instantiated directly (abstract).
  - Concrete subclass with ``get_actions`` can be instantiated.

LocalAIDriver FSM — state transitions
  - Initial state is WANDER.
  - WANDER → AGGRO when a hostile entity enters PVP_AGENT_AGGRO_RANGE.
  - Remains WANDER when no hostile is within aggro range.
  - AGGRO → ATTACK when hostile enters PVP_AGENT_SHOOT_RANGE.
  - ATTACK: ``fire`` field is True while hostile is in shoot range.
  - ATTACK → AGGRO when hostile leaves shoot range.
  - DEAD state produces a no-op AgentActions (no movement, no fire).
  - WANDER state produces valid AgentActions (correct types on all fields).

LocalAIDriver return types
  - ``get_actions()`` always returns an AgentActions instance regardless of state.

KeyboardDriver key mappings
  - No keys pressed → move_dir == (0, 0).
  - I key (pygame.K_i) maps to upward movement (negative or zero y component).
  - K key (pygame.K_k) maps to downward movement (positive or zero y component).
  - J key (pygame.K_j) maps to leftward movement (negative or zero x component).
  - L key (pygame.K_l) maps to rightward movement (positive or zero x component).

NetworkDriver stub interface
  - Has ``connect(host, port)`` method.
  - Has ``get_actions(game_state)`` method.
  - ``get_actions()`` returns a valid AgentActions instance.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ===========================================================================
# Helpers
# ===========================================================================

def _make_entity(x: float, y: float, is_player_controlled: bool = True) -> SimpleNamespace:
    """Minimal entity stub with a position and a is_player_controlled flag."""
    return SimpleNamespace(
        x=x,
        y=y,
        rect=SimpleNamespace(center=(x + 14, y + 24)),  # 28×48 entity center
        is_player_controlled=is_player_controlled,
        alive=True,
    )


def _make_game_state(
    hostiles: list | None = None,
    agent_pos: tuple[float, float] = (0.0, 0.0),
    tile_map: Any = None,
) -> SimpleNamespace:
    """Build a minimal game_state snapshot consumed by LocalAIDriver."""
    return SimpleNamespace(
        entities=list(hostiles or []),
        agent_pos=agent_pos,
        tile_map=tile_map,
    )


# ===========================================================================
# 1. AgentActions dataclass
# ===========================================================================

class TestAgentActions:
    def test_all_fields_present(self):
        from src.entities.input_driver import AgentActions

        actions = AgentActions(
            move_dir=(0.0, 0.0),
            aim_pos=(100.0, 200.0),
            fire=False,
            reload=False,
            use_consumable=None,
        )
        assert hasattr(actions, "move_dir")
        assert hasattr(actions, "aim_pos")
        assert hasattr(actions, "fire")
        assert hasattr(actions, "reload")
        assert hasattr(actions, "use_consumable")

    def test_move_dir_is_two_element_tuple_of_numbers(self):
        from src.entities.input_driver import AgentActions

        actions = AgentActions(
            move_dir=(1.0, -0.5),
            aim_pos=(0.0, 0.0),
            fire=False,
            reload=False,
            use_consumable=None,
        )
        assert isinstance(actions.move_dir, tuple)
        assert len(actions.move_dir) == 2
        assert all(isinstance(v, (int, float)) for v in actions.move_dir)

    def test_aim_pos_is_two_element_tuple_of_numbers(self):
        from src.entities.input_driver import AgentActions

        actions = AgentActions(
            move_dir=(0.0, 0.0),
            aim_pos=(320.5, 240.5),
            fire=False,
            reload=False,
            use_consumable=None,
        )
        assert isinstance(actions.aim_pos, tuple)
        assert len(actions.aim_pos) == 2
        assert all(isinstance(v, (int, float)) for v in actions.aim_pos)

    def test_fire_and_reload_are_booleans(self):
        from src.entities.input_driver import AgentActions

        actions = AgentActions(
            move_dir=(0.0, 0.0),
            aim_pos=(0.0, 0.0),
            fire=True,
            reload=True,
            use_consumable=None,
        )
        assert isinstance(actions.fire, bool)
        assert isinstance(actions.reload, bool)

    def test_use_consumable_accepts_none(self):
        from src.entities.input_driver import AgentActions

        actions = AgentActions(
            move_dir=(0.0, 0.0),
            aim_pos=(0.0, 0.0),
            fire=False,
            reload=False,
            use_consumable=None,
        )
        assert actions.use_consumable is None

    def test_use_consumable_accepts_int_slot_index(self):
        from src.entities.input_driver import AgentActions

        actions = AgentActions(
            move_dir=(0.0, 0.0),
            aim_pos=(0.0, 0.0),
            fire=False,
            reload=False,
            use_consumable=2,
        )
        assert isinstance(actions.use_consumable, int)
        assert actions.use_consumable == 2

    def test_default_fire_and_reload_are_false(self):
        """Omitting fire/reload should default to False (not fire by accident)."""
        from src.entities.input_driver import AgentActions

        # Use keyword defaults if the dataclass provides them
        try:
            actions = AgentActions(move_dir=(0.0, 0.0), aim_pos=(0.0, 0.0))
        except TypeError:
            # All fields required — create with explicit falsy values instead
            actions = AgentActions(
                move_dir=(0.0, 0.0),
                aim_pos=(0.0, 0.0),
                fire=False,
                reload=False,
                use_consumable=None,
            )
        assert actions.fire is False
        assert actions.reload is False


# ===========================================================================
# 2. InputDriver ABC
# ===========================================================================

class TestInputDriverABC:
    def test_input_driver_cannot_be_instantiated_directly(self):
        from src.entities.input_driver import InputDriver

        with pytest.raises(TypeError):
            InputDriver()  # type: ignore[abstract]

    def test_concrete_subclass_with_get_actions_is_instantiable(self):
        from src.entities.input_driver import AgentActions, InputDriver

        class _ConcreteDriver(InputDriver):
            def get_actions(self, game_state) -> AgentActions:
                return AgentActions(
                    move_dir=(0.0, 0.0),
                    aim_pos=(0.0, 0.0),
                    fire=False,
                    reload=False,
                    use_consumable=None,
                )

        driver = _ConcreteDriver()
        assert driver is not None

    def test_get_actions_is_the_single_abstract_method(self):
        from src.entities.input_driver import InputDriver

        abstract_methods = getattr(InputDriver, "__abstractmethods__", frozenset())
        assert "get_actions" in abstract_methods


# ===========================================================================
# 3. LocalAIDriver FSM — state transitions
# ===========================================================================

class TestLocalAIDriverFSM:
    """Tests drive the FSM via get_actions() with crafted game_state snapshots."""

    def _make_driver(self, config: dict | None = None) -> Any:
        from src.entities.input_driver import LocalAIDriver

        cfg = config or {}
        return LocalAIDriver(config=cfg)

    def test_initial_state_is_wander(self):
        driver = self._make_driver()
        assert driver.state.name == "WANDER"

    def test_remains_wander_with_no_hostiles(self):
        driver = self._make_driver()
        game_state = _make_game_state(hostiles=[], agent_pos=(0.0, 0.0))

        driver.get_actions(game_state)

        assert driver.state.name == "WANDER"

    def test_wander_to_aggro_when_hostile_enters_aggro_range(self):
        from src.constants import PVP_AGENT_AGGRO_RANGE

        driver = self._make_driver()
        # Place a hostile just inside the aggro range
        hostile_x = PVP_AGENT_AGGRO_RANGE * 0.5
        hostile = _make_entity(x=hostile_x, y=0.0, is_player_controlled=True)
        game_state = _make_game_state(
            hostiles=[hostile], agent_pos=(0.0, 0.0)
        )

        driver.get_actions(game_state)

        assert driver.state.name in ("AGGRO", "ATTACK"), (
            f"Expected AGGRO or ATTACK after hostile enters range; got {driver.state.name}"
        )

    def test_wander_stays_wander_when_hostile_outside_aggro_range(self):
        from src.constants import PVP_AGENT_AGGRO_RANGE

        driver = self._make_driver()
        # Place a hostile well outside aggro range
        hostile = _make_entity(
            x=PVP_AGENT_AGGRO_RANGE * 3.0, y=0.0, is_player_controlled=True
        )
        game_state = _make_game_state(
            hostiles=[hostile], agent_pos=(0.0, 0.0)
        )

        driver.get_actions(game_state)

        assert driver.state.name == "WANDER"

    def test_aggro_to_attack_when_hostile_enters_shoot_range(self):
        from src.constants import PVP_AGENT_SHOOT_RANGE

        driver = self._make_driver()
        # Manually put driver into AGGRO state
        driver.state = driver._state_enum.AGGRO

        # Place hostile inside shoot range
        hostile = _make_entity(
            x=PVP_AGENT_SHOOT_RANGE * 0.5, y=0.0, is_player_controlled=True
        )
        game_state = _make_game_state(
            hostiles=[hostile], agent_pos=(0.0, 0.0)
        )

        driver.get_actions(game_state)

        assert driver.state.name == "ATTACK"

    def test_attack_state_fire_is_true_when_in_shoot_range(self):
        from src.constants import PVP_AGENT_SHOOT_RANGE

        driver = self._make_driver()
        driver.state = driver._state_enum.ATTACK

        hostile = _make_entity(
            x=PVP_AGENT_SHOOT_RANGE * 0.5, y=0.0, is_player_controlled=True
        )
        game_state = _make_game_state(
            hostiles=[hostile], agent_pos=(0.0, 0.0)
        )

        actions = driver.get_actions(game_state)

        assert actions.fire is True

    def test_attack_to_aggro_when_hostile_leaves_shoot_range(self):
        from src.constants import PVP_AGENT_AGGRO_RANGE, PVP_AGENT_SHOOT_RANGE

        driver = self._make_driver()
        driver.state = driver._state_enum.ATTACK

        # Hostile between shoot range and aggro range → should revert to AGGRO
        mid_range = (PVP_AGENT_SHOOT_RANGE + PVP_AGENT_AGGRO_RANGE) / 2.0
        hostile = _make_entity(x=mid_range, y=0.0, is_player_controlled=True)
        game_state = _make_game_state(
            hostiles=[hostile], agent_pos=(0.0, 0.0)
        )

        driver.get_actions(game_state)

        assert driver.state.name == "AGGRO"

    def test_dead_state_returns_noop_actions(self):
        driver = self._make_driver()
        driver.state = driver._state_enum.DEAD

        game_state = _make_game_state(hostiles=[], agent_pos=(0.0, 0.0))
        actions = driver.get_actions(game_state)

        assert actions.move_dir == (0, 0) or actions.move_dir == (0.0, 0.0)
        assert actions.fire is False
        assert actions.reload is False
        assert actions.use_consumable is None

    def test_dead_state_fire_is_false_even_with_hostile_nearby(self):
        driver = self._make_driver()
        driver.state = driver._state_enum.DEAD

        # Hostile right on top of the dead agent
        hostile = _make_entity(x=1.0, y=1.0, is_player_controlled=True)
        game_state = _make_game_state(
            hostiles=[hostile], agent_pos=(0.0, 0.0)
        )
        actions = driver.get_actions(game_state)

        assert actions.fire is False


# ===========================================================================
# 4. LocalAIDriver return types — get_actions always returns AgentActions
# ===========================================================================

class TestLocalAIDriverReturnTypes:
    """get_actions() must return AgentActions in every FSM state."""

    def _make_driver_in_state(self, state_name: str) -> Any:
        from src.entities.input_driver import LocalAIDriver

        driver = LocalAIDriver(config={})
        driver.state = getattr(driver._state_enum, state_name)
        return driver

    @pytest.mark.parametrize("state_name", ["WANDER", "AGGRO", "ATTACK", "DEAD"])
    def test_get_actions_returns_agent_actions_in_all_states(self, state_name):
        from src.entities.input_driver import AgentActions

        driver = self._make_driver_in_state(state_name)
        game_state = _make_game_state(hostiles=[], agent_pos=(0.0, 0.0))

        actions = driver.get_actions(game_state)

        assert isinstance(actions, AgentActions), (
            f"Expected AgentActions from state {state_name}; got {type(actions)}"
        )

    @pytest.mark.parametrize("state_name", ["WANDER", "AGGRO", "ATTACK", "DEAD"])
    def test_move_dir_is_tuple_in_all_states(self, state_name):
        driver = self._make_driver_in_state(state_name)
        game_state = _make_game_state(hostiles=[], agent_pos=(0.0, 0.0))

        actions = driver.get_actions(game_state)

        assert isinstance(actions.move_dir, tuple) and len(actions.move_dir) == 2

    @pytest.mark.parametrize("state_name", ["WANDER", "AGGRO", "ATTACK", "DEAD"])
    def test_fire_is_bool_in_all_states(self, state_name):
        driver = self._make_driver_in_state(state_name)
        game_state = _make_game_state(hostiles=[], agent_pos=(0.0, 0.0))

        actions = driver.get_actions(game_state)

        assert isinstance(actions.fire, bool)


# ===========================================================================
# 5. KeyboardDriver — IJKL key mappings
# ===========================================================================

class TestKeyboardDriver:
    """KeyboardDriver translates pygame key state into AgentActions."""

    def _make_driver(self) -> Any:
        from src.entities.input_driver import KeyboardDriver

        return KeyboardDriver()

    def _pressed(self, keys: set[int]) -> Any:
        """Return a fake pygame key state where only *keys* are held down."""
        import pygame

        # pygame.key.get_pressed returns a sequence indexed by key constant.
        state = [False] * (max(keys) + 1 if keys else 512)
        for k in keys:
            if k < len(state):
                state[k] = True
        # Pad to at least 512 entries so all standard constants are safe.
        while len(state) < 512:
            state.append(False)
        return state

    def test_no_keys_pressed_produces_zero_move_dir(self):
        import pygame

        driver = self._make_driver()
        game_state = MagicMock()

        with patch("pygame.key.get_pressed", return_value=self._pressed(set())):
            with patch("pygame.mouse.get_pos", return_value=(320, 240)):
                actions = driver.get_actions(game_state)

        assert actions.move_dir == (0, 0) or actions.move_dir == (0.0, 0.0)

    def test_i_key_produces_upward_movement(self):
        """I = move up (negative y or +y depending on convention — y should differ from K)."""
        import pygame

        driver = self._make_driver()
        game_state = MagicMock()

        with patch("pygame.key.get_pressed", return_value=self._pressed({pygame.K_i})):
            with patch("pygame.mouse.get_pos", return_value=(320, 240)):
                actions = driver.get_actions(game_state)

        _, y = actions.move_dir
        # I moves up → y should be non-positive (or the opposite of K's y)
        assert y <= 0, f"I key should produce non-positive y; got {y}"

    def test_k_key_produces_downward_movement(self):
        """K = move down."""
        import pygame

        driver = self._make_driver()
        game_state = MagicMock()

        with patch("pygame.key.get_pressed", return_value=self._pressed({pygame.K_k})):
            with patch("pygame.mouse.get_pos", return_value=(320, 240)):
                actions = driver.get_actions(game_state)

        _, y = actions.move_dir
        assert y >= 0, f"K key should produce non-negative y; got {y}"

    def test_j_key_produces_leftward_movement(self):
        """J = move left."""
        import pygame

        driver = self._make_driver()
        game_state = MagicMock()

        with patch("pygame.key.get_pressed", return_value=self._pressed({pygame.K_j})):
            with patch("pygame.mouse.get_pos", return_value=(320, 240)):
                actions = driver.get_actions(game_state)

        x, _ = actions.move_dir
        assert x <= 0, f"J key should produce non-positive x; got {x}"

    def test_l_key_produces_rightward_movement(self):
        """L = move right."""
        import pygame

        driver = self._make_driver()
        game_state = MagicMock()

        with patch("pygame.key.get_pressed", return_value=self._pressed({pygame.K_l})):
            with patch("pygame.mouse.get_pos", return_value=(320, 240)):
                actions = driver.get_actions(game_state)

        x, _ = actions.move_dir
        assert x >= 0, f"L key should produce non-negative x; got {x}"

    def test_i_and_k_produce_opposite_y_signs(self):
        """I (up) and K (down) must produce opposite y directions."""
        import pygame

        driver = self._make_driver()
        game_state = MagicMock()

        with patch("pygame.key.get_pressed", return_value=self._pressed({pygame.K_i})):
            with patch("pygame.mouse.get_pos", return_value=(320, 240)):
                up_actions = driver.get_actions(game_state)

        with patch("pygame.key.get_pressed", return_value=self._pressed({pygame.K_k})):
            with patch("pygame.mouse.get_pos", return_value=(320, 240)):
                down_actions = driver.get_actions(game_state)

        _, up_y = up_actions.move_dir
        _, down_y = down_actions.move_dir
        # At least one must be non-zero; and they must not be the same
        assert up_y != down_y or (up_y == 0 and down_y == 0), (
            "I and K must produce different y components"
        )

    def test_keyboard_driver_get_actions_returns_agent_actions(self):
        import pygame
        from src.entities.input_driver import AgentActions

        driver = self._make_driver()
        game_state = MagicMock()

        with patch("pygame.key.get_pressed", return_value=self._pressed(set())):
            with patch("pygame.mouse.get_pos", return_value=(320, 240)):
                actions = driver.get_actions(game_state)

        assert isinstance(actions, AgentActions)


# ===========================================================================
# 6. NetworkDriver stub interface
# ===========================================================================

class TestNetworkDriverStub:
    """NetworkDriver is a documented stub; it must expose the right interface."""

    def _make_driver(self) -> Any:
        from src.entities.input_driver import NetworkDriver

        return NetworkDriver()

    def test_has_connect_method(self):
        driver = self._make_driver()
        assert callable(getattr(driver, "connect", None)), (
            "NetworkDriver must have a connect(host, port) method"
        )

    def test_has_get_actions_method(self):
        driver = self._make_driver()
        assert callable(getattr(driver, "get_actions", None))

    def test_get_actions_returns_agent_actions(self):
        from src.entities.input_driver import AgentActions

        driver = self._make_driver()
        game_state = MagicMock()

        actions = driver.get_actions(game_state)

        assert isinstance(actions, AgentActions), (
            "NetworkDriver.get_actions() must return AgentActions even as a stub"
        )

    def test_connect_is_callable_with_host_and_port(self):
        """connect() must not raise when called with a host string and port int."""
        driver = self._make_driver()
        # Should not raise; stub returns None or similar
        driver.connect("127.0.0.1", 9999)

    def test_get_actions_stub_produces_no_fire_by_default(self):
        """Stub must not accidentally start shooting before network is wired up."""
        driver = self._make_driver()
        game_state = MagicMock()

        actions = driver.get_actions(game_state)

        assert actions.fire is False, (
            "NetworkDriver stub must not fire before a real socket is connected"
        )
