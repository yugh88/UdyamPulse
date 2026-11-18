"""Serving layer: monthly account scores kept in the OLTP database (`account_scores`) so portfolio
screens use indexed SQL. Rows are written by the monitoring batch only while consent allows new data,
so an account whose consent was revoked keeps its last known score and nothing newer."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from agents.providers.lake import get_lake
from api.models.db import AccountScore, Application
from core.timeline import month_start


def ensure_partition(db: Session, month_date: date) -> None:
    """PostgreSQL: create the monthly partition if a migration has not already provided it."""
    if db.get_bind().dialect.name != "postgresql":
        return
    nxt = date(month_date.year + (month_date.month == 12), month_date.month % 12 + 1, 1)
    name = f"account_scores_{month_date:%Y_%m}"
    exists = db.execute(text("SELECT to_regclass(:n)"), {"n": name}).scalar()
    if exists is None:
        db.execute(text(f"CREATE TABLE {name} PARTITION OF account_scores FOR VALUES FROM ('{month_date}') TO ('{nxt}')"))


def write_scores(db: Session, app: Application, months: Iterable[int]) -> int:
    """Upsert the account's scores for the given panel months. The caller commits."""
    months = sorted(set(months))
    if not months:
        return 0
    scores = get_lake().scores(months[-1])
    rows = scores[(scores.factory_id == app.factory_id) & scores.month.isin(months)]
    db.query(AccountScore).filter(AccountScore.factory_id == app.factory_id, AccountScore.month.in_(months)).delete(
        synchronize_session=False)
    for r in rows.itertuples():
        first = month_start(int(r.month))
        db.add(AccountScore(factory_id=app.factory_id, month_date=first, month=int(r.month), application_id=app.id,
                            score=int(r.score), band=r.band, pd_12m=float(r.pd_12m)))
    return len(rows)


def recent_scores(db: Session, upto_month: int, window: int = 7) -> dict[str, list[AccountScore]]:
    """Scores for the last `window` months per factory, oldest first, in one indexed query."""
    rows = (db.query(AccountScore)
            .filter(AccountScore.month > upto_month - window, AccountScore.month <= upto_month)
            .order_by(AccountScore.factory_id, AccountScore.month).all())
    out: dict[str, list[AccountScore]] = {}
    for r in rows:
        out.setdefault(r.factory_id, []).append(r)
    return out


def latest_scores(db: Session, factory_ids: Iterable[str]) -> dict[str, list[AccountScore]]:
    """Fallback for accounts with nothing in the recent window (for example, consent revoked long ago)."""
    out: dict[str, list[AccountScore]] = {}
    for fid in factory_ids:
        rows = (db.query(AccountScore).filter(AccountScore.factory_id == fid)
                .order_by(AccountScore.month.desc()).limit(7).all())
        if rows:
            out[fid] = rows[::-1]
    return out
