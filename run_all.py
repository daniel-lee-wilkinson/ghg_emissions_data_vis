"""
run_all.py
----------
Single entry point for the full analysis pipeline.

Usage
-----
    python run_all.py                        # run all three analyses
    python run_all.py --only ag              # run just agricultural analysis
    python run_all.py --only emissions sectors  # run two of the three
    python run_all.py --cache-only           # pre-fetch and cache network data only

Analyses
--------
    ag        : Agricultural production indices  (ag_data.py)
    emissions : GHG emissions and intensity      (clean_dat.py)
    sectors   : Sector-level breakdown           (sectors.py)
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # non-interactive backend, no display needed


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Individual steps — each is a plain function so failures are isolated
# ---------------------------------------------------------------------------

def run_ag() -> None:
    log.info("=== Agricultural production indices ===")
    import ag_data  # noqa: F401  (module-level code runs on import)


def run_emissions() -> None:
    log.info("=== GHG emissions and intensity ===")
    import clean_dat  # noqa: F401


def run_sectors() -> None:
    log.info("=== Sector-level breakdown ===")
    import sectors  # noqa: F401


def run_cache_only() -> None:
    """Pre-fetch and cache network data without running any analysis."""
    log.info("=== Pre-fetching network data ===")
    from config import GDP_DATE_RANGE, GDP_INDICATOR
    from loaders import M49_CACHE_PATH, fetch_world_bank_gdp, load_m49_lookup

    UNSD_M49_URL = "https://unstats.un.org/unsd/methodology/m49/overview/"

    if M49_CACHE_PATH.exists():
        log.info("M49 cache already exists at %s — skipping", M49_CACHE_PATH)
    else:
        load_m49_lookup(UNSD_M49_URL)

    from loaders import _gdp_cache_path
    gdp_cache = _gdp_cache_path(GDP_INDICATOR, GDP_DATE_RANGE)
    if gdp_cache.exists():
        log.info("GDP cache already exists at %s — skipping", gdp_cache)
    else:
        fetch_world_bank_gdp(GDP_INDICATOR, GDP_DATE_RANGE)


# ---------------------------------------------------------------------------
# Registry — add new analyses here
# ---------------------------------------------------------------------------

STEPS: dict[str, callable] = {
    "ag":        run_ag,
    "emissions": run_emissions,
    "sectors":   run_sectors,
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the European GHG + agriculture analysis pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--only",
        nargs="+",
        choices=list(STEPS.keys()),
        metavar="ANALYSIS",
        help=f"Run only the specified analyses. Choices: {', '.join(STEPS)}",
    )
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Pre-fetch and cache network data without running analyses.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.cache_only:
        run_cache_only()
        return

    to_run = args.only if args.only else list(STEPS.keys())

    log.info("Pipeline starting — steps: %s", ", ".join(to_run))
    pipeline_start = time.perf_counter()

    failed = []
    for name in to_run:
        step_start = time.perf_counter()
        try:
            STEPS[name]()
            elapsed = time.perf_counter() - step_start
            log.info("'%s' completed in %.1fs", name, elapsed)
        except Exception:
            log.exception("'%s' failed — continuing with remaining steps", name)
            failed.append(name)

    total = time.perf_counter() - pipeline_start
    log.info("Pipeline finished in %.1fs", total)

    if failed:
        log.error("The following steps failed: %s", ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()