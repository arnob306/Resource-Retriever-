CREATE TABLE IF NOT EXISTS files (
    id              TEXT PRIMARY KEY,        -- uuid4, stable synthetic id
    source_type     TEXT NOT NULL CHECK (source_type IN ('local', 'drive')),
    local_path      TEXT,                    -- NULL for drive-only
    drive_id        TEXT,                    -- NULL for local-only
    display_name    TEXT NOT NULL,
    content_hash    TEXT,                    -- sha256 (local) / md5Checksum (drive); NULL only transiently before first hash
    file_size       INTEGER,                 -- bytes; secondary change-trigger alongside mtime
    modified_time   INTEGER NOT NULL,        -- epoch milliseconds UTC
    page_count      INTEGER,
    status          TEXT NOT NULL DEFAULT 'discovered'
                       CHECK (status IN ('discovered', 'indexed', 'extraction_failed', 'excluded')),
    indexed_at      TEXT,                    -- NULL until successfully embedded
    created_at      TEXT NOT NULL,
    UNIQUE (source_type, local_path),        -- SQLite treats NULLs as distinct in UNIQUE indexes: intentional
    UNIQUE (source_type, drive_id)
);
CREATE INDEX IF NOT EXISTS idx_files_content_hash ON files(content_hash);
CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);

CREATE TABLE IF NOT EXISTS index_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    files_discovered    INTEGER NOT NULL DEFAULT 0,
    files_reprocessed   INTEGER NOT NULL DEFAULT 0,
    files_skipped       INTEGER NOT NULL DEFAULT 0,
    files_deleted       INTEGER NOT NULL DEFAULT 0,
    files_failed        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS search_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    query           TEXT NOT NULL,
    latency_ms      INTEGER NOT NULL,
    result_count    INTEGER NOT NULL,
    searched_at     TEXT NOT NULL
);
