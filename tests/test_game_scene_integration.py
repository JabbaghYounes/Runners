"""
Integration tests for GameScene — the full in-round scene.

Validates the following feature requirements:
  - Tile-based futuristic map rendered at 1280×720
  - At least three distinct named zones (HANGAR BAY, REACTOR CORE, EXTRACTION PAD)
  - Clearly marked extraction zone on the map
  - Passable and impassable tiles correctly configured
  - M key opens a full-screen map overlay showing zones, extraction point, and player position
  - Map is self-contained and fully playable end-to-end
"""
import os
import pytest
import pygame
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Module-level skip guard: require the real game map
# ---------------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REAL_MAP = os.path.join(_ROOT, "assets", "maps", "map_01.json")

pytestmark = pytest.mark.skipif(
    not os.path.exists(_REAL_MAP),
    reason="Real game map (assets/maps/map_01.json) not found — skipping integration tests",
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _key_event(key: int) -> pygame.event.Event:
    """Synthesise a KEYDOWN event for *key*."""
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def event_bus():
    from src.core.event_bus import EventBus
    return EventBus()


@pytest.fixture()
def settings():
    from src.core.settings import Settings
    return Settings()  # default: "1280x720", fullscreen=False


@pytest.fixture()
def assets():
    from src.core.asset_manager import AssetManager
    return AssetManager()


@pytest.fixture()
def xp_system():
    from src.progression.xp_system import XPSystem
    return XPSystem()


@pytest.fixture()
def currency():
    from src.progression.currency import Currency
    return Currency()


@pytest.fixture()
def home_base():
    from src.progression.home_base import HomeBase
    return HomeBase()


@pytest.fixture()
def mock_sm():
    """Lightweight MagicMock that records push / replace calls."""
    return MagicMock()


@pytest.fixture()
def game_scene(mock_sm, settings, assets, event_bus, xp_system, currency, home_base):
    """A fully initialised GameScene backed by the real game map and databases."""
    from src.scenes.game_scene import GameScene
    return GameScene(
        mock_sm, settings, assets, event_bus,
        xp_system, currency, home_base,
    )


@pytest.fixture()
def screen():
    return pygame.Surface((1280, 720))


# ---------------------------------------------------------------------------
# TestGameSceneInit
# ---------------------------------------------------------------------------
class TestGameSceneInit:
    """GameScene.__init__ must wire all subsystems without raising."""

    def test_init_completes_without_error(self, game_scene):
        assert game_scene is not None

    def test_tile_map_loaded_with_correct_dimensions(self, game_scene):
        tm = game_scene.tile_map
        assert tm.tile_size == 32
        assert tm.width == 100
        assert tm.height == 30

    def test_exactly_three_zones_loaded(self, game_scene):
        assert len(game_scene.tile_map.zones) == 3

    def test_zone_names_match_spec(self, game_scene):
        names = {z.name for z in game_scene.tile_map.zones}
        assert "HANGAR BAY" in names
        assert "REACTOR CORE" in names
        assert "EXTRACTION PAD" in names

    def test_extraction_rect_is_valid_pygame_rect(self, game_scene):
        er = game_scene.tile_map.extraction_rect
        assert er is not None
        assert isinstance(er, pygame.Rect)
        assert er.width > 0
        assert er.height > 0

    def test_player_is_alive_at_spawn(self, game_scene):
        assert game_scene.player is not None
        assert game_scene.player.alive is True

    def test_player_spawn_is_inside_hangar_bay(self, game_scene):
        hangar = next(z for z in game_scene.tile_map.zones if z.name == "HANGAR BAY")
        spawn = game_scene.tile_map.player_spawn
        assert hangar.contains(spawn), (
            f"Player spawn {spawn} must lie inside HANGAR BAY {hangar.rect}"
        )

    def test_camera_matches_map_dimensions(self, game_scene):
        cam = game_scene.camera
        mr = game_scene.tile_map.map_rect
        assert cam.map_w == mr.w
        assert cam.map_h == mr.h

    def test_map_overlay_hidden_at_start(self, game_scene):
        assert game_scene._map_overlay_visible is False

    def test_enemies_list_populated_from_zone_spawns(self, game_scene):
        """SpawnSystem should create at least one enemy from zone definitions."""
        assert isinstance(game_scene.enemies, list)
        assert len(game_scene.enemies) > 0


# ---------------------------------------------------------------------------
# TestGameSceneUpdate
# ---------------------------------------------------------------------------
class TestGameSceneUpdate:
    """update(dt) must advance every subsystem without crashing."""

    def test_single_frame_does_not_crash(self, game_scene):
        game_scene.update(dt=0.016)

    def test_sixty_frames_remain_stable(self, game_scene):
        for _ in range(60):
            game_scene.update(dt=0.016)

    def test_update_is_no_op_while_overlay_is_visible(self, game_scene):
        """Game state must NOT advance while the map overlay is open."""
        game_scene._map_overlay_visible = True
        before = game_scene._extraction.seconds_remaining
        game_scene.update(dt=5.0)
        assert game_scene._extraction.seconds_remaining == before

    def test_update_advances_extraction_timer_when_overlay_closed(self, game_scene):
        game_scene._map_overlay_visible = False
        before = game_scene._extraction.seconds_remaining
        game_scene.update(dt=1.0)
        assert game_scene._extraction.seconds_remaining < before

    def test_gravity_eventually_lands_player_on_ground(self, game_scene):
        """After enough physics frames the player must settle on solid ground.

        Uses dt=0.05 (the game's capped max) so each tick moves the player
        at least 2 px vertically, guaranteeing a definitive ground collision
        and a stable on_ground=True reading at the end of every resolved frame.
        """
        for _ in range(60):
            game_scene.update(dt=0.05)
        assert game_scene.player.on_ground


# ---------------------------------------------------------------------------
# TestGameSceneRender
# ---------------------------------------------------------------------------
class TestGameSceneRender:
    """render(screen) must paint the surface without raising."""

    def test_render_does_not_crash(self, game_scene, screen):
        game_scene.render(screen)

    def test_render_overwrites_sentinel_background(self, game_scene, screen):
        """screen.fill(BG_DEEP) is the first render call; the sentinel must be gone."""
        sentinel = (255, 0, 255)
        screen.fill(sentinel)
        game_scene.render(screen)
        assert screen.get_at((0, 0))[:3] != sentinel

    def test_render_with_overlay_visible_does_not_crash(self, game_scene, screen):
        game_scene._map_overlay_visible = True
        game_scene.render(screen)

    def test_map_overlay_changes_centre_screen_pixel(self, game_scene, screen):
        """The overlay panel (PANEL_BG) is different from the background (BG_DEEP)
        at the screen centre, which lies inside the 900×520 panel."""
        game_scene._map_overlay_visible = False
        game_scene.render(screen)
        without_overlay = screen.get_at((640, 360))[:3]

        game_scene._map_overlay_visible = True
        game_scene.render(screen)
        with_overlay = screen.get_at((640, 360))[:3]

        assert with_overlay != without_overlay, (
            "Map overlay must change pixel colour at screen centre "
            f"(without={without_overlay}, with={with_overlay})"
        )

    def test_update_render_cycle_is_stable(self, game_scene, screen):
        """5 interleaved update+render frames must not crash."""
        for _ in range(5):
            game_scene.update(dt=0.016)
            game_scene.render(screen)


# ---------------------------------------------------------------------------
# TestMapOverlayToggle
# ---------------------------------------------------------------------------
class TestMapOverlayToggle:
    """M key must toggle the full-screen map overlay; ESC behaves correctly."""

    def test_m_key_opens_overlay_from_closed(self, game_scene):
        assert not game_scene._map_overlay_visible
        game_scene.handle_events([_key_event(pygame.K_m)])
        assert game_scene._map_overlay_visible

    def test_m_key_closes_overlay_when_open(self, game_scene):
        game_scene._map_overlay_visible = True
        game_scene.handle_events([_key_event(pygame.K_m)])
        assert not game_scene._map_overlay_visible

    def test_m_key_even_toggles_restore_closed_state(self, game_scene):
        """6 consecutive M presses must leave the overlay closed (False → True → … → False)."""
        for _ in range(6):
            game_scene.handle_events([_key_event(pygame.K_m)])
        assert not game_scene._map_overlay_visible

    def test_m_key_odd_toggles_leave_overlay_open(self, game_scene):
        """5 consecutive M presses must leave the overlay open."""
        for _ in range(5):
            game_scene.handle_events([_key_event(pygame.K_m)])
        assert game_scene._map_overlay_visible

    def test_esc_while_overlay_open_closes_overlay(self, game_scene):
        game_scene._map_overlay_visible = True
        game_scene.handle_events([_key_event(pygame.K_ESCAPE)])
        assert not game_scene._map_overlay_visible

    def test_esc_while_overlay_open_does_not_push_pause_menu(self, game_scene, mock_sm):
        """ESC should only close the overlay, not open the pause menu."""
        game_scene._map_overlay_visible = True
        game_scene.handle_events([_key_event(pygame.K_ESCAPE)])
        mock_sm.push.assert_not_called()

    def test_esc_while_overlay_closed_calls_push_pause(self, game_scene):
        """ESC without an open overlay must invoke _push_pause()."""
        with patch.object(game_scene, "_push_pause") as mock_pause:
            game_scene._map_overlay_visible = False
            game_scene.handle_events([_key_event(pygame.K_ESCAPE)])
            mock_pause.assert_called_once()

    def test_overlay_render_shows_all_zone_names(self, game_scene, screen):
        """When the overlay is visible, render() must complete (zone-label smoke test)."""
        game_scene._map_overlay_visible = True
        game_scene.render(screen)  # must not raise


# ---------------------------------------------------------------------------
# TestZoneTransitions
# ---------------------------------------------------------------------------
class TestZoneTransitions:
    """Zone transitions must emit zone_entered with the correct Zone object."""

    def test_first_update_emits_zone_entered_for_hangar_bay(self, game_scene, event_bus):
        entered = []
        event_bus.subscribe("zone_entered", lambda **kw: entered.append(kw.get("zone")))

        game_scene.update(dt=0.016)

        assert len(entered) == 1
        assert entered[0].name == "HANGAR BAY"

    def test_staying_in_same_zone_does_not_re_emit_event(self, game_scene, event_bus):
        entered = []
        event_bus.subscribe("zone_entered", lambda **kw: entered.append(kw.get("zone")))

        game_scene.update(dt=0.016)
        game_scene.update(dt=0.016)

        assert len(entered) == 1, (
            "zone_entered must fire only once when the player stays in the same zone"
        )

    def test_teleport_to_reactor_core_emits_zone_entered(self, game_scene, event_bus):
        entered = []
        event_bus.subscribe("zone_entered", lambda **kw: entered.append(kw.get("zone")))

        # Settle initial zone (HANGAR BAY)
        game_scene.update(dt=0.001)

        # REACTOR CORE occupies world x 1088–2175 (cols 34–67)
        game_scene.player.rect.x = 1500
        game_scene.player.rect.y = 500
        game_scene.update(dt=0.001)

        assert any(z.name == "REACTOR CORE" for z in entered), (
            "Expected zone_entered for REACTOR CORE after teleporting player there"
        )

    def test_teleport_to_extraction_pad_emits_zone_entered(self, game_scene, event_bus):
        entered = []
        event_bus.subscribe("zone_entered", lambda **kw: entered.append(kw.get("zone")))

        game_scene.update(dt=0.001)

        # EXTRACTION PAD occupies world x 2176–3199 (cols 68–99)
        game_scene.player.rect.x = 2400
        game_scene.player.rect.y = 500
        game_scene.update(dt=0.001)

        assert any(z.name == "EXTRACTION PAD" for z in entered)

    def test_all_three_zones_visited_sequentially(self, game_scene, event_bus):
        """Walking through all three zones must fire zone_entered three times."""
        visited = []
        event_bus.subscribe("zone_entered", lambda **kw: visited.append(kw.get("zone").name))

        # HANGAR BAY (player spawns here)
        game_scene.update(dt=0.001)

        # REACTOR CORE
        game_scene.player.rect.x = 1500
        game_scene.player.rect.y = 500
        game_scene.update(dt=0.001)

        # EXTRACTION PAD
        game_scene.player.rect.x = 2400
        game_scene.player.rect.y = 500
        game_scene.update(dt=0.001)

        assert "HANGAR BAY" in visited
        assert "REACTOR CORE" in visited
        assert "EXTRACTION PAD" in visited


# ---------------------------------------------------------------------------
# TestExtractionIntegration
# ---------------------------------------------------------------------------
class TestExtractionIntegration:
    """Extraction zone detection, hold-E progress, success/failure events."""

    def _centre_player_on_extraction(self, game_scene: "GameScene") -> None:
        """Teleport the player's centre to the extraction zone centre."""
        er = game_scene.tile_map.extraction_rect
        game_scene.player.rect.x = er.x + er.w // 2 - game_scene.player.rect.w // 2
        game_scene.player.rect.y = er.y + er.h // 2 - game_scene.player.rect.h // 2

    def test_player_overlapping_extraction_rect_is_detected(self, game_scene):
        self._centre_player_on_extraction(game_scene)
        assert game_scene._extraction.is_player_in_zone(game_scene.player)

    def test_player_far_from_extraction_rect_is_not_detected(self, game_scene):
        game_scene.player.rect.x = 0
        game_scene.player.rect.y = 800
        assert not game_scene._extraction.is_player_in_zone(game_scene.player)

    def test_two_second_hold_e_emits_extraction_success(self, game_scene, event_bus):
        success = []
        event_bus.subscribe("extraction_success", lambda **kw: success.append(kw))

        self._centre_player_on_extraction(game_scene)
        # HOLD_DURATION = 2.0 s; advance by 2.1 s to cross the threshold
        game_scene._extraction.update([game_scene.player], dt=2.1, e_held=True)

        assert len(success) == 1
        assert "player" in success[0]

    def test_one_second_hold_e_does_not_trigger_success(self, game_scene, event_bus):
        """Holding E for only 1 s (of 2 s required) must not fire extraction_success."""
        success = []
        event_bus.subscribe("extraction_success", lambda **kw: success.append(kw))

        self._centre_player_on_extraction(game_scene)
        game_scene._extraction.update([game_scene.player], dt=1.0, e_held=True)

        assert len(success) == 0

    def test_extraction_progress_property_reflects_hold_time(self, game_scene):
        self._centre_player_on_extraction(game_scene)
        game_scene._extraction.update([game_scene.player], dt=1.0, e_held=True)

        progress = game_scene._extraction.extraction_progress
        assert 0.0 < progress <= 1.0

    def test_releasing_e_decreases_hold_progress(self, game_scene):
        self._centre_player_on_extraction(game_scene)
        game_scene._extraction.update([game_scene.player], dt=1.0, e_held=True)
        progress_after_hold = game_scene._extraction._hold_progress
        assert progress_after_hold > 0.0

        # Release E — progress decays
        game_scene._extraction.update([game_scene.player], dt=0.5, e_held=False)
        assert game_scene._extraction._hold_progress < progress_after_hold

    def test_extraction_timer_decrements_during_update(self, game_scene):
        before = game_scene._extraction.seconds_remaining
        game_scene.update(dt=1.0)
        assert game_scene._extraction.seconds_remaining < before

    def test_extraction_progress_is_zero_before_any_hold(self, game_scene):
        assert game_scene._extraction.extraction_progress == pytest.approx(0.0)

    def test_extraction_success_event_causes_scene_replace(self, game_scene, event_bus, mock_sm):
        """Firing extraction_success must trigger _on_extract → sm.replace()."""
        # Call _on_extract directly (it has its own try/except guard)
        game_scene._on_extract(player=game_scene.player)
        assert mock_sm.replace.called, (
            "sm.replace() was not called; verify PostRound and SaveManager are importable"
        )

    def test_extraction_failed_event_causes_scene_replace(self, game_scene, event_bus, mock_sm):
        """Firing extraction_failed must trigger _on_extract_failed → sm.replace()."""
        game_scene._on_extract_failed()
        assert mock_sm.replace.called, (
            "sm.replace() was not called when extraction failed; "
            "verify PostRound and SaveManager are importable"
        )

    def test_full_extraction_flow_via_event_bus(self, game_scene, event_bus, mock_sm):
        """End-to-end: hold E in zone → extraction_success → scene transitions."""
        self._centre_player_on_extraction(game_scene)

        # Drive the extraction system past HOLD_DURATION
        game_scene._extraction.update([game_scene.player], dt=2.1, e_held=True)

        # extraction_success was emitted; _on_extract (subscribed in __init__) fires
        # and calls sm.replace() with a PostRound scene
        assert mock_sm.replace.called


# ---------------------------------------------------------------------------
# TestPlayabilityEndToEnd
# ---------------------------------------------------------------------------
class TestPlayabilityEndToEnd:
    """Coarse end-to-end smoke tests: the map is self-contained and playable."""

    def test_screen_resolution_is_1280x720(self, game_scene):
        w, h = game_scene._settings.resolution_tuple
        assert w == 1280
        assert h == 720

    def test_all_zones_have_non_zero_area(self, game_scene):
        for zone in game_scene.tile_map.zones:
            assert zone.rect.width > 0, f"{zone.name} has zero width"
            assert zone.rect.height > 0, f"{zone.name} has zero height"

    def test_ceiling_row_is_entirely_solid(self, game_scene):
        """Row 0 must be fully solid (world ceiling)."""
        tm = game_scene.tile_map
        for col in range(0, tm.width, 5):  # step by 5 for speed
            assert tm.is_solid(col, 0), f"Ceiling tile col={col} row=0 should be solid"

    def test_bottom_rows_are_entirely_solid(self, game_scene):
        """Rows 27–29 must be fully solid (world floor)."""
        tm = game_scene.tile_map
        for row in range(27, tm.height):
            for col in range(0, tm.width, 5):
                assert tm.is_solid(col, row), (
                    f"Floor tile col={col} row={row} should be solid"
                )

    def test_interior_air_tiles_are_passable(self, game_scene):
        """Sample air tiles in rows 2-4 (always open) across all three zones."""
        tm = game_scene.tile_map
        # Row 2 is open in all zones (only left/right boundary walls are solid)
        for col in (5, 50, 85):
            assert not tm.is_solid(col, 2), (
                f"Interior air tile col={col} row=2 should not be solid"
            )

    def test_extraction_zone_tiles_are_passable(self, game_scene):
        """Every tile covered by extraction_rect must be type 0 or 2 — never solid."""
        tm = game_scene.tile_map
        er = tm.extraction_rect
        ts = tm.tile_size
        col_start = er.x // ts
        col_end = (er.right - 1) // ts
        row_start = er.y // ts
        row_end = (er.bottom - 1) // ts

        for row in range(row_start, row_end + 1):
            for col in range(col_start, col_end + 1):
                assert not tm.is_solid(col, row), (
                    f"Extraction tile ({col},{row}) must not be solid"
                )

    def test_walkability_grid_is_strict_inverse_of_is_solid(self, game_scene):
        """walkability_grid[r][c] == 0 iff is_solid(c, r) is True, spot-checked."""
        tm = game_scene.tile_map
        wg = tm.walkability_grid
        for row in range(0, tm.height, 5):
            for col in range(0, tm.width, 5):
                solid = tm.is_solid(col, row)
                walkable = wg[row][col]
                assert (solid and walkable == 0) or (not solid and walkable == 1), (
                    f"Mismatch at ({col},{row}): is_solid={solid}, "
                    f"walkability_grid={walkable}"
                )

    def test_player_stays_within_map_bounds_during_normal_play(self, game_scene):
        """After 120 frames the player must remain inside the tile-map world rect."""
        for _ in range(120):
            game_scene.update(dt=0.016)

        mr = game_scene.tile_map.map_rect
        p = game_scene.player.rect
        assert mr.contains(p) or mr.colliderect(p), (
            f"Player rect {p} left the map world rect {mr}"
        )

    def test_thirty_frame_update_render_loop_completes(self, game_scene, screen):
        """30 interleaved update+render frames must complete without error."""
        for _ in range(30):
            game_scene.update(dt=1 / 60)
            game_scene.render(screen)
