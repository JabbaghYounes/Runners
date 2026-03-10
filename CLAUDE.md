# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Runners — a futuristic PvPvE extraction shooter built with Python 3.10+ and Pygame 2.x. Players explore a hostile map, complete challenges, fight humanoid robots and other players, collect loot, and extract within a 15-minute round to progress through skill trees and home base upgrades.

## Commands

```bash
# Run the game
python main.py

# Run tests
pytest

# Run a single test file
pytest tests/test_player.py

# Install dependencies
pip install -r requirements.txt
```

## Architecture

The game uses a component-based structure under `src/`:

- **main.py** — Entry point, game loop, Pygame init (target 60 FPS at 1280x720)
- **player.py** — Player character: movement (WASD), crouch, jump, sprint, slide, shooting, inventory interaction
- **enemy.py** — Humanoid robot AI enemies (PvE)
- **map.py** — Single map with dynamic challenge zones, extraction points, tile-based environment
- **inventory.py** — Loot collection, weapon attachments, armor, consumables, extraction value tracking

Assets live in `assets/` (sprites, sound effects, zone-based music loops).

## Game Loop

Spawn → explore map zones → complete vendor challenges → fight PvE robots & PvP players → collect loot → extract before 15-min timer → earn XP/money → upgrade skill tree & home base → queue next round.

## Ricky AI Framework

The `ricky/` directory is a drop-in AI swarm toolkit that drives development from PRD to PRs. It orchestrates specialized agents through a staged pipeline:

```
PRD → Product Manager (extract features) → Design Phase → Per-Feature Swarms → Git PR per feature
```

### Key commands

```bash
# Full pipeline: extract features from PRD → design → implement → test → PR
ricky/scripts/run-product.sh

# Single feature swarm (design → architect → build → test → debug → PR)
ricky/scripts/swarm.sh "<task description>"

# Single feature swarm, skipping design phase (used internally by run-product.sh)
ricky/scripts/swarm.sh --skip-design "<task description>"

# Extract features from PRD into individual files
ricky/scripts/prd-extract.sh

# Run swarm for each extracted feature
ricky/scripts/prd-swarm.sh
```

### Configuration

`ricky/ricky.conf` controls project-specific settings:
- `TEST_CMD="pytest"` — test runner command
- `BASE_BRANCH="main"` — branch for feature branches
- `MAX_RETRIES=3` — debug retry attempts before aborting
- `DESIGN_AGENTS="system-architect ux-designer"` — design agents to run
- `IMPL_AGENTS="backend"` — implementation agents (backend-only for this project)

Agents read this file and `ricky/prd/specs/` for architectural context. The PRD lives at `ricky/prd/prd.md`, extracted features go to `ricky/prd/features/`, and `ricky/prd/status.json` tracks progress (pending → in-progress → complete/failed). Re-running `prd-swarm.sh` resumes from where it left off, skipping completed features.

### Pipeline stages (per feature)

Each feature swarm runs these stages in order:
1. **Design** (optional, `--skip-design` skips) — system-architect, ux-designer generate specs
2. **Architect** — feature-specific architecture → `feature-architecture.md`
3. **Plan** — ordered task breakdown → `feature-plan.md`
4. **Implement** — backend agent writes code (parallel-safe if multiple agents)
5. **Test** — tester agent writes and runs tests via `$TEST_CMD`
6. **Debug** — retry loop (up to `MAX_RETRIES`) with debugger agent on test failures
7. **Commit** — versioncontroller agent creates git commit + PR

### Agent conventions

- Agents must not stage `ricky/*` files in commits
- Implementation agents must not modify files outside their domain (e.g., backend doesn't touch frontend)
- Feature files in `ricky/prd/features/` include dependency info (e.g., `Depends on: tilemap-rendering, player-shooting`)

### Prerequisites for Ricky

- Claude Code CLI (`claude`)
- GitHub CLI (`gh`) for automatic PR creation

## Conventions

- Python 3.10+, follow PEP 8
- Pygame 2.x for all rendering, input, and audio
- Performance-sensitive: maintain 60 FPS — optimize sprite rendering and collision detection
- Save/load system for inventory, skill tree, and home base state
