Allow players to equip armor items that reduce incoming damage.

Depends on: inventory-items, combat-shooting

- Armor items have an `armor_rating` field in the item definition
- Player entity tracks `equipped_armor` and exposes an `armor` property to `CombatSystem`
- Damage formula already accounts for armor: `effective = max(1, raw − armor)`
- Only one armor piece can be equipped at a time; equipping a new piece unequips the old one
- Armor durability (optional MVP scope: armor has no durability, just a flat rating)
- Equipped armor is visible in the inventory UI in a dedicated armor slot

