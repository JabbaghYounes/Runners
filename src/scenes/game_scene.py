"""
GameScene — the in-round scene.  Wraps all game systems into a BaseScene.
"""
import pygame
import random
from typing import List, Optional, Any

from src.scenes.base_scene import BaseScene
from src.constants import BG_DEEP, SCREEN_W, SCREEN_H
from src.core.event_bus import EventBus
from src.core.settings import Settings
from src.core.asset_manager import AssetManager

from src.map.tile_map import TileMap
from src.map.camera import Camera
from src.map.map_overlay import MapOverlay

from src.entities.player import Player
from src.entities.loot_item import LootItem
from src.entities.projectile import Projectile

from src.data.enemy_database import EnemyDatabase
from src.inventory.item_database import ItemDatabase

from src.systems.physics import PhysicsSystem
from src.systems.combat import CombatSystem
from src.systems.ai_system import AISystem
from src.systems.spawn_system import SpawnSystem
from src.systems.loot_system import LootSystem
from src.systems.extraction import ExtractionSystem
from src.systems.audio_system import AudioSystem
from src.systems.challenge_system import ChallengeSystem
from src.systems.buff_system import BuffSystem

from src.ui.hud import HUD
from src.ui.hud_state import HUDState, ZoneInfo, WeaponInfo

import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _path(*parts: str) -> str:
    return os.path.join(_ROOT, *parts)


class GameScene(BaseScene):
    """Full in-round game scene."""

    def __init__(
        self,
        sm: Any,
        settings: Settings,
        assets: AssetManager,
        event_bus: EventBus,
        xp_system: Any,
        currency: Any,
        home_base: Any,
    ):
        self._sm = sm
        self._settings = settings
        self._assets = assets
        self._event_bus = event_bus
        self._xp_system = xp_system
        self._currency = currency
        self._home_base = home_base

        # --- Map ---
        self.tile_map: TileMap = TileMap.load(_path('assets', 'maps', 'map_01.json'))
        mr = self.tile_map.map_rect

        # --- Camera ---
        w, h = settings.resolution_tuple
        self.camera: Camera = Camera(w, h, mr.w, mr.h)

        # --- Player ---
        sx, sy = self.tile_map.player_spawn
        self.player: Player = Player(sx, sy)

        # --- Databases ---
        self._item_db = ItemDatabase.instance()
        if not self._item_db.item_ids:
            self._item_db.load(_path('data', 'items.json'))

        self._enemy_db = EnemyDatabase()
        self._enemy_db.load(_path('data', 'enemies.json'))

        # --- Enemies ---
        spawn_sys = SpawnSystem()
        self.enemies: List[Any] = spawn_sys.spawn_all_zones(
            self.tile_map.zones, self._enemy_db
        )

        # --- Loot ---
        self.loot_items: List[LootItem] = []
        for lx, ly in self.tile_map.loot_spawns:
            item_id = random.choice(self._item_db.item_ids) if self._item_db.item_ids else None
            if item_id:
                item = self._item_db.create(item_id)
                if item:
                    self.loot_items.append(LootItem(lx, ly, item))

        # --- Projectiles ---
        self.projectiles: List[Projectile] = []

        # --- Systems ---
        self._physics = PhysicsSystem()
        self._combat = CombatSystem()
        self._ai = AISystem()
        self._loot = LootSystem(event_bus, self._item_db)
        self._buff = BuffSystem()
        self._challenge = ChallengeSystem(event_bus)
        self._audio = AudioSystem(event_bus, assets)

        ext_rect = self.tile_map.extraction_rect or pygame.Rect(0, 0, 32, 32)
        self._extraction = ExtractionSystem(ext_rect, event_bus, total_time=900.0)

        # --- UI ---
        self._hud = HUD(event_bus)
        self._map_overlay = MapOverlay(w, h)
        self._map_overlay_visible: bool = False

        # --- Zone tracking ---
        self._current_zone: Optional[Any] = None

        # --- Input state ---
        self._e_held: bool = False

        # --- Subscribe events ---
        event_bus.subscribe('enemy_killed', self._on_enemy_killed)
        event_bus.subscribe('extraction_success', self._on_extract)
        event_bus.subscribe('extraction_failed', self._on_extract_failed)

    # ------------------------------------------------------------------ #
    #  BaseScene interface                                                 #
    # ------------------------------------------------------------------ #

    def on_enter(self) -> None:
        pass

    def on_exit(self) -> None:
        pass

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self._map_overlay_visible:
                        self._map_overlay_visible = False
                    else:
                        self._push_pause()
                elif event.key == pygame.K_m:
                    self._map_overlay_visible = not self._map_overlay_visible

        if not self._map_overlay_visible:
            self.player.handle_input(pygame.key.get_pressed(), events)

    def update(self, dt: float) -> None:
        if self._map_overlay_visible:
            return

        keys = pygame.key.get_pressed()
        self._e_held = bool(keys[pygame.K_e])

        # --- Shooting ---
        if self.player._shoot_pressed and self.player.inventory.equipped:
            weapon = self.player.inventory.equipped
            mx, my = pygame.mouse.get_pos()
            wx, wy = self.camera.screen_to_world(mx, my)
            dmg = weapon.get_stat('damage', 15)
            proj = self._combat.fire(self.player, wx, wy, damage=dmg)
            self.projectiles.append(proj)

        # --- Physics ---
        all_physical = [self.player] + [e for e in self.enemies if e.alive]
        self._physics.update(all_physical, self.tile_map, dt)

        # --- Projectile movement ---
        for proj in self.projectiles:
            proj.update(dt)
        self.projectiles = [p for p in self.projectiles if p.alive]

        # --- Combat (projectiles vs enemies) ---
        self._combat.update(
            self.projectiles,
            [e for e in self.enemies if e.alive],
            dt,
        )

        # --- AI ---
        self._ai.update(
            [e for e in self.enemies if e.alive],
            self.player, self.tile_map, dt, self._event_bus,
        )

        # --- Loot ---
        new_drops = self._loot.update(self._e_held, self.loot_items, [self.player])
        self.loot_items.extend(new_drops)
        for li in self.loot_items:
            li.update(dt)
        self.loot_items = [li for li in self.loot_items if not li.despawn]

        # --- Extraction ---
        self._extraction.update([self.player], dt, e_held=self._e_held)

        # --- Buffs ---
        self._buff.update(dt)

        # --- Camera ---
        self.camera.update(self.player.rect)
        self.tile_map.update(dt)

        # --- Zone transitions ---
        player_pos = self.player.center
        for zone in self.tile_map.zones:
            if zone.contains(player_pos):
                if self._current_zone is not zone:
                    self._current_zone = zone
                    self._event_bus.emit('zone_entered', zone=zone)
                break

        # --- Player death ---
        if not self.player.alive:
            self._on_player_dead()

        # --- HUD ---
        self._hud.update(self._build_hud_state(), dt)

    def render(self, screen: pygame.Surface) -> None:
        screen.fill(BG_DEEP)

        # Tile map
        self.tile_map.render(screen, self.camera)

        cam_off = self.camera.offset

        # Loot
        for li in self.loot_items:
            li.render(screen, cam_off)

        # Enemies
        for enemy in self.enemies:
            if enemy.alive:
                enemy.render(screen, cam_off)

        # Projectiles
        for proj in self.projectiles:
            proj.render(screen, cam_off)

        # Player
        self.player.render(screen, cam_off)

        # HUD
        self._hud.draw(screen)

        # Map overlay (M key)
        if self._map_overlay_visible:
            self._map_overlay.render(
                screen,
                zones=self.tile_map.zones,
                player_pos=self.player.center,
                extraction_rect=self.tile_map.extraction_rect,
                enemies=self.enemies,
                seconds_remaining=self._extraction.seconds_remaining,
                map_rect=self.tile_map.map_rect,
            )

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _build_hud_state(self) -> HUDState:
        ext_rect = self.tile_map.extraction_rect
        return HUDState(
            hp=self.player.health,
            max_hp=self.player.max_health,
            armor=self.player.armor,
            max_armor=self.player.max_armor,
            level=self._xp_system.level,
            xp=self._xp_system.xp,
            xp_to_next=self._xp_system.xp_to_next_level(),
            seconds_remaining=self._extraction.seconds_remaining,
            player_world_pos=self.player.center,
            map_world_rect=self.tile_map.map_rect,
            zones=[
                ZoneInfo(z.name, (z.rect.x, z.rect.y, z.rect.w, z.rect.h))
                for z in self.tile_map.zones
            ],
            extraction_pos=(
                (float(ext_rect.centerx), float(ext_rect.centery))
                if ext_rect else None
            ),
            equipped_weapon=(
                WeaponInfo(
                    name=self.player.inventory.equipped.name,
                    ammo=0,
                    max_ammo=0,
                )
                if self.player.inventory.equipped else None
            ),
            in_extraction_zone=self._extraction.is_player_in_zone(self.player),
            extraction_progress=self._extraction.extraction_progress,
            currency=self._currency.balance,
            active_challenges=self._challenge.get_active_challenges(),
        )

    def _on_enemy_killed(self, **kwargs: Any) -> None:
        xp = kwargs.get('xp_reward', 0)
        old_level = self._xp_system.level
        self._xp_system.award(xp)
        if self._xp_system.level > old_level:
            self._event_bus.emit('level.up', level=self._xp_system.level)

    def _on_extract(self, **kwargs: Any) -> None:
        """Extraction succeeded — push PostRound."""
        try:
            from src.scenes.post_round import PostRound
            from src.save.save_manager import SaveManager
            save_mgr = SaveManager(_path('saves', 'save.json'))
            self._sm.replace(PostRound(
                self._sm, self._settings, self._assets,
                self._xp_system, self._currency, save_mgr,
                extracted=True,
                loot_items=list(self.player.inventory.get_items()),
            ))
        except Exception as e:
            print(f"[GameScene] PostRound push failed: {e}")

    def _on_extract_failed(self, **kwargs: Any) -> None:
        print("[GameScene] Extraction failed — time expired.")
        try:
            from src.scenes.post_round import PostRound
            from src.save.save_manager import SaveManager
            save_mgr = SaveManager(_path('saves', 'save.json'))
            self._sm.replace(PostRound(
                self._sm, self._settings, self._assets,
                self._xp_system, self._currency, save_mgr,
                extracted=False,
                loot_items=list(self.player.inventory.get_items()),
            ))
        except Exception as e:
            print(f"[GameScene] PostRound push failed: {e}")

    def _on_player_dead(self) -> None:
        print("[GameScene] Player died.")
        try:
            from src.scenes.post_round import PostRound
            from src.save.save_manager import SaveManager
            save_mgr = SaveManager(_path('saves', 'save.json'))
            self._sm.replace(PostRound(
                self._sm, self._settings, self._assets,
                self._xp_system, self._currency, save_mgr,
                extracted=False,
                loot_items=[],
            ))
        except Exception as e:
            print(f"[GameScene] PostRound push failed: {e}")

    def _push_pause(self) -> None:
        try:
            from src.scenes.pause_menu import PauseMenu
            self._sm.push(PauseMenu(self._sm, self._settings, self._assets))
        except Exception as e:
            print(f"[GameScene] PauseMenu push failed: {e}")
