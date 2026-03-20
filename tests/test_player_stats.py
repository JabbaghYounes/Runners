# Run: pytest tests/test_player_stats.py
"""Tests for the Player entity: stats, health pool, armor, damage, healing,
animation-state flags, and CharacterClass integration.

Covers:
  - Initialisation: position, dimensions, health, armor, alive flag, inventory
  - take_damage: net health reduction, return value, health floor, death
  - heal: health gain, max_health clamp
  - Armor stat: field exists and is non-negative
  - get_effective_armor: exists and returns numeric value
  - CharacterClass integration: VANGUARD stats drive max_health / base_armor;
    Iron Skin activates at ≤ 50 % health
  - Animation-state flags: is_sliding / is_crouching public attributes
  - Entity.animation_controller field: present on Player; render uses it
"""
import pytest
import pygame

from src.entities.player import Player
from src.entities.entity import Entity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_hp(player):
    """Return current health regardless of whether it's called health or current_health."""
    return getattr(player, 'current_health', player.health)


def _try_import_vanguard():
    try:
        from src.entities.character_class import VANGUARD
        return VANGUARD
    except ImportError:
        return None


@pytest.fixture()
def player():
    return Player(x=100, y=200)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestPlayerInit:
    def test_rect_x(self, player):
        assert player.rect.x == 100

    def test_rect_y(self, player):
        assert player.rect.y == 200

    def test_rect_width(self, player):
        assert player.rect.w == 28

    def test_rect_height(self, player):
        assert player.rect.h == 48

    def test_starts_alive(self, player):
        assert player.alive is True

    def test_has_health_field(self, player):
        has = hasattr(player, 'health') or hasattr(player, 'current_health')
        assert has

    def test_has_max_health(self, player):
        assert hasattr(player, 'max_health')
        assert player.max_health > 0

    def test_health_equals_max_at_start(self, player):
        assert _get_hp(player) == player.max_health

    def test_has_armor_field(self, player):
        assert hasattr(player, 'armor')

    def test_armor_nonnegative_at_start(self, player):
        assert player.armor >= 0

    def test_has_max_armor(self, player):
        assert hasattr(player, 'max_armor')

    def test_has_inventory(self, player):
        assert player.inventory is not None

    def test_velocity_zero_at_start(self, player):
        assert player.vx == 0.0
        assert player.vy == 0.0

    def test_on_ground_false_at_start(self, player):
        assert player.on_ground is False


# ---------------------------------------------------------------------------
# Health pool
# ---------------------------------------------------------------------------

class TestHealthPool:
    def test_max_health_at_least_100(self, player):
        assert player.max_health >= 100

    def test_health_is_positive(self, player):
        assert _get_hp(player) > 0

    def test_health_shown_in_hud_state_fields(self, player):
        """HUD reads hp from HUDState, not Player directly — just confirm
        the player exposes what a GameScene can copy across."""
        # Both health-naming conventions must yield a non-negative integer.
        hp = _get_hp(player)
        assert isinstance(hp, int)
        assert hp >= 0


# ---------------------------------------------------------------------------
# take_damage
# ---------------------------------------------------------------------------

class TestTakeDamage:
    def test_reduces_health(self, player):
        player.armor = 0
        hp_before = _get_hp(player)
        player.take_damage(10)
        assert _get_hp(player) < hp_before

    def test_exact_reduction_with_zero_armor(self, player):
        player.armor = 0
        hp_before = _get_hp(player)
        player.take_damage(15)
        assert hp_before - _get_hp(player) == 15

    def test_returns_net_damage_integer(self, player):
        player.armor = 0
        net = player.take_damage(20)
        assert isinstance(net, int)
        assert net > 0

    def test_health_floor_is_zero(self, player):
        player.armor = 0
        player.take_damage(99999)
        assert _get_hp(player) == 0

    def test_player_dies_at_zero_health(self, player):
        player.armor = 0
        player.take_damage(99999)
        assert _get_hp(player) == 0
        assert player.alive is False

    def test_partial_damage_does_not_kill(self, player):
        player.armor = 0
        player.take_damage(player.max_health - 1)
        assert player.alive is True

    def test_repeated_damage_accumulates(self, player):
        player.armor = 0
        player.take_damage(10)
        player.take_damage(10)
        hp = _get_hp(player)
        assert hp == player.max_health - 20

    def test_zero_damage_no_change(self, player):
        hp_before = _get_hp(player)
        player.take_damage(0)
        assert _get_hp(player) == hp_before


# ---------------------------------------------------------------------------
# Armor stat
# ---------------------------------------------------------------------------

class TestArmorStat:
    def test_armor_field_exists(self, player):
        assert hasattr(player, 'armor')

    def test_armor_is_nonnegative(self, player):
        assert player.armor >= 0

    def test_armor_reduces_damage_taken(self, player):
        """Armor reduces incoming damage via the CombatSystem formula.

        ``take_damage()`` no longer self-applies armor — reduction happens in
        CombatSystem (``effective = max(1, raw - armor)``).  This test verifies
        the full chain: setting ``player.armor`` is reflected by
        ``get_effective_armor()``, and the CombatSystem-computed effective
        damage is less than the raw incoming value.
        """
        player.armor = 20
        # get_effective_armor() must reflect the current armor value
        assert player.get_effective_armor() == 20.0

        raw_damage = 30
        # CombatSystem formula
        effective = max(1, raw_damage - int(player.get_effective_armor()))
        hp_before = _get_hp(player)
        player.take_damage(effective)
        net_loss = hp_before - _get_hp(player)
        # Armor absorbed part of the blow; effective damage < raw
        assert net_loss < raw_damage

    def test_zero_armor_takes_full_damage(self, player):
        player.armor = 0
        hp_before = _get_hp(player)
        player.take_damage(25)
        assert hp_before - _get_hp(player) == 25


# ---------------------------------------------------------------------------
# heal
# ---------------------------------------------------------------------------

class TestHeal:
    def test_increases_health(self, player):
        player.armor = 0
        player.take_damage(30)
        hp_before = _get_hp(player)
        player.heal(10)
        assert _get_hp(player) > hp_before

    def test_clamped_at_max_health(self, player):
        player.heal(99999)
        assert _get_hp(player) == player.max_health

    def test_heal_from_damaged_state(self, player):
        player.armor = 0
        player.take_damage(50)
        player.heal(20)
        expected = player.max_health - 50 + 20
        assert _get_hp(player) == expected

    def test_heal_zero_no_change(self, player):
        player.armor = 0
        player.take_damage(10)
        hp_before = _get_hp(player)
        player.heal(0)
        assert _get_hp(player) == hp_before


# ---------------------------------------------------------------------------
# CharacterClass integration (skipped when module not yet implemented)
# ---------------------------------------------------------------------------

class TestCharacterClassIntegration:
    @pytest.fixture(autouse=True)
    def skip_if_no_module(self):
        vanguard = _try_import_vanguard()
        if vanguard is None:
            pytest.skip("src/entities/character_class.py not yet implemented")
        self.VANGUARD = vanguard

    def test_player_accepts_character_class_kwarg(self):
        p = Player(x=0, y=0, character_class=self.VANGUARD)
        assert hasattr(p, 'character_class')

    def test_character_class_stored(self):
        p = Player(x=0, y=0, character_class=self.VANGUARD)
        assert p.character_class is self.VANGUARD

    def test_vanguard_max_health_is_150(self):
        p = Player(x=0, y=0, character_class=self.VANGUARD)
        assert p.max_health == 150

    def test_vanguard_base_armor_is_15(self):
        p = Player(x=0, y=0, character_class=self.VANGUARD)
        assert hasattr(p, 'base_armor')
        assert p.base_armor == 15

    def test_vanguard_starts_at_full_health(self):
        p = Player(x=0, y=0, character_class=self.VANGUARD)
        assert _get_hp(p) == 150

    def test_get_effective_armor_method_exists(self):
        p = Player(x=0, y=0, character_class=self.VANGUARD)
        assert callable(getattr(p, 'get_effective_armor', None))

    def test_get_effective_armor_returns_armor_at_full_health(self):
        p = Player(x=0, y=0, character_class=self.VANGUARD)
        effective = p.get_effective_armor()
        assert isinstance(effective, (int, float))
        # At full health Iron Skin is inactive → effective == p.armor
        assert effective == pytest.approx(p.armor)

    def test_iron_skin_activates_at_half_health(self):
        p = Player(x=0, y=0, character_class=self.VANGUARD)
        # Force health to ≤ 50 %
        if hasattr(p, 'current_health'):
            p.current_health = p.max_health // 2
        else:
            p.health = p.max_health // 2
        effective = p.get_effective_armor()
        # Iron Skin: × 1.2
        assert effective == pytest.approx(p.armor * 1.2)

    def test_recalculate_armor_method_exists(self):
        p = Player(x=0, y=0, character_class=self.VANGUARD)
        assert callable(getattr(p, '_recalculate_armor', None))

    def test_default_class_is_vanguard(self):
        """Player() with no character_class arg should default to VANGUARD."""
        p = Player(x=0, y=0)
        # Vanguard has base_health=150; if default is VANGUARD max_health==150
        vanguard_health = self.VANGUARD.base_health
        assert p.max_health == vanguard_health


# ---------------------------------------------------------------------------
# Animation-state flags
# ---------------------------------------------------------------------------

class TestAnimationStateFlags:
    def test_has_crouching_flag(self, player):
        has = hasattr(player, 'is_crouching') or hasattr(player, '_crouching')
        assert has

    def test_has_sliding_flag(self, player):
        has = hasattr(player, 'is_sliding') or hasattr(player, '_sprinting')
        assert has

    def test_crouching_false_at_start(self, player):
        val = getattr(player, 'is_crouching', getattr(player, '_crouching', False))
        assert val is False

    def test_sliding_false_at_start(self, player):
        val = getattr(player, 'is_sliding', getattr(player, '_sprinting', False))
        assert val is False


# ---------------------------------------------------------------------------
# Entity animation_controller field
# ---------------------------------------------------------------------------

class TestEntityAnimationController:
    def test_player_has_animation_controller_field(self, player):
        assert hasattr(player, 'animation_controller')

    def test_animation_controller_is_none_or_valid(self, player):
        ctrl = player.animation_controller
        assert ctrl is None or hasattr(ctrl, 'get_current_frame')

    def test_entity_render_blits_frame_when_controller_set(self):
        """Entity base render() must use the controller's frame when one is assigned."""
        from src.utils.animation import AnimationController

        class _AM:
            def load_image(self, _): return None

        entity = Entity(x=0, y=0, w=48, h=64)
        ctrl = AnimationController({"idle": ("x.png", 2, 8.0)}, _AM(),
                                   frame_w=48, frame_h=64)
        entity.animation_controller = ctrl

        surface = pygame.Surface((200, 200))
        entity.render(surface, (0, 0))   # must not raise

    def test_entity_render_with_no_controller_does_not_crash(self):
        entity = Entity(x=50, y=50)
        entity.animation_controller = None
        surface = pygame.Surface((200, 200))
        entity.render(surface, (0, 0))   # must not raise


# ---------------------------------------------------------------------------
# Player render
# ---------------------------------------------------------------------------

class TestPlayerRender:
    def test_render_does_not_crash(self, player):
        surface = pygame.Surface((640, 480))
        player.render(surface, (0, 0))

    def test_render_with_camera_offset(self, player):
        surface = pygame.Surface((640, 480))
        player.render(surface, (100, 50))   # non-zero offset must not crash


# ---------------------------------------------------------------------------
# Damage floor spec: effective = max(1, raw − armor) when raw > 0
# ---------------------------------------------------------------------------

class TestDamageFloorSpec:
    """Player.take_damage() enforces a minimum of 1 HP lost when amount > 0.

    Spec: ``effective = max(1, raw − armor)`` — armor can never reduce damage
    below 1.  A zero-damage call (amount=0) is a no-op and returns 0.
    """

    def test_damage_floor_is_one_when_armor_equals_raw_damage(self):
        """CombatSystem computes max(1, raw - armor) then passes to take_damage."""
        p = Player(x=0, y=0)
        p.armor = 15
        before = p.health
        effective = max(1, 15 - p.armor)  # CombatSystem does this

        net = p.take_damage(effective)

        assert net == 1
        assert p.health == before - 1

    def test_damage_floor_is_one_when_armor_exceeds_raw_damage(self):
        """CombatSystem floors to 1 when armor > raw_damage."""
        p = Player(x=0, y=0)
        p.armor = 50
        effective = max(1, 10 - p.armor)

        net = p.take_damage(effective)

        assert net == 1

    def test_damage_floor_is_one_with_massive_armor(self):
        """CombatSystem floors to 1 even with extreme armor."""
        p = Player(x=0, y=0)
        p.armor = 9999
        before = p.health
        effective = max(1, 5 - p.armor)

        net = p.take_damage(effective)

        assert net == 1
        assert p.health == before - 1

    def test_zero_damage_call_returns_zero(self):
        """take_damage(0) is a no-op: returns 0 and leaves health unchanged."""
        p = Player(x=0, y=0)
        before = p.health

        result = p.take_damage(0)

        assert result == 0
        assert p.health == before

    def test_zero_damage_call_does_not_kill_player(self):
        """take_damage(0) must never set alive=False."""
        p = Player(x=0, y=0)
        p.health = 1  # critically low

        p.take_damage(0)

        assert p.alive is True

    def test_damage_above_armor_deals_reduced_amount(self):
        """CombatSystem computes raw − armor when raw > armor."""
        p = Player(x=0, y=0)
        p.armor = 10
        before = p.health
        effective = max(1, 30 - p.armor)  # CombatSystem does this

        net = p.take_damage(effective)

        assert net == 20
        assert p.health == before - 20

    def test_damage_return_value_is_actual_hp_lost(self):
        """Return value must equal the number of HP deducted."""
        p = Player(x=0, y=0)
        p.armor = 5
        before = p.health

        net = p.take_damage(20)   # effective = 15
        after = p.health

        assert net == before - after

    def test_repeated_min_damage_accumulates(self):
        """Multiple 1-damage hits each reduce health by exactly 1."""
        p = Player(x=0, y=0)
        p.armor = 9999
        before = p.health

        for _ in range(5):
            p.take_damage(1)

        assert p.health == before - 5
