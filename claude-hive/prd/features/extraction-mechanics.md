Implement extraction zones that players must reach to successfully keep their loot.

Depends on: tile-map, round-timer, inventory-items

- `ExtractionZone` entities are placed in the map data file and rendered as a visible highlighted area
- `ExtractionSystem` detects player overlap with an extraction zone and starts a 3-second channel time
- Successful extraction emits `"player_extracted"` with the player's current inventory snapshot
- If the player leaves the zone before channeling completes, the extraction is cancelled
- On `"round_end"` without extraction, inventory loot gained during the round is lost
- Post-round screen receives the extracted inventory to compute earned money

