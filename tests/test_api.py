"""API QA 테스트 — 각 테스트는 임시 DB에서 격리 실행됩니다."""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ADMIN = "test-token"


def _make_client(tmp_path, monkeypatch, **env):
    monkeypatch.setenv("JGPC_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("JGPC_ADMIN_TOKEN", ADMIN)
    for k, v in env.items():
        monkeypatch.setenv(k, str(v))
    # 환경변수를 반영하려면 모듈을 새로 로드해야 합니다.
    for mod in ("server.main", "server.db"):
        sys.modules.pop(mod, None)
    main = importlib.import_module("server.main")
    return TestClient(main.app)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    with _make_client(tmp_path, monkeypatch) as c:
        yield c


@pytest.fixture()
def bulk_client(tmp_path, monkeypatch):
    """레이트리밋을 풀어 대량 입력이 필요한 테스트용."""
    with _make_client(tmp_path, monkeypatch, JGPC_RATE_POST=1000, JGPC_RATE_TRIAL=1000) as c:
        yield c


def mkpost(client, **kw):
    payload = {
        "category": "free",
        "title": "테스트 제목입니다",
        "body": "테스트 본문입니다.",
        "author": "테스터",
    }
    payload.update(kw)
    return client.post("/api/posts", json=payload)


# ────────────── 헬스 / 기본 ──────────────
def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["schema"] == "1"


def test_empty_list(client):
    r = client.get("/api/posts")
    body = r.json()
    assert r.status_code == 200
    assert body["total"] == 0
    assert body["counts"]["all"] == 0


# ────────────── 글쓰기 ──────────────
def test_create_post(client):
    r = mkpost(client)
    assert r.status_code == 201
    p = r.json()["post"]
    assert p["title"] == "테스트 제목입니다"
    assert p["views"] == 0
    assert p["comment_count"] == 0
    assert p["likes"] == 0
    assert "author_key" not in p, "작성자 해시가 외부로 노출되면 안 됩니다"


def test_create_post_trims_and_strips_control_chars(client):
    r = mkpost(client, title="  제목 앞뒤 공백  ", body="본문\x00에 널문자")
    p = r.json()["post"]
    assert p["title"] == "제목 앞뒤 공백"
    assert "\x00" not in p["body"]


@pytest.mark.parametrize(
    "bad",
    [
        {"title": "짧"},                      # 최소 길이 미달
        {"title": "a" * 61},                  # 최대 길이 초과
        {"body": "x"},                        # 본문 최소 길이 미달
        {"category": "notice"},               # 공지는 회원이 못 씀
        {"category": "없는분류"},
        {"author": "a" * 13},                 # 닉네임 초과
        {"title": "   "},                     # 공백만
    ],
)
def test_create_post_validation(client, bad):
    assert mkpost(client, **bad).status_code == 422


def test_notice_is_admin_only_but_readable(client):
    """공지는 API로 작성 불가하지만, 시드로 들어간 공지는 조회·필터가 된다."""
    from server.db import get_conn

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO posts(category,title,body,author,pinned) VALUES ('notice','공지 제목','내용','운영팀',1)"
        )
    r = client.get("/api/posts", params={"category": "notice"})
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["pinned"] is True


# ────────────── 조회 ──────────────
def test_get_post_increments_views(client):
    pid = mkpost(client).json()["post"]["id"]
    assert client.get(f"/api/posts/{pid}").json()["post"]["views"] == 1
    assert client.get(f"/api/posts/{pid}").json()["post"]["views"] == 2


def test_get_missing_post_404(client):
    r = client.get("/api/posts/9999")
    assert r.status_code == 404
    assert r.json()["ok"] is False


def test_list_search_and_filter(client):
    mkpost(client, title="키친 라인 질문", category="free")
    mkpost(client, title="패들 나눔합니다", category="market", body="입문용 패들 드려요")

    assert client.get("/api/posts", params={"q": "키친"}).json()["total"] == 1
    assert client.get("/api/posts", params={"q": "입문용"}).json()["total"] == 1
    assert client.get("/api/posts", params={"category": "market"}).json()["total"] == 1
    assert client.get("/api/posts", params={"q": "없는단어"}).json()["total"] == 0

    counts = client.get("/api/posts").json()["counts"]
    assert counts["all"] == 2 and counts["market"] == 1 and counts["review"] == 0


def test_list_bad_category_400(client):
    assert client.get("/api/posts", params={"category": "xxx"}).status_code == 400


def test_pinned_first_regardless_of_sort(client):
    from server.db import get_conn

    mkpost(client, title="일반글 최신")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO posts(category,title,body,author,pinned,views) "
            "VALUES ('notice','고정 공지','내용','운영팀',1,0)"
        )
    for sort in ("new", "view", "cmt"):
        items = client.get("/api/posts", params={"sort": sort}).json()["items"]
        assert items[0]["title"] == "고정 공지", f"{sort} 정렬에서 고정글이 최상단이 아님"


def test_pagination(bulk_client):
    for i in range(7):
        assert mkpost(bulk_client, title=f"페이지 테스트 {i}").status_code == 201
    p1 = bulk_client.get("/api/posts", params={"page": 1, "size": 3}).json()
    p2 = bulk_client.get("/api/posts", params={"page": 2, "size": 3}).json()
    p3 = bulk_client.get("/api/posts", params={"page": 3, "size": 3}).json()
    assert (len(p1["items"]), len(p2["items"]), len(p3["items"])) == (3, 3, 1)
    assert p1["total"] == 7
    assert {i["id"] for i in p1["items"]}.isdisjoint({i["id"] for i in p2["items"]})


def test_pagination_out_of_range_is_empty_not_error(bulk_client):
    mkpost(bulk_client)
    r = bulk_client.get("/api/posts", params={"page": 99, "size": 20})
    assert r.status_code == 200 and r.json()["items"] == [] and r.json()["total"] == 1


def test_page_size_bounds(client):
    assert client.get("/api/posts", params={"size": 0}).status_code == 422
    assert client.get("/api/posts", params={"size": 51}).status_code == 422
    assert client.get("/api/posts", params={"page": 0}).status_code == 422


# ────────────── 댓글 ──────────────
def test_add_comment(client):
    pid = mkpost(client).json()["post"]["id"]
    r = client.post(f"/api/posts/{pid}/comments", json={"body": "좋은 글이네요", "author": "이웃"})
    assert r.status_code == 201
    post = r.json()["post"]
    assert post["comment_count"] == 1
    assert post["comments"][0]["body"] == "좋은 글이네요"


def test_comment_on_missing_post_404(client):
    assert client.post("/api/posts/9999/comments", json={"body": "hi"}).status_code == 404


def test_comment_validation(client):
    pid = mkpost(client).json()["post"]["id"]
    assert client.post(f"/api/posts/{pid}/comments", json={"body": ""}).status_code == 422
    assert client.post(f"/api/posts/{pid}/comments", json={"body": "a" * 501}).status_code == 422


# ────────────── 좋아요 ──────────────
def test_like_is_deduplicated_per_client(client):
    pid = mkpost(client).json()["post"]["id"]
    r1 = client.post(f"/api/posts/{pid}/like", json={"client_id": "client-aaa"})
    r2 = client.post(f"/api/posts/{pid}/like", json={"client_id": "client-aaa"})
    r3 = client.post(f"/api/posts/{pid}/like", json={"client_id": "client-bbb"})
    assert r1.json() == {"ok": True, "likes": 1, "added": True}
    assert r2.json() == {"ok": True, "likes": 1, "added": False}
    assert r3.json()["likes"] == 2


def test_like_requires_client_id(client):
    pid = mkpost(client).json()["post"]["id"]
    assert client.post(f"/api/posts/{pid}/like", json={"client_id": "ab"}).status_code == 422


# ────────────── 삭제 (관리자) ──────────────
def test_delete_requires_admin_token(client):
    pid = mkpost(client).json()["post"]["id"]
    assert client.delete(f"/api/posts/{pid}").status_code == 401
    assert client.delete(f"/api/posts/{pid}", headers={"x-admin-token": "wrong"}).status_code == 401
    assert client.delete(f"/api/posts/{pid}", headers={"x-admin-token": ADMIN}).status_code == 200
    # 소프트 삭제 후 목록·상세에서 사라져야 함
    assert client.get("/api/posts").json()["total"] == 0
    assert client.get(f"/api/posts/{pid}").status_code == 404


# ────────────── 무료 체험 신청 ──────────────
def trial_payload(**kw):
    p = {
        "name": "홍길동",
        "phone": "010-1234-5678",
        "slot": "토요일 오전 (10:00)",
        "headcount": "1명 (혼자 가요)",
        "experience": "first",
        "source": "first-visit",
    }
    p.update(kw)
    return p


def test_create_trial(client):
    r = client.post("/api/trials", json=trial_payload())
    assert r.status_code == 201
    assert r.json()["ok"] is True and r.json()["id"] >= 1


@pytest.mark.parametrize(
    "bad",
    [
        {"phone": "1234"},
        {"phone": "02-123-4567"},        # 유선번호 거부
        {"phone": "010-12-34"},
        {"name": ""},
        {"experience": "expert"},        # 허용값 외
        {"slot": ""},
    ],
)
def test_trial_validation(client, bad):
    assert client.post("/api/trials", json=trial_payload(**bad)).status_code == 422


@pytest.mark.parametrize("ok_phone", ["010-1234-5678", "01012345678", "010 1234 5678", "011-234-5678"])
def test_trial_phone_formats(client, ok_phone):
    assert client.post("/api/trials", json=trial_payload(phone=ok_phone)).status_code == 201


def test_trials_admin_only(client):
    client.post("/api/trials", json=trial_payload())
    assert client.get("/api/admin/trials").status_code == 401
    r = client.get("/api/admin/trials", headers={"x-admin-token": ADMIN})
    assert r.status_code == 200 and r.json()["total"] == 1
    assert r.json()["items"][0]["status"] == "new"


def test_trial_status_update(client):
    tid = client.post("/api/trials", json=trial_payload()).json()["id"]
    h = {"x-admin-token": ADMIN}
    assert client.patch(f"/api/admin/trials/{tid}", json={"status": "booked"}, headers=h).status_code == 200
    assert client.get("/api/admin/trials", params={"status": "booked"}, headers=h).json()["total"] == 1
    assert client.patch(f"/api/admin/trials/{tid}", json={"status": "몰라"}, headers=h).status_code == 422
    assert client.patch("/api/admin/trials/999", json={"status": "done"}, headers=h).status_code == 404


def test_trial_memo_update(client):
    tid = client.post("/api/trials", json=trial_payload()).json()["id"]
    h = {"x-admin-token": ADMIN}
    r = client.patch(f"/api/admin/trials/{tid}", json={"memo": "무릎 통증 있음"}, headers=h)
    assert r.status_code == 200
    t = r.json()["trial"]
    assert t["memo"] == "무릎 통증 있음"
    assert t["status"] == "new", "메모만 바꿀 때 상태가 초기화되면 안 됩니다"
    # 상태만 변경해도 메모는 유지
    t2 = client.patch(f"/api/admin/trials/{tid}", json={"status": "done"}, headers=h).json()["trial"]
    assert t2["status"] == "done" and t2["memo"] == "무릎 통증 있음"


def test_trial_update_requires_a_field(client):
    tid = client.post("/api/trials", json=trial_payload()).json()["id"]
    r = client.patch(f"/api/admin/trials/{tid}", json={}, headers={"x-admin-token": ADMIN})
    assert r.status_code == 400


# ────────────── 관리자 페이지 지원 API ──────────────
def test_admin_verify(client):
    assert client.get("/api/admin/verify").status_code == 401
    assert client.get("/api/admin/verify", headers={"x-admin-token": "nope"}).status_code == 401
    assert client.get("/api/admin/verify", headers={"x-admin-token": ADMIN}).json() == {"ok": True}


def test_admin_posts_includes_deleted(client):
    pid = mkpost(client).json()["post"]["id"]
    h = {"x-admin-token": ADMIN}
    client.delete(f"/api/posts/{pid}", headers=h)
    assert client.get("/api/posts").json()["total"] == 0          # 공개 목록에서는 사라지고
    items = client.get("/api/admin/posts", headers=h).json()["items"]
    assert len(items) == 1 and items[0]["deleted"] == 1            # 관리 목록에는 남아 있어야 함


def test_admin_posts_requires_token(client):
    assert client.get("/api/admin/posts").status_code == 401


def test_pin_and_unpin(client):
    pid = mkpost(client).json()["post"]["id"]
    h = {"x-admin-token": ADMIN}
    r = client.patch(f"/api/admin/posts/{pid}/pin", json={"pinned": True}, headers=h)
    assert r.status_code == 200 and r.json()["pinned"] is True
    assert client.get("/api/posts").json()["items"][0]["pinned"] is True
    client.patch(f"/api/admin/posts/{pid}/pin", json={"pinned": False}, headers=h)
    assert client.get("/api/posts").json()["items"][0]["pinned"] is False


def test_pin_requires_admin(client):
    pid = mkpost(client).json()["post"]["id"]
    assert client.patch(f"/api/admin/posts/{pid}/pin", json={"pinned": True}).status_code == 401


def test_restore_deleted_post(client):
    pid = mkpost(client).json()["post"]["id"]
    h = {"x-admin-token": ADMIN}
    client.delete(f"/api/posts/{pid}", headers=h)
    assert client.get(f"/api/posts/{pid}").status_code == 404
    assert client.post(f"/api/admin/posts/{pid}/restore", headers=h).status_code == 200
    assert client.get(f"/api/posts/{pid}").status_code == 200
    assert client.get("/api/posts").json()["total"] == 1


def test_restore_requires_admin(client):
    assert client.post("/api/admin/posts/1/restore").status_code == 401


def test_admin_page_is_served(client):
    r = client.get("/admin.html")
    assert r.status_code == 200
    assert "관리자" in r.text
    assert 'name="robots" content="noindex' in r.text, "관리자 페이지는 검색 색인에서 제외돼야 합니다"


def test_stats(client):
    mkpost(client)
    pid = client.get("/api/posts").json()["items"][0]["id"]
    client.post(f"/api/posts/{pid}/comments", json={"body": "댓글"})
    client.post("/api/trials", json=trial_payload())
    s = client.get("/api/admin/stats", headers={"x-admin-token": ADMIN}).json()
    assert s["posts"] == 1 and s["comments"] == 1
    assert s["trials"]["total"] == 1 and s["trials"]["last7days"] == 1
    assert s["trials"]["by_status"]["new"] == 1


# ────────────── 레이트리밋 ──────────────
def test_rate_limit_on_posts(client):
    codes = [mkpost(client, title=f"연속 작성 {i}").status_code for i in range(5)]
    assert codes[:3] == [201, 201, 201]
    assert codes[3] == 429 and codes[4] == 429


def test_rate_limit_on_trials(client):
    codes = [client.post("/api/trials", json=trial_payload()).status_code for _ in range(5)]
    assert codes.count(201) == 3
    assert codes.count(429) == 2


# ────────────── 보안 ──────────────
def test_stored_xss_payload_is_returned_verbatim_not_executed(client):
    """서버는 원문을 그대로 저장·반환하고, 프런트엔드가 textContent로 렌더링해 차단합니다.
    (이스케이프를 서버에서 이중으로 하면 본문이 깨지므로 저장은 원문 유지가 맞습니다.)"""
    payload = "<script>alert(1)</script>"
    pid = mkpost(client, body=payload).json()["post"]["id"]
    got = client.get(f"/api/posts/{pid}").json()["post"]["body"]
    assert got == payload


def test_sql_injection_in_search_is_safe(client):
    mkpost(client, title="정상 글")
    r = client.get("/api/posts", params={"q": "' OR 1=1 --"})
    assert r.status_code == 200 and r.json()["total"] == 0
    # 테이블이 살아있는지 확인
    assert client.get("/api/posts").json()["total"] == 1


def test_static_site_is_served(client):
    r = client.get("/index.html")
    assert r.status_code == 200
    assert "딩크라운지 피클볼 클럽" in r.text


def test_api_routes_not_shadowed_by_static_mount(client):
    assert client.get("/api/health").status_code == 200
