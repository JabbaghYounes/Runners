from typing import List, Any

class SpawnSystem:
    def spawn_zone_enemies(self, zone: Any, enemy_db: Any) -> List[Any]:
        enemies = []
        for spawn_def in zone.enemy_spawns:
            type_id = spawn_def.get('type', 'grunt')
            pos = spawn_def.get('pos', [0, 0])
            enemy = enemy_db.create(type_id)
            enemy.rect.x = int(pos[0]) - enemy.rect.w // 2
            enemy.rect.y = int(pos[1]) - enemy.rect.h
            if zone.spawn_points:
                enemy.patrol_waypoints = list(zone.spawn_points)
            enemies.append(enemy)
        return enemies

    def spawn_all_zones(self, zones: List[Any], enemy_db: Any) -> List[Any]:
        all_enemies = []
        for zone in zones:
            all_enemies.extend(self.spawn_zone_enemies(zone, enemy_db))
        return all_enemies
