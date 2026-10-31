"""SQLite storage for prices and forecast runs.

All times are stored as UTC epoch seconds and all prices as EUR/MWh without VAT.
"""
import sqlite3
from contextlib import closing

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    ts INTEGER NOT NULL,            -- interval start, UTC epoch seconds
    resolution INTEGER NOT NULL,    -- interval length in minutes (15 or 60)
    price REAL NOT NULL,            -- EUR/MWh, VAT 0
    source TEXT NOT NULL,
    fetched_at INTEGER NOT NULL,
    PRIMARY KEY (ts, resolution)
);
CREATE TABLE IF NOT EXISTS forecast_runs (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    issued_at INTEGER NOT NULL,     -- first time this run was seen, UTC epoch seconds
    content_hash TEXT NOT NULL,
    UNIQUE (source, content_hash)
);
CREATE TABLE IF NOT EXISTS forecast_values (
    run_id INTEGER NOT NULL REFERENCES forecast_runs(id) ON DELETE CASCADE,
    ts INTEGER NOT NULL,
    resolution INTEGER NOT NULL,
    price REAL NOT NULL,            -- EUR/MWh, VAT 0
    PRIMARY KEY (run_id, ts)
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE INDEX IF NOT EXISTS forecast_runs_issued ON forecast_runs (source, issued_at);
"""

# Sources in priority order: a higher priority source overwrites a lower one.
SOURCE_PRIORITY = {"spot-hinta.fi": 1, "entsoe": 2}


class Database:
    def __init__(self, path):
        self.con = sqlite3.connect(path)
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(SCHEMA)

    def close(self):
        self.con.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- prices --
    def store_prices(self, rows, source, fetched_at):
        """Store (ts, resolution, price) rows. Returns the number of rows written.

        Existing rows from a source with the same or higher priority are kept.
        """
        prio = SOURCE_PRIORITY.get(source, 0)
        written = 0
        with self.con:
            for ts, resolution, price in rows:
                cur = self.con.execute("SELECT source FROM prices WHERE ts = ? AND resolution = ?",
                                       (ts, resolution))
                old = cur.fetchone()
                if old is not None and SOURCE_PRIORITY.get(old[0], 0) > prio:
                    continue
                if old is not None and old[0] == source:
                    self.con.execute("UPDATE prices SET price = ?, fetched_at = ? WHERE ts = ? AND resolution = ?",
                                     (price, fetched_at, ts, resolution))
                else:
                    self.con.execute("INSERT OR REPLACE INTO prices VALUES (?, ?, ?, ?, ?)",
                                     (ts, resolution, price, source, fetched_at))
                written += 1
        return written

    def prices_end(self, source=None):
        """End of the last stored price interval (epoch seconds), or None."""
        sql = "SELECT MAX(ts + resolution * 60) FROM prices"
        args = ()
        if source is not None:
            sql += " WHERE source = ?"
            args = (source,)
        return self.con.execute(sql, args).fetchone()[0]

    def prices(self, start, end):
        """(ts, resolution, price) rows with start <= ts < end."""
        cur = self.con.execute("SELECT ts, resolution, price FROM prices WHERE ts >= ? AND ts < ? "
                               "ORDER BY resolution, ts", (start, end))
        return cur.fetchall()

    def sources(self, start, end):
        cur = self.con.execute("SELECT DISTINCT source FROM prices WHERE ts >= ? AND ts < ?", (start, end))
        return sorted(r[0] for r in cur)

    # -- forecasts --
    def store_forecast_run(self, source, issued_at, content_hash, rows):
        """Store a forecast run unless identical content is already stored.

        Returns the new run id, or None for a duplicate.
        """
        with self.con:
            cur = self.con.execute("INSERT OR IGNORE INTO forecast_runs (source, issued_at, content_hash) "
                                   "VALUES (?, ?, ?)", (source, issued_at, content_hash))
            if cur.rowcount == 0:
                return None
            run_id = cur.lastrowid
            self.con.executemany("INSERT OR REPLACE INTO forecast_values VALUES (?, ?, ?, ?)",
                                 [(run_id, ts, res, price) for ts, res, price in rows])
        return run_id

    def forecast_runs(self, source, since=None, until=None):
        """(id, issued_at) of the runs of a source, oldest first."""
        sql = "SELECT id, issued_at FROM forecast_runs WHERE source = ?"
        args = [source]
        if since is not None:
            sql += " AND issued_at >= ?"
            args.append(since)
        if until is not None:
            sql += " AND issued_at < ?"
            args.append(until)
        return self.con.execute(sql + " ORDER BY issued_at", args).fetchall()

    def forecast_values(self, run_id, start=None, end=None):
        """(ts, resolution, price) of a run."""
        sql = "SELECT ts, resolution, price FROM forecast_values WHERE run_id = ?"
        args = [run_id]
        if start is not None:
            sql += " AND ts >= ?"
            args.append(start)
        if end is not None:
            sql += " AND ts < ?"
            args.append(end)
        return self.con.execute(sql + " ORDER BY ts", args).fetchall()

    # -- meta --
    def get_meta(self, key, default=None):
        with closing(self.con.execute("SELECT value FROM meta WHERE key = ?", (key,))) as cur:
            row = cur.fetchone()
        return default if row is None else row[0]

    def set_meta(self, key, value):
        with self.con:
            self.con.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))
