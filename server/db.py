"""SQLite persistence for the self-hosted CareerRadar starter.
Run on a single host; migrate to Postgres/Supabase before scaling horizontally.
"""
import sqlite3, os
from pathlib import Path
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = os.environ.get('CAREERRADAR_DB', str(ROOT / 'var' / 'careerradar.sqlite3'))

@contextmanager
def connect():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=10000')
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
 password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'seeker' CHECK (role IN ('seeker','employer','moderator','admin')),
 created_at TEXT NOT NULL, disabled INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 expires_at TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profiles (
 user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 full_name TEXT NOT NULL DEFAULT '', headline TEXT NOT NULL DEFAULT '',
 country TEXT NOT NULL DEFAULT 'United Arab Emirates', city TEXT NOT NULL DEFAULT 'Dubai',
 desired_titles TEXT NOT NULL DEFAULT '', skills TEXT NOT NULL DEFAULT '',
 years_experience INTEGER NOT NULL DEFAULT 0, salary_min INTEGER DEFAULT NULL,
 salary_currency TEXT NOT NULL DEFAULT 'AED', summary TEXT NOT NULL DEFAULT '',
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS providers (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK (kind IN ('greenhouse','lever')),
 slug TEXT NOT NULL, display_name TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, UNIQUE(kind,slug)
);
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, source TEXT NOT NULL, external_id TEXT NOT NULL,
 company TEXT NOT NULL, title TEXT NOT NULL, location TEXT NOT NULL DEFAULT '',
 country TEXT NOT NULL DEFAULT '', work_type TEXT NOT NULL DEFAULT 'Not specified',
 description TEXT NOT NULL DEFAULT '', url TEXT NOT NULL, posted_at TEXT,
 first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','closed','review')),
 salary_min INTEGER, salary_max INTEGER, currency TEXT,
 UNIQUE(source,external_id)
);
CREATE INDEX IF NOT EXISTS idx_jobs_status_date ON jobs(status,first_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
CREATE TABLE IF NOT EXISTS saves (
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 created_at TEXT NOT NULL, PRIMARY KEY(user_id,job_id)
);
CREATE TABLE IF NOT EXISTS alerts (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 name TEXT NOT NULL, query TEXT NOT NULL DEFAULT '', location TEXT NOT NULL DEFAULT '',
 frequency TEXT NOT NULL DEFAULT 'daily' CHECK(frequency IN ('immediate','2h','6h','daily','weekly','off')),
 enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alert_user ON alerts(user_id);
CREATE TABLE IF NOT EXISTS alert_deliveries (
 alert_id TEXT NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
 job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 delivered_at TEXT NOT NULL, PRIMARY KEY(alert_id,job_id)
);
CREATE TABLE IF NOT EXISTS notifications (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL,
 title TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL,
 read_at TEXT DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS applications (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL,
 company TEXT NOT NULL, title TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('interested','applied','assessment','interview','followup','offer','rejected','withdrawn')),
 applied_at TEXT DEFAULT NULL, follow_up_at TEXT DEFAULT NULL,
 notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_app_user ON applications(user_id,created_at DESC);
CREATE TABLE IF NOT EXISTS cv_documents (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 filename TEXT NOT NULL, stored_name TEXT NOT NULL, bytes INTEGER NOT NULL,
 extracted_text TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS job_reports (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 reason TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ingestion_runs (
 id TEXT PRIMARY KEY, provider_id TEXT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
 started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL,
 new_count INTEGER NOT NULL DEFAULT 0, updated_count INTEGER NOT NULL DEFAULT 0,
 error TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS audit_log (
 id TEXT PRIMARY KEY, actor_id TEXT NOT NULL, action TEXT NOT NULL,
 detail TEXT NOT NULL, created_at TEXT NOT NULL
);
"""

def init_db():
    with connect() as c:
        c.executescript(SCHEMA)

# 0.3 additive schema. Existing self-hosted SQLite data is retained.
SCHEMA += """
CREATE TABLE IF NOT EXISTS walkin_events (
 id TEXT PRIMARY KEY,company TEXT NOT NULL,title TEXT NOT NULL,venue TEXT NOT NULL,
 city TEXT NOT NULL,country TEXT NOT NULL,starts_at TEXT NOT NULL,ends_at TEXT NOT NULL,
 source_url TEXT NOT NULL,requirements TEXT NOT NULL DEFAULT '',documents TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','published','cancelled')),
 reviewed_at TEXT,created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_walkins_status_time ON walkin_events(status,starts_at);
CREATE TABLE IF NOT EXISTS cv_shares (
 id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 cv_id TEXT NOT NULL REFERENCES cv_documents(id) ON DELETE CASCADE,
 token_hash TEXT NOT NULL UNIQUE,expires_at TEXT NOT NULL,
 max_opens INTEGER NOT NULL DEFAULT 10,open_count INTEGER NOT NULL DEFAULT 0,
 revoked_at TEXT,created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cv_shares_user ON cv_shares(user_id);
CREATE TABLE IF NOT EXISTS followup_reminders (
 application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
 due_date TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(application_id,due_date)
);
"""

# 0.4: Persist privately owned editable, job-targeted CV and cover-letter drafts.
SCHEMA += """
CREATE TABLE IF NOT EXISTS tailored_documents (
 id TEXT PRIMARY KEY,
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 cv_id TEXT REFERENCES cv_documents(id) ON DELETE SET NULL,
 kind TEXT NOT NULL CHECK(kind IN ('cv','cover_letter')),
 title TEXT NOT NULL,
 content TEXT NOT NULL,
 match_terms_json TEXT NOT NULL DEFAULT '[]',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tailored_owner ON tailored_documents(user_id,updated_at DESC);
"""
