import pygame
from typing import Tuple, List, Optional
from src.entities.entity import Entity
from src.inventory.inventory import Inventory
from src.constants import WALK_SPEED, SPRINT_SPEED, JUMP_VEL, ACCENT_CYAN, TEXT_BRIGHT

class Player(Entity):
    def __init__(self, x: float, y: float):
        super().__init__(x, y, 28, 48)
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.on_ground: bool = False
        self.health: int = 100
        self.max_health: int = 100
        self.armor: int = 0
        self.max_armor: int = 100
        self.level: int = 1
        self.xp: int = 0
        self.inventory: Inventory = Inventory()
        self._facing_right: bool = True
        self._e_held: bool = False
        self._sprinting: bool = False
        self._crouching: bool = False
        self._shoot_pressed: bool = False

    def handle_input(self, keys: pygame.key.ScancodeWrapper, events: List[pygame.event.Event]) -> None:
        from src.constants import KEY_BINDINGS
        speed = SPRINT_SPEED if keys[pygame.K_LSHIFT] else WALK_SPEED
        if keys[pygame.K_a]:
            self.vx = -speed
            self._facing_right = False
        elif keys[pygame.K_d]:
            self.vx = speed
            self._facing_right = True
        else:
            self.vx = 0.0

        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_w:
                if self.on_ground:
                    self.vy = JUMP_VEL

        self._e_held = keys[pygame.K_e]
        self._sprinting = keys[pygame.K_LSHIFT]
        self._crouching = keys[pygame.K_s]

        self._shoot_pressed = False
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._shoot_pressed = True

    def take_damage(self, amount: int) -> int:
        absorbed = min(self.armor, amount // 2)
        self.armor = max(0, self.armor - absorbed)
        net = amount - absorbed
        self.health = max(0, self.health - net)
        if self.health <= 0:
            self.alive = False
        return net

    def heal(self, amount: int) -> None:
        self.health = min(self.max_health, self.health + amount)

    def render(self, screen: pygame.Surface, camera_offset: Tuple[int, int]) -> None:
        ox, oy = camera_offset
        draw_rect = pygame.Rect(self.rect.x - ox, self.rect.y - oy, self.rect.w, self.rect.h)
        pygame.draw.rect(screen, ACCENT_CYAN, draw_rect)
        # Direction indicator (nose)
        nx = draw_rect.right + 4 if self._facing_right else draw_rect.left - 4
        ny = draw_rect.centery
        pygame.draw.circle(screen, TEXT_BRIGHT, (nx, ny), 4)
