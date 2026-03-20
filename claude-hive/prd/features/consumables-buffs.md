Implement healing packs and buff consumables that can be used from the quick-slot bar.

Depends on: inventory-items, player-movement

- Consumable types (healing pack, speed buff, damage buff) defined in `data/items.json`
- Using a consumable from a quick slot emits `"consumable_used"` on the EventBus
- `BuffSystem` applies timed stat modifiers (duration, magnitude) and removes them on expiry
- Healing packs restore a configurable HP amount; healing cannot exceed max HP
- Active buffs are visible as icons in the HUD with a countdown timer
- Consumables are removed from inventory on use

