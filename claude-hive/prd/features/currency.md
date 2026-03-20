Track in-game currency earned from extracted loot value and challenge rewards.

Depends on: loot-system, challenge-system, extraction-mechanics

- `CurrencySystem` subscribes to `"player_extracted"` and sums monetary value of all extracted items
- Challenge rewards (money) are added via `"challenge_completed"` event
- Currency balance persists across rounds in save data
- Currency is displayed on the post-round screen and in the home base scene
- Currency cannot go below zero
- Spending currency (home base upgrades) emits `"currency_spent"` and deducts the amount

