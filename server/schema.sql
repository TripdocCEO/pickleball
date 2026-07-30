-- ─────────────────────────────────────────────────────────────
-- 정관 피클볼 클럽 — SQLite 스키마
-- forward-compatible: 컬럼 추가만 하고 삭제/이름변경은 마이그레이션으로
-- ─────────────────────────────────────────────────────────────

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- 스키마 버전 관리
CREATE TABLE IF NOT EXISTS schema_meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
INSERT OR IGNORE INTO schema_meta(key, value) VALUES ('version', '1');

-- ── 게시글 ──
CREATE TABLE IF NOT EXISTS posts (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  category   TEXT    NOT NULL CHECK (category IN ('notice','free','review','partner','market')),
  title      TEXT    NOT NULL,
  body       TEXT    NOT NULL,
  author     TEXT    NOT NULL,
  pinned     INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0,1)),
  views      INTEGER NOT NULL DEFAULT 0,
  deleted    INTEGER NOT NULL DEFAULT 0 CHECK (deleted IN (0,1)),
  author_key TEXT,                       -- 작성자 본인 확인용 해시(수정·삭제)
  created_at TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
  updated_at TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_posts_list    ON posts(deleted, pinned DESC, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_cat     ON posts(category, deleted);

-- ── 댓글 ──
CREATE TABLE IF NOT EXISTS comments (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id    INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  author     TEXT    NOT NULL,
  body       TEXT    NOT NULL,
  deleted    INTEGER NOT NULL DEFAULT 0 CHECK (deleted IN (0,1)),
  created_at TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id, deleted, id);

-- ── 좋아요 (클라이언트 토큰 단위 중복 방지) ──
CREATE TABLE IF NOT EXISTS post_likes (
  post_id    INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  client_id  TEXT    NOT NULL,
  created_at TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
  PRIMARY KEY (post_id, client_id)
);

-- ── 무료 체험 신청 (사이트 1차 전환 지표) ──
CREATE TABLE IF NOT EXISTS trials (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  name       TEXT    NOT NULL,
  phone      TEXT    NOT NULL,
  slot       TEXT    NOT NULL,           -- 희망 요일·시간
  headcount  TEXT    NOT NULL DEFAULT '1명',
  experience TEXT    NOT NULL DEFAULT 'first',  -- first | some | regular
  memo       TEXT,
  source     TEXT,                       -- 유입 페이지
  status     TEXT    NOT NULL DEFAULT 'new' CHECK (status IN ('new','contacted','booked','done','canceled')),
  created_at TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_trials_status ON trials(status, created_at DESC);

-- ── 요청 로그 (레이트리밋·스팸 추적용, 경량) ──
CREATE TABLE IF NOT EXISTS write_log (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  kind       TEXT NOT NULL,              -- post | comment | trial
  ip_hash    TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_write_log ON write_log(ip_hash, kind, created_at);
