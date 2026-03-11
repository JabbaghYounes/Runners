import pygame
from enum import Enum, auto
from typing import Tuple, List, Dict, Any, Optional
from src.entities.entity import Entity

class AIState(Enum):
    PATROL = auto()
    AGGRO = auto()
    ATTACK = auto()
    DEAD = auto()

class RobotEnemy(Entity):
    def __init__(self, x: float, y: float, type_id: str = 'grunt'):
        super().__init__(x, y, 28, 40)
        self.type_id: str = type_id
        self.hp: int = 60
        self.max_hp: int = 60
        self.speed: float = 80.0
        self.aggro_range: float = 200.0
        self.attack_range: float = 60.0
        self.attack_damage: int = 10
        self.attack_cooldown: float = 1.5
        self._attack_timer: float = 0.0
        self.xp_reward: int = 50
        self.loot_table: List[Dict[str, Any]] = []
        self.ai_state: AIState = AIState.PATROL
        self.patrol_waypoints: List[Tuple[float, float]] = []
        self._wp_index: int = 0
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.on_ground: bool = False
        self._anim_timer: float = 0.0

    def take_damage(self, amount: int) -> None:
        self.hp = max(0, self.hp - amount)
        if self.hp <= 0:
            self.ai_state = AIState.DEAD
            self.alive = False

    def is_dead(self) -> bool:
        return self.hp <= 0

    def advance_animation(self) -> None:
        self._anim_timer += 1

    def render(self, screen: pygame.Surface, camera_offset: Tuple[int, int]) -> None:
        if not self.alive:
            return
        ox, oy = camera_offset
        draw_rect = pygame.Rect(self.rect.x - ox, self.rect.y - oy, self.rect.w, self.rect.h)
        color = (220, 80, 80) if self.type_id == 'elite' else (180, 60, 60)
        pygame.draw.rect(screen, color, draw_rect)
        # HP bar
        bar_w = self.rect.w
        hp_pct = self.hp / max(1, self.max_hp)
        pygame.draw.rect(screen, (60, 20, 20), (draw_rect.x, draw_rect.y - 6, bar_w, 4))
        pygame.draw.rect(screen, (220, 60, 60), (draw_rect.x, draw_rect.y - 6, int(bar_w * hp_pct), 4))
