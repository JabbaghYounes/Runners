"""Tests for enemy animation: EnemyDatabase building AnimationController,
and RobotEnemy.update() advancing frame state from the FSM.
"""
from __future__ import annotations

import pygame
import pytest

from src.entities.animation_controller import AnimationController
from src.entities.robot_enemy import AIState, RobotEnemy
from src.data.enemy_database import EnemyDatabase

from pathlib import Path

_ENEMIES_JSON = Path(__file__).parents[1] / "data" / "enemies.json"


# ---------------------------------------------------------------------------
# Asset manager stubs
# ---------------------------------------------------------------------------

class _PlaceholderAssets:
    """Returns the 32×32 magenta placeholder AssetManager produces on a miss."""

    def load_image(self, rel_path: str, *, alpha: bool = True,
                   scale=None) -> pygame.Surface:
        surf = pygame.Surface((32, 32))
        surf.fill((255, 0, 255))
        return surf


class _RealSheetAssets:
    """Returns a fake sprite sheet of the requested dimensions."""

    def __init__(self, sheet_w: int, sheet_h: int) -> None:
        self._w = sheet_w
        self._h = sheet_h

    def load_image(self, rel_path: str, *, alpha: bool = True,
                   scale=None) -> pygame.Surface:
        surf = pygame.Surface((self._w, self._h))
        surf.fill((80, 80, 80))
        return surf


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(asset_manager=None) -> EnemyDatabase:
    return EnemyDatabase(path=_ENEMIES_JSON, asset_manager=asset_manager)


# grunt has 14 distinct frame indices: max(patrol[3], aggro[7], attack[9], dead[13]) + 1 = 14
_GRUNT_SHEET_W = 14 * 32   # 448 px
_GRUNT_SHEET_H = 48


# ---------------------------------------------------------------------------
# EnemyDatabase.create() — animation controller building
# ---------------------------------------------------------------------------

class TestEnemyDatabaseAnimationBuilding:

    def test_no_asset_manager_leaves_controller_none(self) -> None:
        db = _make_db(asset_manager=None)
        robot = db.create("grunt")
        assert robot.animation_controller is None

    def test_placeholder_sheet_builds_controller(self) -> None:
        """Even a placeholder sheet must produce a valid AnimationController."""
        db = _make_db(asset_manager=_PlaceholderAssets())
        robot = db.create("grunt")
        assert robot.animation_controller is not None
        assert isinstance(robot.animation_controller, AnimationController)

    def test_real_sheet_builds_controller(self) -> None:
        db = _make_db(
            asset_manager=_RealSheetAssets(_GRUNT_SHEET_W, _GRUNT_SHEET_H),
        )
        robot = db.create("grunt")
        assert isinstance(robot.animation_controller, AnimationController)

    def test_controller_has_all_four_states(self) -> None:
        db = _make_db(asset_manager=_PlaceholderAssets())
        ctrl = db.create("grunt").animation_controller
        for state in ("patrol", "aggro", "attack", "dead"):
            assert state in ctrl._states_config, f"Missing state: {state!r}"

    def test_every_state_has_at_least_one_surface_frame(self) -> None:
        db = _make_db(asset_manager=_PlaceholderAssets())
        ctrl = db.create("grunt").animation_controller
        for state_name, cfg in ctrl._states_config.items():
            assert cfg["frames"], f"State {state_name!r} has no frames"
            for frame in cfg["frames"]:
                assert isinstance(frame, pygame.Surface), \
                    f"State {state_name!r}: frame is not a Surface"

    def test_frame_count_matches_json_for_real_sheet(self) -> None:
        """With a wide-enough sheet, frame indices from JSON should all slice."""
        db = _make_db(
            asset_manager=_RealSheetAssets(_GRUNT_SHEET_W, _GRUNT_SHEET_H),
        )
        ctrl = db.create("grunt").animation_controller
        # grunt JSON: patrol=4, aggro=4, attack=2, dead=4 frames
        assert len(ctrl._states_config["patrol"]["frames"]) == 4
        assert len(ctrl._states_config["aggro"]["frames"]) == 4
        assert len(ctrl._states_config["attack"]["frames"]) == 2
        assert len(ctrl._states_config["dead"]["frames"]) == 4

    def test_fps_defaults_applied(self) -> None:
        """Hardcoded FPS defaults are used when enemies.json has no anim_fps."""
        db = _make_db(asset_manager=_PlaceholderAssets())
        ctrl = db.create("grunt").animation_controller
        assert ctrl._states_config["patrol"]["fps"] == 8
        assert ctrl._states_config["aggro"]["fps"] == 10
        assert ctrl._states_config["attack"]["fps"] == 12
        assert ctrl._states_config["dead"]["fps"] == 6

    def test_heavy_type_uses_its_own_frame_dimensions(self) -> None:
        """Heavy bot uses 48×64 frames; controller frames must match."""
        # heavy has up to index 15 → 16 frames × 48 wide = 768 px sheet
        db = _make_db(
            asset_manager=_RealSheetAssets(16 * 48, 64),
        )
        robot = db.create("heavy")
        ctrl = robot.animation_controller
        assert ctrl is not None
        # Check a frame has the correct width
        frame = ctrl._states_config["patrol"]["frames"][0]
        assert frame.get_width() == 48
        assert frame.get_height() == 64

    def test_out_of_range_index_clamped_not_crash(self) -> None:
        """A sheet narrower than declared frame indices should not crash."""
        # Provide a sheet only 1 frame wide; all indices will be clamped to 0
        db = _make_db(
            asset_manager=_RealSheetAssets(32, 48),  # only frame 0 exists
        )
        robot = db.create("grunt")   # grunt indices go up to 13
        ctrl = robot.animation_controller
        assert ctrl is not None
        # All frames should exist (clamped to frame 0)
        for state_cfg in ctrl._states_config.values():
            assert state_cfg["frames"]


# ---------------------------------------------------------------------------
# RobotEnemy.update() — FSM → animation state mapping
# ---------------------------------------------------------------------------

class TestRobotEnemyUpdateAnimation:

    def _robot_with_ctrl(self) -> RobotEnemy:
        db = _make_db(asset_manager=_PlaceholderAssets())
        return db.create("grunt")

    def test_patrol_state_sets_patrol_anim(self) -> None:
        robot = self._robot_with_ctrl()
        robot.state = AIState.PATROL
        robot.update(dt=0.1)
        assert robot.animation_controller._current_state == "patrol"

    def test_aggro_state_sets_aggro_anim(self) -> None:
        robot = self._robot_with_ctrl()
        robot.state = AIState.AGGRO
        robot.update(dt=0.1)
        assert robot.animation_controller._current_state == "aggro"

    def test_attack_state_sets_attack_anim(self) -> None:
        robot = self._robot_with_ctrl()
        robot.state = AIState.ATTACK
        robot.update(dt=0.1)
        assert robot.animation_controller._current_state == "attack"

    def test_dead_state_sets_dead_anim(self) -> None:
        robot = self._robot_with_ctrl()
        robot.state = AIState.DEAD
        robot.update(dt=0.1)
        assert robot.animation_controller._current_state == "dead"

    def test_update_without_controller_does_not_crash(self) -> None:
        robot = RobotEnemy(x=0.0, y=0.0)
        assert robot.animation_controller is None
        robot.update(dt=0.1)   # should not raise

    def test_update_syncs_float_from_rect(self) -> None:
        """sync_from_rect() is called: manually nudging rect.x is reflected in x."""
        robot = RobotEnemy(x=0.0, y=0.0)
        robot.rect.x = 64          # simulate PhysicsSystem moving the rect
        robot.update(dt=0.016)
        assert robot.x == pytest.approx(64.0)

    def test_facing_direction_from_vx(self) -> None:
        """vx >= 0 → facing_right=True passed to controller."""
        robot = self._robot_with_ctrl()
        robot.state = AIState.AGGRO
        robot.vx = -50.0           # moving left
        robot.update(dt=0.1)
        assert robot.animation_controller._facing_right is False

        robot.vx = 50.0
        robot.update(dt=0.1)
        assert robot.animation_controller._facing_right is True


# ---------------------------------------------------------------------------
# RobotEnemy.render() — animation controller vs fallback paths
# ---------------------------------------------------------------------------

class TestRobotEnemyRender:

    def test_render_with_controller_does_not_crash(self) -> None:
        db = _make_db(asset_manager=_PlaceholderAssets())
        robot = db.create("grunt", pos=(50.0, 50.0))
        robot.update(dt=0.016)
        screen = pygame.Surface((640, 480))
        robot.render(screen, (0, 0))

    def test_render_fallback_without_controller_does_not_crash(self) -> None:
        robot = RobotEnemy(x=50.0, y=50.0)
        assert robot.animation_controller is None
        screen = pygame.Surface((640, 480))
        robot.render(screen, (0, 0))

    def test_render_skipped_when_not_alive(self) -> None:
        robot = RobotEnemy(x=0.0, y=0.0)
        robot.alive = False
        screen = pygame.Surface((640, 480))
        bg_color = screen.get_at((0, 0))
        robot.render(screen, (0, 0))
        # Screen should be unchanged (nothing blitted)
        assert screen.get_at((0, 0)) == bg_color
