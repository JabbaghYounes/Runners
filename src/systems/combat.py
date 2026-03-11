import pygame
from typing import List, Any

class CombatSystem:
    def update(self, projectiles: List[Any], entities: List[Any], dt: float) -> None:
        for proj in list(projectiles):
            if not proj.alive:
                continue
            for entity in entities:
                if not getattr(entity, 'alive', True):
                    continue
                if entity is proj.owner:
                    continue
                if proj.rect.colliderect(entity.rect):
                    if hasattr(entity, 'take_damage'):
                        if hasattr(entity, 'get_effective_armor'):
                            armor = entity.get_effective_armor()
                            damage = max(1, proj.damage - armor)
                        else:
                            damage = proj.damage
                        entity.take_damage(damage)
                    proj.alive = False
                    break

    def fire(self, owner: Any, target_x: float, target_y: float,
             damage: int = 15, speed: float = 600.0) -> Any:
        from src.entities.projectile import Projectile
        import math
        cx, cy = owner.center
        dx = target_x - cx
        dy = target_y - cy
        dist = math.hypot(dx, dy) or 1
        vx = dx / dist * speed
        vy = dy / dist * speed
        return Projectile(cx - 4, cy - 2, vx, vy, damage, owner=owner)
