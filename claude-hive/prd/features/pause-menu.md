Implement an in-game pause menu overlay that freezes the game scene beneath it.

Depends on: core-infrastructure

- Pause menu is pushed onto the scene stack (game scene below is frozen)
- Options: Resume (pop), Restart Round (replace_all + new GameScene), Exit to Menu (replace_all + MainMenu)
- Round timer pauses while pause menu is open
- AI and physics systems halt updates while paused
- Pause triggered by Escape key during gameplay
- Settings accessible from pause menu via `push`

