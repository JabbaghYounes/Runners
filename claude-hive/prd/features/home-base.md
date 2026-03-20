Implement the Home Base hub scene with purchasable upgrades using earned currency.

Depends on: currency, skill-tree

- `HomeBaseScene` is accessible from the main menu and post-round screen
- Upgrades are defined in `data/home_base.json` with cost, prerequisite upgrades, and effect
- Purchasing an upgrade deducts currency via `"currency_spent"` and unlocks the upgrade
- Upgrade effects apply globally (e.g. increased starting inventory slots, bonus XP multiplier)
- Home base UI renders upgrade nodes with locked/available/purchased states
- Upgrades and currency balance are saved after every home-base transaction

