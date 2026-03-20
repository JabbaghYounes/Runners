Allow players to equip weapon mods (scopes, barrels, grips, etc.) that modify weapon stats.

Depends on: inventory-items, combat-shooting

- Attachment types defined in `data/attachments.json` with stat modifiers (accuracy, range, fire rate, damage)
- Each weapon has a configurable list of attachment slots it supports
- Equipping an attachment updates the weapon's effective stats immediately
- Attachments are `Item` instances with type `attachment` and can be found as loot
- Inventory UI shows attachment slots per weapon when a weapon is selected
- Removing an attachment returns it to the inventory

