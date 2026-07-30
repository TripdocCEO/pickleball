"""
정관 피클볼 클럽 — 백엔드 API
FastAPI + SQLite. 정적 사이트(public/)도 같은 서버에서 서빙합니다.

실행:  uvicorn server.main:app --reload --port 8000
문서:  http://localhost:8000/api/docs
"""
from __future__ import annotations

import hashlib
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .db import DB_PATH, get_conn, init_db

ROOT_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = ROOT_DIR / "public"

ADMIN_TOKEN = os.environ.get("JGPC_ADMIN_TOKEN", "changeme-dev-token")
IP_SALT = os.environ.get("JGPC_IP_SALT", "jgpc-local-salt")
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "JGPC_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
    ).split(",")
    if o.strip()
]

CATEGORIES = ("notice", "free", "review", "partner", "market")
# 회원이 직접 쓸 수 있는 분류 (공지는 운영자 전용)
PUBLIC_CATEGORIES = ("free", "review", "partner", "market")

# 분당 쓰기 제한 (환경변수로 조정 가능)
RATE_LIMITS = {
    "post": int(os.environ.get("JGPC_RATE_POST", 3)),
    "comment": int(os.environ.get("JGPC_RATE_COMMENT", 10)),
    "trial": int(os.environ.get("JGPC_RATE_TRIAL", 3)),
}

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="정관 피클볼 클럽 API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


# ────────────────────────────── 유틸 ──────────────────────────────
CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
PHONE_RE = re.compile(r"^01[0-9][-\s]?\d{3,4}[-\s]?\d{4}$")


def clean(text: str) -> str:
    """제어문자 제거 + 앞뒤 공백 정리. HTML은 이스케이프하지 않고 저장하며,
    출력 시 프런트엔드가 textContent로 렌더링해 XSS를 차단합니다."""
    return CTRL_RE.sub("", text).strip()


def ip_hash(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")
    return hashlib.sha256(f"{IP_SALT}:{ip}".encode()).hexdigest()[:16]


def check_rate(conn, kind: str, iph: str) -> None:
    limit = RATE_LIMITS.get(kind, 10)
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM write_log "
        "WHERE kind = ? AND ip_hash = ? AND created_at >= datetime('now','localtime','-60 seconds')",
        (kind, iph),
    ).fetchone()
    if row["n"] >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"요청이 너무 잦습니다. 잠시 후 다시 시도해 주세요. (분당 {limit}회)",
        )
    conn.execute("INSERT INTO write_log(kind, ip_hash) VALUES (?, ?)", (kind, iph))


def require_admin(x_admin_token: str = Header(default="")) -> None:
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="관리자 토큰이 필요합니다.")


# ────────────────────────────── 스키마 ──────────────────────────────
class PostIn(BaseModel):
    category: Literal["free", "review", "partner", "market"]
    title: str = Field(min_length=2, max_length=60)
    body: str = Field(min_length=2, max_length=5000)
    author: str = Field(default="익명", max_length=12)

    @field_validator("title", "body", "author")
    @classmethod
    def _clean(cls, v: str) -> str:
        v = clean(v)
        if not v:
            raise ValueError("내용을 입력해 주세요.")
        return v


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=500)
    author: str = Field(default="익명", max_length=12)

    @field_validator("body", "author")
    @classmethod
    def _clean(cls, v: str) -> str:
        v = clean(v)
        if not v:
            raise ValueError("내용을 입력해 주세요.")
        return v


class LikeIn(BaseModel):
    client_id: str = Field(min_length=6, max_length=64)


class TrialIn(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    phone: str = Field(min_length=9, max_length=20)
    slot: str = Field(min_length=1, max_length=40)
    headcount: str = Field(default="1명", max_length=20)
    experience: Literal["first", "some", "regular"] = "first"
    memo: Optional[str] = Field(default=None, max_length=300)
    source: Optional[str] = Field(default=None, max_length=80)

    @field_validator("name", "slot", "headcount")
    @classmethod
    def _clean(cls, v: str) -> str:
        v = clean(v)
        if not v:
            raise ValueError("내용을 입력해 주세요.")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        v = clean(v)
        if not PHONE_RE.match(v):
            raise ValueError("휴대폰 번호 형식이 올바르지 않습니다. (예: 010-1234-5678)")
        return v


class TrialStatusIn(BaseModel):
    status: Optional[Literal["new", "contacted", "booked", "done", "canceled"]] = None
    memo: Optional[str] = Field(default=None, max_length=300)


class PinIn(BaseModel):
    pinned: bool


# ────────────────────────────── 오류 응답 ──────────────────────────────
@app.exception_handler(HTTPException)
async def _http_exc(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.detail})


# ────────────────────────────── 헬스 ──────────────────────────────
@app.get("/api/health")
def health():
    with get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM posts WHERE deleted = 0").fetchone()["n"]
        ver = conn.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()
    return {"ok": True, "db": str(DB_PATH), "schema": ver["value"] if ver else None, "posts": n}


# ────────────────────────────── 게시판 ──────────────────────────────
def _post_row(conn, pid: int, with_comments: bool = False) -> dict:
    row = conn.execute(
        "SELECT p.*, "
        " (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id AND c.deleted = 0) AS comment_count, "
        " (SELECT COUNT(*) FROM post_likes l WHERE l.post_id = p.id) AS likes "
        "FROM posts p WHERE p.id = ? AND p.deleted = 0",
        (pid,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="글을 찾을 수 없습니다.")
    d = dict(row)
    d.pop("author_key", None)
    d["pinned"] = bool(d["pinned"])
    if with_comments:
        d["comments"] = [
            dict(c)
            for c in conn.execute(
                "SELECT id, author, body, created_at FROM comments "
                "WHERE post_id = ? AND deleted = 0 ORDER BY id ASC",
                (pid,),
            ).fetchall()
        ]
    return d


@app.get("/api/posts")
def list_posts(
    category: str = Query(default="all"),
    q: str = Query(default="", max_length=60),
    sort: Literal["new", "view", "cmt"] = "new",
    page: int = Query(default=1, ge=1, le=1000),
    size: int = Query(default=20, ge=1, le=50),
):
    if category != "all" and category not in CATEGORIES:
        raise HTTPException(status_code=400, detail="존재하지 않는 분류입니다.")

    where = ["p.deleted = 0"]
    params: list = []
    if category != "all":
        where.append("p.category = ?")
        params.append(category)
    if q.strip():
        where.append("(p.title LIKE ? OR p.body LIKE ? OR p.author LIKE ?)")
        like = f"%{q.strip()}%"
        params += [like, like, like]

    order = {
        "new": "p.pinned DESC, p.created_at DESC, p.id DESC",
        "view": "p.pinned DESC, p.views DESC, p.id DESC",
        "cmt": "p.pinned DESC, comment_count DESC, p.id DESC",
    }[sort]

    sql = (
        "SELECT p.id, p.category, p.title, p.author, p.pinned, p.views, p.created_at, "
        " (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id AND c.deleted = 0) AS comment_count, "
        " (SELECT COUNT(*) FROM post_likes l WHERE l.post_id = p.id) AS likes "
        f"FROM posts p WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ? OFFSET ?"
    )

    with get_conn() as conn:
        rows = conn.execute(sql, (*params, size, (page - 1) * size)).fetchall()
        total = conn.execute(
            f"SELECT COUNT(*) AS n FROM posts p WHERE {' AND '.join(where)}", params
        ).fetchone()["n"]
        counts = {
            r["category"]: r["n"]
            for r in conn.execute(
                "SELECT category, COUNT(*) AS n FROM posts WHERE deleted = 0 GROUP BY category"
            ).fetchall()
        }

    items = []
    for r in rows:
        d = dict(r)
        d["pinned"] = bool(d["pinned"])
        items.append(d)

    return {
        "ok": True,
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "counts": {"all": sum(counts.values()), **{c: counts.get(c, 0) for c in CATEGORIES}},
    }


@app.get("/api/posts/{pid}")
def get_post(pid: int):
    with get_conn() as conn:
        conn.execute("UPDATE posts SET views = views + 1 WHERE id = ? AND deleted = 0", (pid,))
        return {"ok": True, "post": _post_row(conn, pid, with_comments=True)}


@app.post("/api/posts", status_code=201)
def create_post(payload: PostIn, request: Request):
    iph = ip_hash(request)
    with get_conn() as conn:
        check_rate(conn, "post", iph)
        cur = conn.execute(
            "INSERT INTO posts(category, title, body, author, author_key) VALUES (?,?,?,?,?)",
            (payload.category, payload.title, payload.body, payload.author, iph),
        )
        return {"ok": True, "post": _post_row(conn, cur.lastrowid, with_comments=True)}


@app.post("/api/posts/{pid}/comments", status_code=201)
def add_comment(pid: int, payload: CommentIn, request: Request):
    iph = ip_hash(request)
    with get_conn() as conn:
        _post_row(conn, pid)  # 존재 확인
        check_rate(conn, "comment", iph)
        conn.execute(
            "INSERT INTO comments(post_id, author, body) VALUES (?,?,?)",
            (pid, payload.author, payload.body),
        )
        return {"ok": True, "post": _post_row(conn, pid, with_comments=True)}


@app.post("/api/posts/{pid}/like")
def like_post(pid: int, payload: LikeIn):
    with get_conn() as conn:
        _post_row(conn, pid)
        cur = conn.execute(
            "INSERT OR IGNORE INTO post_likes(post_id, client_id) VALUES (?,?)",
            (pid, payload.client_id),
        )
        likes = conn.execute(
            "SELECT COUNT(*) AS n FROM post_likes WHERE post_id = ?", (pid,)
        ).fetchone()["n"]
    return {"ok": True, "likes": likes, "added": cur.rowcount > 0}


@app.delete("/api/posts/{pid}", dependencies=[Depends(require_admin)])
def delete_post(pid: int):
    with get_conn() as conn:
        _post_row(conn, pid)
        conn.execute("UPDATE posts SET deleted = 1, updated_at = datetime('now','localtime') WHERE id = ?", (pid,))
    return {"ok": True, "deleted": pid}


# ────────────────────────────── 무료 체험 신청 ──────────────────────────────
@app.post("/api/trials", status_code=201)
def create_trial(payload: TrialIn, request: Request):
    iph = ip_hash(request)
    with get_conn() as conn:
        check_rate(conn, "trial", iph)
        cur = conn.execute(
            "INSERT INTO trials(name, phone, slot, headcount, experience, memo, source) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                payload.name, payload.phone, payload.slot, payload.headcount,
                payload.experience, payload.memo, payload.source,
            ),
        )
    return {"ok": True, "id": cur.lastrowid, "message": "신청이 접수됐습니다. 카카오톡으로 확정 안내를 보내 드릴게요."}


@app.get("/api/admin/trials", dependencies=[Depends(require_admin)])
def list_trials(status: str = Query(default="all"), limit: int = Query(default=100, ge=1, le=500)):
    sql = "SELECT * FROM trials"
    params: list = []
    if status != "all":
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    return {"ok": True, "items": rows, "total": len(rows)}


@app.patch("/api/admin/trials/{tid}", dependencies=[Depends(require_admin)])
def update_trial(tid: int, payload: TrialStatusIn):
    sets, params = [], []
    if payload.status is not None:
        sets.append("status = ?")
        params.append(payload.status)
    if payload.memo is not None:
        sets.append("memo = ?")
        params.append(clean(payload.memo))
    if not sets:
        raise HTTPException(status_code=400, detail="변경할 항목이 없습니다.")
    with get_conn() as conn:
        cur = conn.execute(f"UPDATE trials SET {', '.join(sets)} WHERE id = ?", (*params, tid))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="신청 건을 찾을 수 없습니다.")
        row = conn.execute("SELECT * FROM trials WHERE id = ?", (tid,)).fetchone()
    return {"ok": True, "trial": dict(row)}


@app.get("/api/admin/posts", dependencies=[Depends(require_admin)])
def admin_posts(limit: int = Query(default=200, ge=1, le=500)):
    """관리용 글 목록 — 삭제된 글까지 포함."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT p.id, p.category, p.title, p.author, p.pinned, p.views, p.deleted, p.created_at, "
            " (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id AND c.deleted = 0) AS comment_count "
            "FROM posts p ORDER BY p.pinned DESC, p.created_at DESC, p.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return {"ok": True, "items": [dict(r) for r in rows], "total": len(rows)}


@app.patch("/api/admin/posts/{pid}/pin", dependencies=[Depends(require_admin)])
def pin_post(pid: int, payload: PinIn):
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE posts SET pinned = ?, updated_at = datetime('now','localtime') WHERE id = ? AND deleted = 0",
            (1 if payload.pinned else 0, pid),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="글을 찾을 수 없습니다.")
    return {"ok": True, "id": pid, "pinned": payload.pinned}


@app.post("/api/admin/posts/{pid}/restore", dependencies=[Depends(require_admin)])
def restore_post(pid: int):
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE posts SET deleted = 0, updated_at = datetime('now','localtime') WHERE id = ?", (pid,)
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="글을 찾을 수 없습니다.")
    return {"ok": True, "id": pid, "restored": True}


@app.get("/api/admin/verify", dependencies=[Depends(require_admin)])
def verify_token():
    """관리자 페이지 로그인 확인용."""
    return {"ok": True}


@app.get("/api/admin/stats", dependencies=[Depends(require_admin)])
def stats():
    with get_conn() as conn:
        posts = conn.execute("SELECT COUNT(*) AS n FROM posts WHERE deleted = 0").fetchone()["n"]
        comments = conn.execute("SELECT COUNT(*) AS n FROM comments WHERE deleted = 0").fetchone()["n"]
        trials = conn.execute("SELECT COUNT(*) AS n FROM trials").fetchone()["n"]
        by_status = {
            r["status"]: r["n"]
            for r in conn.execute("SELECT status, COUNT(*) AS n FROM trials GROUP BY status").fetchall()
        }
        recent = conn.execute(
            "SELECT COUNT(*) AS n FROM trials WHERE created_at >= datetime('now','localtime','-7 days')"
        ).fetchone()["n"]
    return {
        "ok": True,
        "posts": posts,
        "comments": comments,
        "trials": {"total": trials, "last7days": recent, "by_status": by_status},
    }


# ────────────────────────────── 정적 사이트 ──────────────────────────────
# API 라우트 뒤에 마운트해야 /api/* 가 가려지지 않습니다.
if PUBLIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="public")
