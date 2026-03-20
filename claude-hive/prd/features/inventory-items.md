Implement the item model, 24-slot inventory with 4 quick slots, and the item database.

Depends on: core-infrastructure

- `Item` model has: id, name, rarity, type (weapon / armor / consumable / attachment), weight, and monetary value
- `Inventory` manages 24 general slots + 4 quick slots; enforces max-weight or slot-count rules
- `ItemDatabase` loads all items from `data/items.json`; no code change needed to add new items
- E key while overlapping a `LootItem` entity moves it into inventory (emits `"item_picked_up"`)
- Inventory screen (Tab) renders a grid of occupied slots with item icons and tooltip on hover
- Inventory persists correctly through push/pop scene transitions (overlay semantics)

