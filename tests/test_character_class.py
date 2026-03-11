"""Tests for CharacterClass and PassiveAbility (src/entities/character_class.py).

Covers:
  - PassiveAbility dataclass fields and defaults
  - CharacterClass dataclass fields
  - VANGUARD constant: id, name, base_health, base_armor, passive
  - Iron Skin hook: +20 % effective armor when health ≤ 50 %
"""
import pytest


# Skip the entire module gracefully if the feature file has not been created yet.
character_class = pytest.importorskip(
    "src.entities.character_class",
    reason="src/entities/character_class.py not yet implemented",
)


# ---------------------------------------------------------------------------
# PassiveAbility
# ---------------------------------------------------------------------------

class TestPassiveAbility:
    def test_can_instantiate(self):
        p = character_class.PassiveAbility(name="Test", description="Desc")
        assert p is not None

    def test_name_field(self):
        p = character_class.PassiveAbility(name="Iron Skin", description="desc")
        assert p.name == "Iron Skin"

    def test_description_field(self):
        p = character_class.PassiveAbility(name="n", description="Heals on kill")
        assert p.description == "Heals on kill"

    def test_on_get_effective_armor_defaults_none(self):
        p = character_class.PassiveAbility(name="n", description="d")
        assert p.on_get_effective_armor is None

    def test_on_get_effective_armor_accepts_callable(self):
        hook = lambda player: player.armor * 2.0
        p = character_class.PassiveAbility(name="n", description="d",
                                           on_get_effective_armor=hook)
        assert callable(p.on_get_effective_armor)


# ---------------------------------------------------------------------------
# CharacterClass
# ---------------------------------------------------------------------------

class TestCharacterClass:
    def _passive(self):
        return character_class.PassiveAbility(name="None", description="None")

    def test_can_instantiate(self):
        cc = character_class.CharacterClass(
            id="test", name="Tester", base_health=100,
            base_armor=5, passive=self._passive()
        )
        assert cc is not None

    def test_id_field(self):
        cc = character_class.CharacterClass(
            id="warrior", name="Warrior", base_health=100,
            base_armor=5, passive=self._passive()
        )
        assert cc.id == "warrior"

    def test_name_field(self):
        cc = character_class.CharacterClass(
            id="x", name="Warrior", base_health=100,
            base_armor=5, passive=self._passive()
        )
        assert cc.name == "Warrior"

    def test_base_health_field(self):
        cc = character_class.CharacterClass(
            id="x", name="X", base_health=200,
            base_armor=5, passive=self._passive()
        )
        assert cc.base_health == 200

    def test_base_armor_field(self):
        cc = character_class.CharacterClass(
            id="x", name="X", base_health=100,
            base_armor=25, passive=self._passive()
        )
        assert cc.base_armor == 25

    def test_passive_field_stored(self):
        p = self._passive()
        cc = character_class.CharacterClass(
            id="x", name="X", base_health=100,
            base_armor=5, passive=p
        )
        assert cc.passive is p


# ---------------------------------------------------------------------------
# VANGUARD constant
# ---------------------------------------------------------------------------

class TestVanguard:
    @pytest.fixture(autouse=True)
    def vanguard(self):
        self.v = character_class.VANGUARD

    def test_exists(self):
        assert self.v is not None

    def test_id(self):
        assert self.v.id == "vanguard"

    def test_name(self):
        assert self.v.name == "Vanguard"

    def test_base_health_is_150(self):
        assert self.v.base_health == 150

    def test_base_armor_is_15(self):
        assert self.v.base_armor == 15

    def test_has_passive(self):
        assert self.v.passive is not None

    def test_passive_name_is_iron_skin(self):
        assert self.v.passive.name == "Iron Skin"

    def test_passive_has_armor_hook(self):
        assert self.v.passive.on_get_effective_armor is not None
        assert callable(self.v.passive.on_get_effective_armor)


# ---------------------------------------------------------------------------
# Iron Skin passive hook
# ---------------------------------------------------------------------------

def _mock_player(current_health, max_health, armor):
    """Minimal player-like object for hook testing."""
    class _P:
        pass
    p = _P()
    p.current_health = current_health
    p.health = current_health          # backwards-compat alias
    p.max_health = max_health
    p.armor = armor
    return p


class TestIronSkinHook:
    """Iron Skin: effective armor = armor × 1.2 when health ≤ 50 % of max."""

    @pytest.fixture(autouse=True)
    def hook(self):
        self.hook = character_class.VANGUARD.passive.on_get_effective_armor

    def test_full_health_no_bonus(self):
        p = _mock_player(150, 150, 20)
        assert self.hook(p) == pytest.approx(20.0)

    def test_above_50_percent_no_bonus(self):
        # 100/150 ≈ 66.7 % → above threshold
        p = _mock_player(100, 150, 20)
        assert self.hook(p) == pytest.approx(20.0)

    def test_exactly_50_percent_activates(self):
        # 75/150 = 50 % → Iron Skin active
        p = _mock_player(75, 150, 20)
        assert self.hook(p) == pytest.approx(24.0)   # 20 × 1.2

    def test_below_50_percent_activates(self):
        p = _mock_player(50, 150, 20)
        assert self.hook(p) == pytest.approx(24.0)

    def test_one_hp_activates(self):
        p = _mock_player(1, 150, 20)
        assert self.hook(p) == pytest.approx(24.0)

    def test_zero_health_activates(self):
        p = _mock_player(0, 150, 20)
        assert self.hook(p) == pytest.approx(24.0)

    def test_bonus_is_exactly_20_percent(self):
        p = _mock_player(1, 100, 100)
        assert self.hook(p) == pytest.approx(120.0)

    def test_zero_armor_stays_zero_regardless(self):
        p = _mock_player(1, 100, 0)
        assert self.hook(p) == pytest.approx(0.0)
