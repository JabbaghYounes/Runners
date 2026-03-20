Show a post-round summary after extraction or round-end, then return to the main menu or queue again.

Depends on: extraction-mechanics, xp-leveling, currency

- Displays: list of extracted items with rarity and value, total money earned, XP earned, new level (if leveled up)
- If round ended without extraction, shows a "FAILED TO EXTRACT" state with loot lost
- "Queue Again" button starts a new round (replace_all to GameScene)
- "Home Base" button navigates to HomeBaseScene
- "Main Menu" button navigates to MainMenu
- Save is triggered automatically when the post-round screen is entered

