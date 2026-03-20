"""GameScene -- the in-round scene.  Wraps all game systems into a BaseScene.

Supports two construction modes:
1. Full: GameScene(sm, settings, assets, event_bus, xp_system, currency, home_base)
2. Stub: GameScene(sm, settings, assets)  -- minimal, no map/item loading
3. Test: GameScene(event_bus=bus, audio=audio, settings=settings, zones=zones)
"""
import os
import random

import pygame
from typing import List, Optional, Any

from src.scenes.base_scene import BaseScene
from src.constants import BG_DEEP, SCREEN_W, SCREEN_H
from src.core.event_bus import EventBus
from src.core.settings import Settings

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _path(*parts: str) -> str:
    return os.path.join(_ROOT, *parts)


class GameScene(BaseScene):
    """Full in-round game scene."""

    def __init__(
        self,
        sm: Any = None,
        settings: "Settings | None" = None,
        assets: Any = None,
        event_bus: "EventBus | None" = None,
        xp_system: Any = None,
        currency: Any = None,
        home_base: Any = None,
        *,
        audio: Any = None,
        zones: "list | None" = None,
        skill_tree: Any = None,
    ):
        self._sm = sm
        self._settings = settings or Settings()
        self._assets = assets
        self._event_bus = event_bus or EventBus()
        self._xp_system = xp_system
        self._currency = currency
        self._home_base = home_base
        self._skill_tree = skill_tree
        self._audio = audio

        # Input state
        self._e_held: bool = False
        self._map_overlay_visible: bool = False

        # Zone tracking (used by zone-only tests)
        self._current_zone: Optional[Any] = None
        self._prev_zone: Optional[Any] = None

        # Loot value bonus from home base
        self.loot_value_bonus: float = 0.0

        # Loot system — initialised to None; set by _init_full.
        # _loot_items_fallback is used by the loot_items property in stub mode.
        self._loot_sys: Optional[Any] = None
        self._loot_items_fallback: list = []

        # Try to load the full map-based setup when a scene manager is provided.
        self._full_init = False
        _want_full = self._sm is not None
        if _want_full:
            try:
                self._init_full(zones)
            except Exception as e:
                # Fall back to stub mode for lightweight tests
                self._init_stub(zones)
        else:
            self._init_stub(zones)

    def _init_full(self, zones_override):
        """Full initialization with tile map, databases, entities, systems."""
        from src.map.tile_map import TileMap
        from src.map.camera import Camera
        from src.entities.player import Player
        from src.data.enemy_database import EnemyDatabase
        from src.inventory.item_database import ItemDatabase
        from src.systems.physics import PhysicsSystem
        from src.systems.combat import CombatSystem
        from src.systems.ai_system import AISystem
        from src.systems.spawn_system import SpawnSystem
        from src.systems.loot_system import LootSystem
        from src.systems.buff_system import BuffSystem
        from src.ui.hud import HUD
        from src.ui.hud_state import HUDState, ZoneInfo, WeaponInfo

        # Map
        map_path = _path('assets', 'maps', 'map_01.json')
        self.tile_map: TileMap = TileMap.load(map_path)
        mr = self.tile_map.map_rect

        # Camera
        w, h = self._settings.resolution_tuple
        self.camera: Camera = Camera(w, h, mr.w, mr.h)

        # Player
        sx, sy = self.tile_map.player_spawn
        self.player: Player = Player(sx, sy)
        self._player = self.player

        # Databases
        self._item_db = ItemDatabase.instance()
        if not self._item_db.item_ids:
            items_path = _path('data', 'items.json')
            if os.path.exists(items_path):
                self._item_db.load(items_path)

        self._enemy_db = EnemyDatabase()
        enemies_path = _path('data', 'enemies.json')
        if os.path.exists(enemies_path):
            self._enemy_db.load(enemies_path)

        # Enemies
        spawn_sys = SpawnSystem()
        self.enemies: List[Any] = spawn_sys.spawn_all_zones(
            self.tile_map.zones, self._enemy_db
        )

        # Loot
        self.loot_items: list = []
        try:
            from src.entities.loot_item import LootItem
            for lx, ly in self.tile_map.loot_spawns:
                item_id = random.choice(self._item_db.item_ids) if self._item_db.item_ids else None
                if item_id:
                    item = self._item_db.create(item_id)
                    if item:
                        self.loot_items.append(LootItem(item, lx, ly))
        except Exception:
            pass

        # Projectiles
        self.projectiles: list = []

        # Systems
        self._physics = PhysicsSystem()
        self._combat = CombatSystem(event_bus=self._event_bus)
        self._ai = AISystem()
        try:
            self._loot_sys = LootSystem(self._event_bus, self._item_db)
        except Exception:
            self._loot_sys = None

        # Spawn static map loot through LootSystem so it owns all items from the start
        try:
            if self._loot_sys is not None:
                self._loot_sys.spawn_round_loot(self.tile_map.loot_spawns)
        except Exception:
            pass
        self._buff = BuffSystem()
        self.player.set_buff_system(self._buff)

        # Kill counter (for RoundSummary)
        self._kill_count: int = 0

        # Challenge system
        try:
            from src.systems.challenge_system import ChallengeSystem
            self._challenge = ChallengeSystem(self._event_bus)
        except Exception:
            self._challenge = None

        # Audio system
        try:
            from src.systems.audio_system import AudioSystem
            self._audio_sys = AudioSystem(self._event_bus, self._assets)
        except Exception:
            self._audio_sys = None

        # Extraction zone — stored separately for rendering.
        try:
            from src.map.extraction_zone import ExtractionZone
            _ext_rect = self.tile_map.extraction_rect or pygame.Rect(0, 0, 32, 32)
            self._extraction_zone = ExtractionZone(rect=_ext_rect)
        except Exception:
            self._extraction_zone = None

        # Extraction system
        try:
            from src.systems.extraction import ExtractionSystem
            ext_rect = self.tile_map.extraction_rect or pygame.Rect(0, 0, 32, 32)
            self._extraction = ExtractionSystem(ext_rect, self._event_bus, total_time=900.0)
        except Exception:
            try:
                from src.systems.extraction_system import ExtractionSystem as ES2
                from src.map.extraction_zone import ExtractionZone
                ext_rect = self.tile_map.extraction_rect or pygame.Rect(0, 0, 32, 32)
                zone = ExtractionZone(rect=ext_rect)
                self._extraction = ES2(self._event_bus, zone)
            except Exception:
                self._extraction = None

        # HUD
        try:
            self._hud = HUD(self._event_bus)
        except Exception:
            self._hud = None

        # Map overlay
        try:
            from src.map.map_overlay import MapOverlay
            w, h = self._settings.resolution_tuple
            self._map_overlay = MapOverlay(w, h)
        except Exception:
            self._map_overlay = None

        # Zones (for zone detection)
        if zones_override is not None:
            self._zones: list = zones_override
        else:
            self._zones: list = list(self.tile_map.zones)

        # Apply home base bonuses
        if self._home_base is not None:
            self._apply_home_base_bonuses(self.player, self._home_base)

        # Apply skill tree bonuses
        if self._skill_tree is not None:
            self._apply_skill_tree_bonuses(self.player, self._skill_tree)

        # Round timer
        from src.systems.round_timer import RoundTimer
        self._round_timer = RoundTimer(self._event_bus)

        # Transition guard — prevents double scene-replace when multiple
        # "end-of-round" events arrive in the same frame.
        self._transitioning: bool = False

        # Subscribe events
        self._event_bus.subscribe('enemy_killed', self._on_enemy_killed)
        self._event_bus.subscribe('extraction_success', self._on_extract)
        self._event_bus.subscribe('extraction_failed', self._on_extract_failed)
        self._event_bus.subscribe('round_end', self._on_round_end)

        # Round timer (started in on_enter to align with scene lifecycle)
        from src.systems.round_timer import RoundTimer
        self._round_timer = RoundTimer(self._event_bus)

        self._full_init = True

    def _init_stub(self, zones_override):
        """Stub initialization for lightweight tests."""
        from src.entities.player import Player

        self.player = Player(0, 0)
        self._player = self.player
        self.player.alive = True
        self.enemies = []
        self.loot_items = []
        self.projectiles = []
        self._zones = zones_override if zones_override is not None else self._default_zones()
        self._extraction = None
        self._round_timer = None
        self._transitioning: bool = False
        self._hud = None
        self._map_overlay = None
        self._physics = None
        self._combat = None
        self._ai = None
        self._loot_sys = None
        self._buff = None
        self._challenge = None
        if not hasattr(self, '_audio_sys'):
            self._audio_sys = None

        self._round_timer = None

        # Apply home base bonuses in stub mode too
        if self._home_base is not None:
            self._apply_home_base_bonuses(self.player, self._home_base)

        # Apply skill tree bonuses in stub mode too
        if self._skill_tree is not None:
            self._apply_skill_tree_bonuses(self.player, self._skill_tree)

    # ------------------------------------------------------------------
    # loot_items property — unified accessor for both full and stub mode
    # ------------------------------------------------------------------

    @property
    def loot_items(self) -> list:
        """Return live loot items: from LootSystem in full mode, fallback list in stub."""
        if self._loot_sys is not None:
            return self._loot_sys.loot_items
        return self._loot_items_fallback

    @loot_items.setter
    def loot_items(self, value: list) -> None:
        """Allow direct assignment in stub mode (e.g., ``self.loot_items = []``)."""
        if self._loot_sys is not None:
            # In full mode loot is owned by LootSystem — ignore external assignment
            return
        self._loot_items_fallback = value

    # ------------------------------------------------------------------
    # _apply_home_base_bonuses — tested as an unbound method call
    # ------------------------------------------------------------------

    def _apply_home_base_bonuses(self, player, home_base) -> None:
        """Apply home-base facility bonuses to the player and scene."""
        if home_base is None:
            return

        bonuses = {}
        if hasattr(home_base, 'get_round_bonuses'):
            result = home_base.get_round_bonuses()
            if isinstance(result, dict):
                bonuses = result
        if not bonuses and hasattr(home_base, 'get_all_bonuses'):
            result = home_base.get_all_bonuses()
            if isinstance(result, dict):
                bonuses = result

        # extra_hp
        extra_hp = 0
        if "extra_hp" in bonuses:
            extra_hp = int(bonuses["extra_hp"])
        elif hasattr(home_base, 'get_bonus') and not isinstance(home_base.get_bonus, type(lambda: None).__class__.__mro__[0]):
            try:
                extra_hp = int(home_base.get_bonus("extra_hp"))
            except (TypeError, ValueError):
                pass
        if extra_hp > 0:
            player.max_health += extra_hp
            player.health += extra_hp

        # extra_slots
        extra_slots = 0
        if "extra_slots" in bonuses:
            extra_slots = int(bonuses["extra_slots"])
        elif hasattr(home_base, 'get_bonus'):
            try:
                extra_slots = int(home_base.get_bonus("extra_slots"))
            except (TypeError, ValueError):
                pass
        if extra_slots > 0 and hasattr(player, 'inventory') and hasattr(player.inventory, 'expand_capacity'):
            player.inventory.expand_capacity(extra_slots)

        # loot_value_bonus
        loot_bonus = 0.0
        if "loot_value_bonus" in bonuses:
            loot_bonus = float(bonuses["loot_value_bonus"])
        elif hasattr(home_base, 'get_bonus'):
            try:
                loot_bonus = float(home_base.get_bonus("loot_value_bonus"))
            except (TypeError, ValueError):
                pass
        self.loot_value_bonus = loot_bonus

    # ------------------------------------------------------------------
    # _apply_skill_tree_bonuses — apply stat bonuses from the skill tree
    # ------------------------------------------------------------------

    def _apply_skill_tree_bonuses(self, player, skill_tree) -> None:
        """Apply stat bonuses from unlocked skill tree nodes to the player."""
        if skill_tree is None:
            return

        bonuses = {}
        if hasattr(skill_tree, "get_stat_bonuses"):
            result = skill_tree.get_stat_bonuses()
            if isinstance(result, dict):
                bonuses = result

        # extra_hp -- add to both health and max_health
        extra_hp = int(bonuses.get("extra_hp", 0))
        if extra_hp > 0:
            player.max_health += extra_hp
            player.health += extra_hp

        # extra_armor -- add to armor
        extra_armor = int(bonuses.get("extra_armor", 0))
        if extra_armor > 0:
            player.armor = getattr(player, "armor", 0) + extra_armor

        # speed_mult -- increase walk speed
        speed_mult = float(bonuses.get("speed_mult", 0))
        if speed_mult > 0:
            base_speed = getattr(player, "walk_speed", None)
            if base_speed is not None:
                player.walk_speed = base_speed * (1.0 + speed_mult)

        # damage_mult -- store on player for combat system to use
        damage_mult = float(bonuses.get("damage_mult", 0))
        if damage_mult > 0:
            player.damage_mult = getattr(player, "damage_mult", 1.0) + damage_mult

    # ------------------------------------------------------------------
    # BaseScene interface
    # ------------------------------------------------------------------

    def on_enter(self) -> None:
        if self._round_timer:
            self._round_timer.reset()
            self._round_timer.start()

    def on_exit(self) -> None:
        if self._round_timer:
            self._round_timer.reset()
        self._transitioning = False

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self._map_overlay_visible:
                        self._map_overlay_visible = False
                    else:
                        self._push_pause()
                    return
                elif event.key == pygame.K_m:
                    self._map_overlay_visible = not self._map_overlay_visible
                elif event.key == pygame.K_TAB:
                    if self._full_init and not self._map_overlay_visible:
                        self._push_inventory()
                    return

        if not self._map_overlay_visible and self._full_init:
            try:
                self.player.handle_input(pygame.key.get_pressed(), events)
            except Exception:
                pass

    def update(self, dt: float) -> None:
        if self._map_overlay_visible:
            return

        if self._full_init:
            self._update_full(dt)
        else:
            self._update_stub(dt)

    def _update_full(self, dt: float) -> None:
        self._pulse_time += dt
        try:
            from src.constants import KEY_EXTRACT
            keys = pygame.key.get_pressed()
            self._e_held = bool(keys[pygame.K_e])
            self._extract_held = bool(keys[KEY_EXTRACT])
        except Exception:
            self._e_held = False
            self._extract_held = False

        # Round timer
        if self._round_timer:
            self._round_timer.update(dt)

        # Physics
        if self._physics:
            all_physical = [self.player] + [e for e in self.enemies if e.alive]
            self._physics.update(all_physical, self.tile_map, dt)

        # Enemy animations: sync physics position + advance animation controller.
        # Must happen AFTER physics and BEFORE AISystem so AI reads correct coords.
        for enemy in self.enemies:
            if enemy.alive:
                try:
                    enemy.update(dt)
                except Exception:
                    pass

        # Projectile movement
        for proj in self.projectiles:
            proj.update(dt)
        self.projectiles = [p for p in self.projectiles if p.alive]

        # Combat — targets include the player so enemy projectiles can hit them.
        # CombatSystem already skips proj.owner == target (no self-hits).
        if self._combat:
            self._combat.update(
                self.projectiles,
                [self.player] + [e for e in self.enemies if e.alive],
                dt,
            )

        # AI — returns enemy-fired projectiles for this frame
        if self._ai:
            try:
                enemy_projs = self._ai.update(
                    [e for e in self.enemies if e.alive],
                    self.player, self.tile_map, dt, self._event_bus,
                    combat_system=self._combat,
                )
                if enemy_projs:
                    self.projectiles.extend(enemy_projs)
            except Exception:
                pass

        # Loot
        if self._loot_sys:
            try:
                self._loot_sys.update(self.player, e_key_pressed=self._e_held)
            except Exception:
                pass
        for li in self.loot_items:
            try:
                li.update(dt)
            except Exception:
                pass

        # Extraction
        if self._extraction:
            try:
                self._extraction.update([self.player], dt, e_held=self._e_held)
            except Exception:
                pass

        # Buffs
        if self._buff:
            try:
                self._buff.update(dt)
            except Exception:
                pass

        # Camera
        if hasattr(self, 'camera'):
            self.camera.update(self.player.rect)
        if hasattr(self, 'tile_map'):
            try:
                self.tile_map.update(dt)
            except Exception:
                pass

        # Zone transitions
        player_pos = self.player.center
        found_zone = None
        for zone in self._zones:
            if zone.contains(player_pos):
                found_zone = zone
                break
        if found_zone is not None:
            if self._current_zone is not found_zone:
                self._current_zone = found_zone
                self._prev_zone = found_zone
                self._event_bus.emit('zone_entered', zone=found_zone)
        else:
            self._current_zone = None

        # Player death
        if not self.player.alive:
            self._on_player_dead()

        # HUD
        if self._hud:
            try:
                self._hud.update(self._build_hud_state(), dt)
            except Exception:
                pass

        # Round timer
        if self._round_timer:
            self._round_timer.update(dt)

        # Audio forwarding
        if self._audio is not None:
            vx = getattr(self.player, 'velocity_x', 0)
            vy = getattr(self.player, 'velocity_y', 0)
            moving = (vx != 0 or vy != 0)
            self._audio.update(dt, player_is_moving=moving)

    def _zone_for_player(self) -> Optional[Any]:
        """Return the zone the player is currently inside, or None."""
        if hasattr(self.player, 'rect'):
            player_pos = (self.player.rect.centerx, self.player.rect.centery)
        else:
            player_pos = (0, 0)
        for zone in self._zones:
            if zone.contains(player_pos):
                return zone
        return None

    @staticmethod
    def _default_zones() -> list:
        """Create three default zones spanning 1280px total width."""
        from src.map.zone import Zone
        return [
            Zone("CARGO BAY",     pygame.Rect(0,   0, 427, 720), music_track="cargo_bay.ogg"),
            Zone("REACTOR CORE",  pygame.Rect(427, 0, 426, 720), music_track="reactor_core.ogg"),
            Zone("COMMAND DECK",  pygame.Rect(853, 0, 427, 720), music_track="command_deck.ogg"),
        ]

    def _update_stub(self, dt: float) -> None:
        """Update for stub mode (zone-only tests)."""
        current = self._zone_for_player()

        if current is not None:
            if self._current_zone is not current:
                self._current_zone = current
                self._prev_zone = current
                self._event_bus.emit('zone_entered', zone=current)
        else:
            self._current_zone = None

        # Audio forwarding
        if self._audio is not None:
            vx = getattr(self._player, 'velocity_x', 0)
            vy = getattr(self._player, 'velocity_y', 0)
            moving = (vx != 0 or vy != 0)
            self._audio.update(dt, player_is_moving=moving)

    def render(self, screen: pygame.Surface) -> None:
        screen.fill(BG_DEEP)

        if self._full_init:
            self._render_full(screen)

        # Map overlay
        if self._map_overlay_visible and self._map_overlay and self._full_init:
            try:
                self._map_overlay.render(
                    screen,
                    zones=self.tile_map.zones,
                    player_pos=self.player.center,
                    extraction_rect=self.tile_map.extraction_rect,
                    enemies=self.enemies,
                    seconds_remaining=(
                        self._round_timer.seconds_remaining if self._round_timer else 0
                    ),
                    map_rect=self.tile_map.map_rect,
                )
            except Exception:
                pass

    def _render_full(self, screen: pygame.Surface) -> None:
        # Tile map
        try:
            self.tile_map.render(screen, self.camera)
        except Exception:
            pass

        cam_off = self.camera.offset if hasattr(self, 'camera') else (0, 0)

        # Loot
        for li in self.loot_items:
            try:
                li.render(screen, cam_off)
            except Exception:
                pass

        # Enemies
        for enemy in self.enemies:
            if enemy.alive:
                try:
                    enemy.render(screen, cam_off)
                except Exception:
                    pass

        # Projectiles
        for proj in self.projectiles:
            try:
                proj.render(screen, cam_off)
            except Exception:
                pass

        # Player
        try:
            self.player.render(screen, cam_off)
        except Exception:
            pass

        # HUD
        if self._hud:
            try:
                self._hud.draw(screen)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # HUD state builder
    # ------------------------------------------------------------------

    def _build_hud_state(self):
        from src.ui.hud_state import HUDState, ZoneInfo, WeaponInfo, ConsumableSlot

        tile_map = getattr(self, 'tile_map', None)
        ext_rect = getattr(tile_map, 'extraction_rect', None) if tile_map else None
        xp_sys = self._xp_system

        # Build zones list from tile_map zones if available, else from _zones
        if tile_map and hasattr(tile_map, 'zones'):
            zone_infos = [
                ZoneInfo(
                    name=z.name,
                    color=tuple(getattr(z, 'color', (60, 120, 180))),
                    # pygame.Rect(z.rect) works whether z.rect is already a Rect
                    # or a (x, y, w, h) tuple — confirming intent here.
                    world_rect=pygame.Rect(z.rect),
                )
                for z in tile_map.zones
            ]
        else:
            zone_infos = []
            for z in self._zones:
                r = z.rect
                if isinstance(r, pygame.Rect):
                    zone_infos.append(ZoneInfo(name=z.name, world_rect=r))
                else:
                    zone_infos.append(ZoneInfo(name=z.name, world_rect=pygame.Rect(*r)))

        # Build map_world_rect from tile_map or zones
        if tile_map and hasattr(tile_map, 'map_rect'):
            map_rect = tile_map.map_rect
        elif self._zones:
            # Compute bounding rect from zones
            rects = []
            for z in self._zones:
                r = z.rect
                if isinstance(r, pygame.Rect):
                    rects.append(r)
                else:
                    rects.append(pygame.Rect(*r))
            if rects:
                map_rect = rects[0].unionall(rects[1:]) if len(rects) > 1 else rects[0]
            else:
                map_rect = pygame.Rect(0, 0, 1280, 720)
        else:
            map_rect = pygame.Rect(0, 0, 1280, 720)

        # Quick-slot items for HUD display (preserves positional alignment)
        consumable_slots = []
        try:
            inv = getattr(self.player, "inventory", None)
            if inv is not None:
                for i in range(4):
                    qs_item = inv.quick_slot_item(i)
                    if qs_item is not None:
                        consumable_slots.append(
                            ConsumableSlot(
                                label=qs_item.name[:8],
                                count=getattr(qs_item, "quantity", 1),
                                icon=None,
                            )
                        )
                    else:
                        consumable_slots.append(None)  # type: ignore[arg-type]
        except AttributeError:
            pass

        return HUDState(
            tile_surf=getattr(getattr(self, 'tile_map', None), 'baked_minimap', None),
            hp=float(self.player.health),
            max_hp=float(self.player.max_health),
            armor=float(getattr(self.player, 'armor', 0)),
            max_armor=float(getattr(self.player, 'max_armor', 100)),
            level=xp_sys.level if xp_sys else 1,
            xp=xp_sys.xp if xp_sys else 0,
            xp_to_next=xp_sys.xp_to_next_level() if xp_sys else 100,
            seconds_remaining=(
                self._round_timer.seconds_remaining if self._round_timer else 0
            ),
            player_world_pos=self.player.center,
            map_world_rect=map_rect,
            zones=zone_infos,
            extraction_pos=(
                (float(ext_rect.centerx), float(ext_rect.centery))
                if ext_rect else None
            ),
            in_extraction_zone=(
                self._extraction.is_player_in_zone(self.player)
                if self._extraction and hasattr(self._extraction, 'is_player_in_zone')
                else False
            ),
            extraction_progress=(
                self._extraction.extraction_progress
                if self._extraction and hasattr(self._extraction, 'extraction_progress')
                else 0.0
            ),
            currency=self._currency.balance if self._currency else 0,
            active_challenges=(
                self._challenge.get_active_challenges()
                if self._challenge and hasattr(self._challenge, 'get_active_challenges')
                else []
            ),
            consumable_slots=consumable_slots,
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_enemy_killed(self, **kwargs: Any) -> None:
        self._kill_count = getattr(self, '_kill_count', 0) + 1
        xp = kwargs.get('xp_reward', 0)
        if self._xp_system and xp:
            old_level = self._xp_system.level
            self._xp_system.award(xp)
            if self._xp_system.level > old_level:
                self._event_bus.emit('level.up', level=self._xp_system.level)

    def _collect_loot(self) -> list:
        """Return the player's current inventory items as a list."""
        loot: list = []
        if hasattr(self.player, 'inventory'):
            inv = self.player.inventory
            if hasattr(inv, 'get_items'):
                loot = list(inv.get_items())
            elif isinstance(inv, list):
                loot = list(inv)
        return loot

    def _build_post_round(
        self,
        status: str,
        loot: list,
        challenge_system: object,
    ) -> "PostRound":
        """Construct a PostRound instance with a full RoundSummary."""
        from src.scenes.post_round import PostRound
        from src.save.save_manager import SaveManager
        from src.core.round_summary import RoundSummary
        from src.constants import EXTRACTION_XP

        save_mgr = SaveManager(_path('saves', 'save.json'))
        level_before = self._xp_system.level if self._xp_system else 1

        completed_count = 0
        total_count = 0
        if challenge_system is not None:
            try:
                completed_count = len(challenge_system.get_completed_challenges())
                total_count = len(challenge_system.get_active_raw())
            except Exception:
                pass

        xp_earned = EXTRACTION_XP if status == "success" else 0
        summary = RoundSummary(
            extraction_status=status,
            extracted_items=list(loot),
            xp_earned=xp_earned,
            money_earned=0,
            kills=getattr(self, '_kill_count', 0),
            challenges_completed=completed_count,
            challenges_total=total_count,
            level_before=level_before,
        )

        return PostRound(
            summary=summary,
            xp_system=self._xp_system,
            currency=self._currency,
            save_manager=save_mgr,
            scene_manager=self._sm,
            audio_system=getattr(self, '_audio_sys', None),
            challenge_system=challenge_system,
        )

    def _on_extract(self, **kwargs: Any) -> None:
        """Extraction succeeded -- push PostRound."""
        if self._transitioning:
            return
        self._transitioning = True
        try:
            self._sm.replace(
                self._build_post_round("success", self._collect_loot(), self._challenge)
            )
        except Exception as e:
            print(f"[GameScene] PostRound push failed: {e}")

    def _on_extract_failed(self, **kwargs: Any) -> None:
        if self._transitioning:
            return
        self._transitioning = True
        try:
            self._sm.replace(
                self._build_post_round("timeout", [], self._challenge)
            )
        except Exception as e:
            print(f"[GameScene] PostRound push failed: {e}")

    def _on_player_dead(self) -> None:
        if self._transitioning:
            return
        self._transitioning = True
        try:
            self._sm.replace(
                self._build_post_round("eliminated", [], None)
            )
        except Exception as e:
            print(f"[GameScene] PostRound push failed: {e}")

    def _on_round_end(self, **kwargs: Any) -> None:
        """Round timer expired -- force extraction failure for all players."""
        self._on_extract_failed(**kwargs)

    def _push_pause(self) -> None:
        try:
            from src.scenes.pause_menu import PauseMenu
            # Guard against rapid double-ESC stacking two PauseMenus
            if isinstance(self._sm.active, PauseMenu):
                return
            self._sm.push(PauseMenu(self._sm, self._settings, self._assets))
        except Exception as e:
            print(f"[GameScene] PauseMenu push failed: {e}")

    def _push_inventory(self) -> None:
        """Push the InventoryScreen overlay onto the scene stack."""
        if not self._full_init:
            return
        inv = getattr(self.player, "inventory", None)
        if inv is None:
            return
        try:
            from src.ui.inventory_screen import InventoryScreen
            self._sm.push(InventoryScreen(self._sm, inv, self._assets))
        except Exception as e:
            print(f"[GameScene] InventoryScreen push failed: {e}")
