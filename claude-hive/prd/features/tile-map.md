Render a single tile-based map using 32×32 pixel tiles with a scrolling camera and named map zones.

Depends on: core-infrastructure

- Map is defined in a data file (JSON or CSV) and loaded without code changes for new layouts
- Camera follows the player and clamps to map boundaries
- Tiles render on `LAYER_TILES` (Z = 0)
- At least one extraction zone and multiple named challenge zones are defined on the map
- Solid tiles block physics movement; open tiles allow free passage
- Mini-map overlay accurately reflects the tile layout

