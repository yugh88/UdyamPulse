"""Fit the synthetic generator's macro parameters to real Indian statistics (Tier B) and write
`data_gen/calibration.yaml`, where every value names its source.

From MoSPI's Index of Industrial Production (base 2011-12, monthly, by NIC division) we derive, per sector:
- `season`: calendar-month index (ratio to a centred 12-month average, Apr 2020 - Mar 2022 excluded);
- `growth`: median year-on-year growth, same exclusion;
- `noise_sd`: monthly irregular component (sd of the log residual);
- `shock`: the depth of the April 2020 fall vs April 2019 and the months until output was back to 95%,
  used as the *shape* of the synthetic panel's macro shock (scaled, see `shock_scale`).

When the IIP file is missing (offline, `make demo`), the generator's documented hand-set values are used and
the YAML records `source: fallback`, which is logged loudly.

    python -m data_gen.calibrate
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from data_gen.generate import SECTORS
from data_real.common import CACHE

OUT = Path(__file__).resolve().parent / "calibration.yaml"
IIP_FILE = CACHE / "iip_monthly.parquet"
BASE_YEAR = "2011-12"
SECTOR_SERIES = {  # UdyamPulse sector → IIP NIC division (2011-12 base)
    "auto_components": "Manufacture of Motor Vehicles, Trailers and Semi-trailers",
    "engineering": "Manufacture of Machinery and Equipment n.e.c.",
    "textiles": "Manufacture of Textiles",
    "ceramics": "Manufacture of Other Non-metallic Mineral Products",
    "food_processing": "Manufacture of Food Products",
}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
EXCLUDE = (pd.Timestamp("2020-04-01"), pd.Timestamp("2022-03-01"))
SHOCK_SCALE = 0.30  # the panel's shock is a demand shock 30% as deep as the 2020 lockdown, not a lockdown
log = logging.getLogger("udyampulse.calibrate")

# Targets with no automatable source: design values, cited honestly.
DEFAULT_TARGETS = {
    "default_rate_overall": {"value": [0.06, 0.09], "source": "design target from docs/DATA_STRATEGY.md: within "
                             "the range of MSME stress rates in RBI Financial Stability Reports; verify against "
                             "the latest report before a pilot"},
    "micro_vs_small_default_ratio": {"value": 1.6, "source": "design: micro units default more often than small "
                                     "units in public MSME credit reports; exact ratio not automated"},
    "micro_share": {"value": 0.6, "source": "design: lending-portfolio mix (Udyam registrations are mostly micro, "
                    "but bank MSME books skew larger); manual Udyam dashboard steps in data_real/README.md"},
}


def _series(df: pd.DataFrame, name: str) -> pd.Series:
    s = df[(df["base_year"] == BASE_YEAR) & (df["sub_category"].str.strip() == name)].copy()
    s["date"] = pd.to_datetime(s["year"].astype(str) + "-" + s["month"].map(lambda m: MONTHS.index(m) + 1).astype(str) + "-01")
    return s.groupby("date")["index"].mean().sort_index().asfreq("MS")


def fit_sector(s: pd.Series) -> dict:
    keep = ~((s.index >= EXCLUDE[0]) & (s.index <= EXCLUDE[1]))
    ma = s.rolling(12, center=True).mean().rolling(2).mean().shift(-1)  # centred 2x12 moving average
    ratio = (s / ma)[keep].dropna()
    season = ratio.groupby(ratio.index.month).mean()
    season = (season / season.mean()).reindex(range(1, 13))
    yoy = (s / s.shift(12) - 1)[keep & ~((s.index >= EXCLUDE[0]) & (s.index <= EXCLUDE[1] + pd.DateOffset(years=1)))]
    resid = np.log(s / (ma * s.index.month.map(season).to_numpy()))[keep].dropna()
    apr19, apr20 = s.get(pd.Timestamp("2019-04-01")), s.get(pd.Timestamp("2020-04-01"))
    depth = float(apr20 / apr19 - 1) if apr19 and apr20 else None
    recovery = None
    for k in range(1, 30):
        d = pd.Timestamp("2020-04-01") + pd.DateOffset(months=k)
        prev = s.get(d - pd.DateOffset(years=1))
        if d in s.index and prev and s[d] / prev >= 0.95:
            recovery = k
            break
    return {
        "season": [round(float(x), 4) for x in season.to_numpy()],
        "growth": round(float(yoy.dropna().median()), 4),
        "noise_sd": round(float(resid.std()), 4),
        "shock": {"depth_apr2020_vs_apr2019": round(depth, 3) if depth is not None else None,
                  "months_to_95pct": recovery},
        "series": None,  # filled by caller
        "observations": int(s.notna().sum()),
        "range": [str(s.dropna().index.min().date()), str(s.dropna().index.max().date())],
    }


def fallback() -> dict:
    return {sector: {"season": cfg["season"], "growth": 0.08, "noise_sd": 0.05,
                     "shock": {"depth_apr2020_vs_apr2019": -0.6, "months_to_95pct": 6},
                     "source": "fallback: generator hand-set values (IIP file not available)"}
            for sector, cfg in SECTORS.items()}


def calibrate(iip_file: Path = IIP_FILE) -> dict:
    meta: dict = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "shock_scale": SHOCK_SCALE,
                  "shock_scale_source": "design: a demand shock 30% as deep as April 2020, shaped like its recovery",
                  "targets": DEFAULT_TARGETS}
    if not iip_file.exists():
        log.warning("Tier B calibration: %s missing; using FALLBACK hand-set ranges. Run `make data-real`.", iip_file)
        return {**meta, "source": "fallback", "sectors": fallback()}
    df = pd.read_parquet(iip_file)
    retrieved = str(df["retrieved_at"].iloc[0]) if "retrieved_at" in df else None
    sectors = {}
    for sector, name in SECTOR_SERIES.items():
        s = _series(df, name)
        if s.notna().sum() < 36:
            log.warning("IIP series %r too short; sector %s uses fallback", name, sector)
            sectors[sector] = fallback()[sector]
            continue
        fit = fit_sector(s)
        fit["series"] = name
        fit["source"] = (f"MoSPI IIP base {BASE_YEAR}, {name}, {fit['range'][0]} to {fit['range'][1]} "
                         f"({fit['observations']} months), retrieved {retrieved}")
        sectors[sector] = fit
    return {**meta, "source": "MoSPI Index of Industrial Production via api.mospi.gov.in",
            "licence": str(df["licence"].iloc[0]) if "licence" in df else None, "sectors": sectors}


def load() -> dict:
    """The committed calibration, or the fallback when the YAML is absent."""
    if OUT.exists():
        return yaml.safe_load(OUT.read_text())
    log.warning("data_gen/calibration.yaml missing; using FALLBACK hand-set ranges")
    return {"source": "fallback", "shock_scale": SHOCK_SCALE, "targets": DEFAULT_TARGETS, "sectors": fallback()}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cal = calibrate()
    header = ("# Generator calibration (Tier B). Written by `python -m data_gen.calibrate`; every value names its "
              "source.\n# Fallback values are used, and logged, when the MoSPI file is not available.\n")
    OUT.write_text(header + yaml.safe_dump(cal, sort_keys=False, allow_unicode=True, width=110))
    print(f"wrote {OUT} (source: {cal['source']})")


if __name__ == "__main__":
    main()
