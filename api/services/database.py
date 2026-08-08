"""
SQLite / PostgreSQL dual-backend database manager.

If DATABASE_URL is not set, uses SQLite (existing behaviour).
If DATABASE_URL is set, connects to PostgreSQL via asyncpg + psycopg2.
Placeholder conversion (? -> $1, $2, $3) is handled transparently.
"""
import os
import sqlite3
import aiosqlite
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def utc_now_naive() -> datetime:
    """Return the current UTC time as a timezone-naive datetime for PostgreSQL TIMESTAMP columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ---------------------------------------------------------------------------
# SQLite mode  (unchanged behaviour)
# ---------------------------------------------------------------------------
if not DATABASE_URL:

    DB_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "tender_engine.db",
    )

    def _get_connection() -> sqlite3.Connection:
        """Get a synchronous SQLite connection for schema setup."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_db():
        """
        Create tables if they don't exist.
        Called once at startup.
        """
        conn = _get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                    email                   TEXT UNIQUE NOT NULL,
                    hashed_password         TEXT NOT NULL,
                    full_name               TEXT DEFAULT '',
                    company_name            TEXT DEFAULT '',
                    role                    TEXT DEFAULT 'customer',
                    plan                    TEXT DEFAULT 'free',
                    is_active               INTEGER DEFAULT 1,
                    email_verified          INTEGER DEFAULT 1,
                    failed_login_attempts   INTEGER DEFAULT 0,
                    locked_until            TIMESTAMP,
                    last_login_at           TIMESTAMP,
                    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER NOT NULL REFERENCES users(id),
                    key        TEXT UNIQUE NOT NULL,
                    name       TEXT DEFAULT 'Default',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            for statement in [
                "ALTER TABLE users ADD COLUMN company_name TEXT DEFAULT ''",
                "ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'customer'",
                "ALTER TABLE users ADD COLUMN email_verified INTEGER DEFAULT 1",
                "ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0",
                "ALTER TABLE users ADD COLUMN locked_until TIMESTAMP",
                "ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP",
            ]:
                try:
                    cursor.execute(statement)
                except sqlite3.OperationalError:
                    pass

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    session_id          TEXT UNIQUE NOT NULL,
                    refresh_token_hash  TEXT NOT NULL,
                    user_agent          TEXT DEFAULT '',
                    ip_address          TEXT DEFAULT '',
                    remember_me         INTEGER DEFAULT 0,
                    impersonated_by     INTEGER,
                    expires_at          TIMESTAMP NOT NULL,
                    last_active_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    revoked_at          TIMESTAMP,
                    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_session_id ON auth_sessions(session_id)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS auth_audit_log (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id             INTEGER,
                    actor_user_id       INTEGER,
                    action              TEXT NOT NULL,
                    session_id          TEXT,
                    ip_address          TEXT DEFAULT '',
                    user_agent          TEXT DEFAULT '',
                    details_json        TEXT,
                    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_audit_user_id ON auth_audit_log(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_audit_actor_user_id ON auth_audit_log(actor_user_id)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processing_jobs (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id          TEXT UNIQUE NOT NULL,
                    user_id         TEXT,
                    filename        TEXT,
                    original_name   TEXT,
                    status          TEXT DEFAULT 'queued',
                    progress        TEXT DEFAULT 'pending',
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    result_json     TEXT,
                    error_message   TEXT
                )
            """)

            try:
                cursor.execute("ALTER TABLE processing_jobs ADD COLUMN retry_count INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE processing_jobs ADD COLUMN retry_data_json TEXT")
            except sqlite3.OperationalError:
                pass

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS marketing_leads (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    name            TEXT NOT NULL,
                    email           TEXT UNIQUE NOT NULL,
                    company         TEXT DEFAULT '',
                    role            TEXT DEFAULT '',
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.executescript("""
                CREATE TABLE IF NOT EXISTS tenders (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id            TEXT UNIQUE NOT NULL,
                    user_id           TEXT,
                    filename          TEXT,
                    original_filename TEXT,
                    file_hash         TEXT DEFAULT '',
                    mime_type         TEXT DEFAULT '',
                    file_size         INTEGER DEFAULT 0,
                    status            TEXT DEFAULT 'queued',
                    pipeline_version  TEXT DEFAULT 'v1',
                    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at      TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_tenders_job_id ON tenders(job_id);
                CREATE INDEX IF NOT EXISTS idx_tenders_user_id ON tenders(user_id);
                CREATE INDEX IF NOT EXISTS idx_tenders_status ON tenders(status);
                CREATE INDEX IF NOT EXISTS idx_tenders_file_hash ON tenders(file_hash);

                CREATE TABLE IF NOT EXISTS tender_results (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    tender_id         TEXT NOT NULL,
                    raw_text          TEXT,
                    sector            TEXT,
                    sector_confidence TEXT,
                    duration_months   INTEGER,
                    locations_json    TEXT,
                    workforce_json    TEXT,
                    schedule_json     TEXT,
                    boq_json          TEXT,
                    boq_confidence    TEXT,
                    pricing_json      TEXT,
                    pricing_mode      TEXT DEFAULT 'estimated',
                    warnings_json     TEXT,
                    evidence_json     TEXT,
                    extraction_method TEXT,
                    pipeline_version  TEXT DEFAULT 'v1',
                    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tender_id) REFERENCES tenders(job_id)
                );
                CREATE INDEX IF NOT EXISTS idx_tender_results_tender_id ON tender_results(tender_id);

                CREATE TABLE IF NOT EXISTS processing_events (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    tender_id   TEXT NOT NULL,
                    stage       TEXT NOT NULL,
                    status      TEXT DEFAULT 'pending',
                    details     TEXT,
                    duration_ms INTEGER,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tender_id) REFERENCES tenders(job_id)
                );
                CREATE INDEX IF NOT EXISTS idx_processing_events_tender_id ON processing_events(tender_id);
                CREATE INDEX IF NOT EXISTS idx_processing_events_stage ON processing_events(stage);
            """)

            for col in [
                "win_probability_index REAL",
                "win_probability_explanation TEXT",
                "critical_traps_json TEXT",
                "compliance_gaps_json TEXT",
                "detected_currency_json TEXT",
                "evidence_json TEXT",
            ]:
                try:
                    cursor.execute(f"ALTER TABLE tender_results ADD COLUMN {col}")
                except sqlite3.OperationalError:
                    pass

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    tender_id       TEXT NOT NULL,
                    stage           TEXT NOT NULL,
                    status          TEXT NOT NULL DEFAULT 'pending',
                    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    duration_ms     INTEGER,
                    confidence      TEXT,
                    source_module   TEXT,
                    warnings        TEXT,
                    errors          TEXT,
                    details         TEXT,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tender_id) REFERENCES tenders(job_id)
                )
            """)
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_tender_id ON audit_log(tender_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_stage ON audit_log(stage)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_status ON audit_log(status)")
            except sqlite3.OperationalError:
                pass

            conn.commit()
            from .analytics_service import init_analytics_schema_sync
            init_analytics_schema_sync()
            logger.info("[DB] SQLite database initialized at %s", DB_PATH)
        except Exception as e:
            logger.error("[DB] Failed to initialize database: %s", e)
            raise
        finally:
            conn.close()

    async def get_db() -> aiosqlite.Connection:
        """Return an async SQLite connection for use in route handlers."""
        db = await aiosqlite.connect(DB_PATH)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        return db

    async def close_db(db: aiosqlite.Connection):
        """Safely close an async database connection."""
        await db.close()

    # -- Synchronous helpers for middleware compatibility --

    def get_user_by_email_sync(email: str) -> Optional[dict]:
        """Lookup user by email (synchronous, used in middleware)."""
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def get_user_by_id_sync(user_id: int) -> Optional[dict]:
        """Lookup user by ID (synchronous)."""
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def get_api_key_sync(api_key: str) -> Optional[dict]:
        """Lookup an API key and return associated user data."""
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.*, ak.key as api_key
                FROM api_keys ak
                JOIN users u ON u.id = ak.user_id
                WHERE ak.key = ?
            """, (api_key,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

# ---------------------------------------------------------------------------
# PostgreSQL mode  (transparent wrapper)
# ---------------------------------------------------------------------------
else:
    import asyncpg
    import psycopg2
    import psycopg2.extras

    DB_PATH = None  # not used in PG mode

    _PG_DSN = DATABASE_URL
    _PG_POOL = None

    # ------------------------------------------------------------------ #
    #  Placeholder converter:  ?  ->  $1 $2 $3 ...
    # ------------------------------------------------------------------ #
    def _convert_placeholders(sql: str) -> str:
        """Replace '?' placeholders with PostgreSQL $1, $2, ... style."""
        count = 0
        result = []
        for ch in sql:
            if ch == '?':
                count += 1
                result.append(f'${count}')
            else:
                result.append(ch)
        return ''.join(result)

    # ------------------------------------------------------------------ #
    #  Async cursor wrapper  (used by get_db / close_db)
    # ------------------------------------------------------------------ #
    class _AsyncCursor:
        """Emulates aiosqlite cursor over asyncpg results."""

        __slots__ = ('_conn', '_sql', '_args', '_rows', '_idx', '_lastrowid')

        def __init__(self, conn, sql: str, args):
            self._conn = conn
            self._sql = sql
            self._args = args if args is not None else ()
            self._rows = None
            self._idx = 0
            self._lastrowid = None

        async def _run(self):
            if self._rows is not None:
                return
            pg_sql = _convert_placeholders(self._sql)
            stripped = pg_sql.strip().upper()
            is_insert = stripped.startswith("INSERT")

            if is_insert:
                pg_sql += " RETURNING id"

                print("\n==========================")
                print("POSTGRES SQL:")
                print(pg_sql)
                print("PARAMETERS:")
                print(self._args)
                print("==========================\n")

                record = await self._conn.fetchrow(pg_sql, *self._args)
                self._lastrowid = record["id"] if record else None
                self._rows = [dict(record)] if record else []
            else:
                records = await self._conn.fetch(pg_sql, *self._args)
                self._rows = [dict(r) for r in records]

        @property
        def lastrowid(self):
            return self._lastrowid

        async def fetchone(self):
            await self._run()
            if self._idx < len(self._rows):
                row = self._rows[self._idx]
                self._idx += 1
                return row
            return None

        async def fetchall(self):
            await self._run()
            return self._rows

    class _AsyncConnection:
        """Emulates aiosqlite.Connection over asyncpg."""

        def __init__(self, conn):
            self._conn = conn
            self.row_factory = None  # accepted but ignored

        async def execute(self, sql: str, *args):
            params = args[0] if args else ()
            if isinstance(params, (list, tuple)):
                params = tuple(params)
            else:
                params = (params,) if params is not None else ()
            cursor = _AsyncCursor(self._conn, sql, params)
            await cursor._run()
            return cursor

        async def commit(self):
            await self._conn.execute("COMMIT")

        async def close(self):
            await self._conn.close()

    # ------------------------------------------------------------------ #
    #  Sync cursor wrapper  (used by _get_connection + sync helpers)
    # ------------------------------------------------------------------ #
    class _SyncCursor:
        """Emulates sqlite3.Cursor over psycopg2."""

        __slots__ = ('_cursor', '_conn', '_lastrowid')

        def __init__(self, cursor, conn):
            self._cursor = cursor
            self._conn = conn
            self._lastrowid = None

        def execute(self, sql: str, params=None):
            pg_sql = _convert_placeholders(sql)
            stripped = pg_sql.strip().upper()
            is_insert = stripped.startswith("INSERT")

            if is_insert:
                pg_sql += " RETURNING id"
                self._cursor.execute(pg_sql, params or ())
                row = self._cursor.fetchone()
                self._lastrowid = row[0] if row else None
            else:
                self._cursor.execute(pg_sql, params or ())
            return self

        def executescript(self, script: str):
            """Split multi-statement script and run each statement."""
            statements = [s.strip() for s in script.split(";") if s.strip()]
            for stmt in statements:
                self.execute(stmt)

        def fetchone(self):
            row = self._cursor.fetchone()
            if row is None:
                return None
            return dict(row) if hasattr(row, 'keys') else row

        def fetchall(self):
            rows = self._cursor.fetchall()
            if not rows:
                return []
            if hasattr(rows[0], 'keys'):
                return [dict(r) for r in rows]
            return rows

        @property
        def lastrowid(self):
            return self._lastrowid

    class _SyncConnection:
        """Emulates sqlite3.Connection over psycopg2."""

        def __init__(self, dsn: str):
            self._conn = psycopg2.connect(dsn)
            self._conn.autocommit = False

        def cursor(self):
            pg_cursor = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            return _SyncCursor(pg_cursor, self._conn)

        def commit(self):
            self._conn.commit()

        def close(self):
            self._conn.close()

    # ------------------------------------------------------------------ #
    #  Public API  (identical signatures to SQLite mode)
    # ------------------------------------------------------------------ #

    def _get_connection() -> _SyncConnection:
        """Get a synchronous PostgreSQL connection wrapper."""
        return _SyncConnection(_PG_DSN)

    # -- Pool initialisation for async access -- #
    async def _get_pool():
        global _PG_POOL
        if _PG_POOL is None:
            _PG_POOL = await asyncpg.create_pool(_PG_DSN, min_size=1, max_size=10)
        return _PG_POOL

    # -- PostgreSQL DDL (equivalent schema, no AUTOINCREMENT) -- #
    _PG_SCHEMA = """
        CREATE TABLE IF NOT EXISTS users (
            id                      SERIAL PRIMARY KEY,
            email                   TEXT UNIQUE NOT NULL,
            hashed_password         TEXT NOT NULL,
            full_name               TEXT DEFAULT '',
            company_name            TEXT DEFAULT '',
            role                    TEXT DEFAULT 'customer',
            plan                    TEXT DEFAULT 'free',
            is_active               INTEGER DEFAULT 1,
            email_verified          INTEGER DEFAULT 1,
            failed_login_attempts   INTEGER DEFAULT 0,
            locked_until            TIMESTAMP,
            last_login_at           TIMESTAMP,
            created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS api_keys (
            id         SERIAL PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            key        TEXT UNIQUE NOT NULL,
            name       TEXT DEFAULT 'Default',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS auth_sessions (
            id                  SERIAL PRIMARY KEY,
            user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            session_id          TEXT UNIQUE NOT NULL,
            refresh_token_hash  TEXT NOT NULL,
            user_agent          TEXT DEFAULT '',
            ip_address          TEXT DEFAULT '',
            remember_me         INTEGER DEFAULT 0,
            impersonated_by     INTEGER,
            expires_at          TIMESTAMP NOT NULL,
            last_active_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            revoked_at          TIMESTAMP,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_auth_sessions_session_id ON auth_sessions(session_id);

        CREATE TABLE IF NOT EXISTS auth_audit_log (
            id                  SERIAL PRIMARY KEY,
            user_id             INTEGER,
            actor_user_id       INTEGER,
            action              TEXT NOT NULL,
            session_id          TEXT,
            ip_address          TEXT DEFAULT '',
            user_agent          TEXT DEFAULT '',
            details_json        TEXT,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_auth_audit_user_id ON auth_audit_log(user_id);
        CREATE INDEX IF NOT EXISTS idx_auth_audit_actor_user_id ON auth_audit_log(actor_user_id);

        CREATE TABLE IF NOT EXISTS processing_jobs (
            id              SERIAL PRIMARY KEY,
            job_id          TEXT UNIQUE NOT NULL,
            user_id         TEXT,
            filename        TEXT,
            original_name   TEXT,
            status          TEXT DEFAULT 'queued',
            progress        TEXT DEFAULT 'pending',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            result_json     TEXT,
            error_message   TEXT,
            retry_count     INTEGER DEFAULT 0,
            retry_data_json TEXT
        );

        CREATE TABLE IF NOT EXISTS marketing_leads (
            id              SERIAL PRIMARY KEY,
            name            TEXT NOT NULL,
            email           TEXT UNIQUE NOT NULL,
            company         TEXT DEFAULT '',
            role            TEXT DEFAULT '',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tenders (
            id                SERIAL PRIMARY KEY,
            job_id            TEXT UNIQUE NOT NULL,
            user_id           TEXT,
            filename          TEXT,
            original_filename TEXT,
            file_hash         TEXT DEFAULT '',
            mime_type         TEXT DEFAULT '',
            file_size         INTEGER DEFAULT 0,
            status            TEXT DEFAULT 'queued',
            pipeline_version  TEXT DEFAULT 'v1',
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at      TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_tenders_job_id ON tenders(job_id);
        CREATE INDEX IF NOT EXISTS idx_tenders_user_id ON tenders(user_id);
        CREATE INDEX IF NOT EXISTS idx_tenders_status ON tenders(status);
        CREATE INDEX IF NOT EXISTS idx_tenders_file_hash ON tenders(file_hash);

        CREATE TABLE IF NOT EXISTS tender_results (
            id                        SERIAL PRIMARY KEY,
            tender_id                 TEXT NOT NULL,
            raw_text                  TEXT,
            sector                    TEXT,
            sector_confidence         TEXT,
            duration_months           INTEGER,
            locations_json            TEXT,
            workforce_json            TEXT,
            schedule_json             TEXT,
            boq_json                  TEXT,
            boq_confidence            TEXT,
            pricing_json              TEXT,
            pricing_mode              TEXT DEFAULT 'estimated',
            warnings_json             TEXT,
            evidence_json             TEXT,
            extraction_method         TEXT,
            pipeline_version          TEXT DEFAULT 'v1',
            win_probability_index     REAL,
            win_probability_explanation TEXT,
            critical_traps_json       TEXT,
            compliance_gaps_json      TEXT,
            detected_currency_json    TEXT,
            created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tender_id) REFERENCES tenders(job_id)
        );
        CREATE INDEX IF NOT EXISTS idx_tender_results_tender_id ON tender_results(tender_id);

        CREATE TABLE IF NOT EXISTS processing_events (
            id          SERIAL PRIMARY KEY,
            tender_id   TEXT NOT NULL,
            stage       TEXT NOT NULL,
            status      TEXT DEFAULT 'pending',
            details     TEXT,
            duration_ms INTEGER,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tender_id) REFERENCES tenders(job_id)
        );
        CREATE INDEX IF NOT EXISTS idx_processing_events_tender_id ON processing_events(tender_id);
        CREATE INDEX IF NOT EXISTS idx_processing_events_stage ON processing_events(stage);

        CREATE TABLE IF NOT EXISTS audit_log (
            id              SERIAL PRIMARY KEY,
            tender_id       TEXT NOT NULL,
            stage           TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pending',
            timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            duration_ms     INTEGER,
            confidence      TEXT,
            source_module   TEXT,
            warnings        TEXT,
            errors          TEXT,
            details         TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tender_id) REFERENCES tenders(job_id)
        );
        CREATE INDEX IF NOT EXISTS idx_audit_log_tender_id ON audit_log(tender_id);
        CREATE INDEX IF NOT EXISTS idx_audit_log_stage ON audit_log(stage);
        CREATE INDEX IF NOT EXISTS idx_audit_log_status ON audit_log(status);

        CREATE TABLE IF NOT EXISTS platform_analytics (
            id                      SERIAL PRIMARY KEY,
            job_id                  TEXT UNIQUE NOT NULL,
            created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at            TIMESTAMP,
            processing_duration_ms  INTEGER,
            upload_size_bytes       INTEGER,
            page_count              INTEGER,
            ocr_used                INTEGER,
            extraction_method       TEXT,
            sector                  TEXT,
            sector_confidence       TEXT,
            duration_months         INTEGER,
            total_value             REAL,
            total_value_confidence  TEXT,
            boq_line_count          INTEGER,
            line_items_count        INTEGER,
            pricing_mode            TEXT,
            has_pricing             INTEGER,
            has_boq                 INTEGER,
            has_dates               INTEGER,
            has_locations           INTEGER,
            has_workforce           INTEGER,
            has_schedule            INTEGER,
            risk_score              REAL,
            risk_level              TEXT,
            warnings_count          INTEGER,
            errors_count            INTEGER,
            ocr_confidence          REAL,
            overall_confidence      REAL,
            pipeline_version        TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_platform_analytics_job_id ON platform_analytics(job_id);
    """

    def init_db():
        """Create PostgreSQL tables. Called once at startup."""
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            # Split schema by semicolons and execute each statement
            statements = [s.strip() for s in _PG_SCHEMA.split(";") if s.strip()]
            for stmt in statements:
                cursor.execute(stmt)
            conn.commit()
            logger.info("[DB] PostgreSQL database initialized")
        except Exception as e:
            logger.error("[DB] Failed to initialize PostgreSQL database: %s", e)
            raise
        finally:
            conn.close()

    async def get_db():
        """Return an async PostgreSQL connection wrapper."""
        pool = await _get_pool()
        pg_conn = await pool.acquire()
        return _AsyncConnection(pg_conn)

    async def close_db(db: _AsyncConnection):
        """Release the async PostgreSQL connection back to the pool."""
        pool = await _get_pool()
        await pool.release(db._conn)

    # -- Synchronous helpers for middleware compatibility --

    def get_user_by_email_sync(email: str) -> Optional[dict]:
        """Lookup user by email (synchronous, used in middleware)."""
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def get_user_by_id_sync(user_id: int) -> Optional[dict]:
        """Lookup user by ID (synchronous)."""
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def get_api_key_sync(api_key: str) -> Optional[dict]:
        """Lookup an API key and return associated user data."""
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.*, ak.key as api_key
                FROM api_keys ak
                JOIN users u ON u.id = ak.user_id
                WHERE ak.key = ?
            """, (api_key,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()