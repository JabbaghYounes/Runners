# Claude Hive

A drop-in AI swarm toolkit for autonomous development. Copy the `claude-hive/` folder into any project and go from a PRD to implemented features with pull requests.

## Quick Start

```bash
# 1. Copy claude-hive/ into your project
cp -r claude-hive/ /path/to/your-project/claude-hive/

# 2. Configure for your project
vim claude-hive/hive.conf

# 3. Write your PRD
vim claude-hive/prd/prd.md

# 4. Run the full pipeline
claude-hive/scripts/run-product.sh

# Or run the iteration loop (build → retrospective → evolve PRD → repeat)
claude-hive/scripts/iterate.sh --max-iterations 3 --auto-apply
```

## How It Works

Claude Hive orchestrates specialized AI agents through a staged pipeline:

```
PRD
 → Product Manager (extract features)
 → Design Phase (architecture, DB, API, UX specs)
 → Per-Feature Swarms
    → Architect → Implementation (parallel) → Tester → Debugger (retry)
    → Polish (optional, N passes) → Review (optional) → PR
 → Git PR per feature
 → Retrospective (optional) → PRD Evolution (optional)
```

The design phase runs once for the whole product. Each feature then gets its own branch (`ai-feature-<timestamp>`) and pull request.

With `iterate.sh`, the pipeline loops automatically — building features, analyzing the output, evolving the PRD, and running again with `--incremental` until the retrospective finds nothing left to improve.

## Structure

```
claude-hive/
  hive.conf          # Project-specific settings (test cmd, base branch, etc.)
  agents/             # Agent prompt definitions (one .md per role)
  pipelines/          # Pipeline stage documentation (YAML)
  prd/
    prd.md            # Your product requirements (edit this)
    features/         # Auto-generated feature files (one per feature)
    specs/            # Auto-generated specs (design + per-feature architecture/plan)
    status/           # Per-feature stage-level progress (resume support)
    status.json       # Summary status (backward compatible)
    logs/             # Agent output logs and cost tracking (per run)
  scripts/
    lib.sh            # Shared functions (logging, rate-limit, status tracking)
    run-product.sh    # Full pipeline: PRD → design → features → PRs
    swarm.sh          # Run a single feature swarm
    prd-extract.sh    # Extract features from PRD
    prd-swarm.sh      # Run swarm for all extracted features (sequential or parallel)
    cost-report.sh    # Generate token usage and cost report from logs
    integration-test.sh # Cross-feature integration test pass
    iterate.sh        # Automated iteration loop (build → retrospective → evolve → repeat)
    tui.sh            # Live ANSI progress dashboard
    run-product-tui.sh # Full pipeline with integrated TUI dashboard
```

## Configuration

Edit `claude-hive/hive.conf` to match your project:

```bash
TEST_CMD="npm test"           # Command to run tests
BASE_BRANCH="main"            # Base branch for feature branches
MAX_RETRIES=3                 # Max debug retries before aborting
POLISH_PASSES=0               # Code improvement passes per feature (0 = disabled)
ENABLE_REVIEW=false           # PR review agent before commit
ENABLE_RETROSPECTIVE=false    # Post-pipeline analysis
ENABLE_PRD_EVOLUTION=false    # Refine PRD from retrospective
ENABLE_INTEGRATION_TEST=false # Cross-feature integration tests
```

## Prerequisites

- [Claude Code](https://claude.ai/code) CLI (`claude`) — **Max subscription recommended**
- [GitHub CLI](https://cli.github.com/) (`gh`) — for automatic PR creation
- Git
