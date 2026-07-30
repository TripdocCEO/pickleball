# 딩크라운지 피클볼 클럽 — 웹사이트 (프런트 + 백엔드 + DB)

부산 기장군 정관 실내 피클볼 클럽의 공식 웹사이트입니다.
정적 페이지 22개 + 커뮤니티 게시판 + 무료 체험 신청 접수 기능을 포함합니다.

---

## 빠른 시작

```
run.bat  더블클릭
```

- 사이트: <http://localhost:8000>
- **관리자 페이지: <http://localhost:8000/admin.html>**
- API 문서(Swagger): <http://localhost:8000/api/docs>

처음 실행하면 가상환경 생성 → 패키지 설치 → 초기 데이터 주입까지 자동으로 진행됩니다.

### 수동 실행

```bash
uv venv
uv pip install fastapi "uvicorn[standard]" pytest httpx
.venv\Scripts\python.exe server\seed.py
.venv\Scripts\python.exe -m uvicorn server.main:app --port 8000
```

---

## 폴더 구조

```
app/
├─ server/
│  ├─ main.py       API + 정적 서빙 (FastAPI)
│  ├─ db.py         SQLite 커넥션 헬퍼
│  ├─ schema.sql    테이블 정의
│  └─ seed.py       초기 게시글 주입 (중복 실행 안전)
├─ public/          웹사이트 22페이지 + assets/
├─ tests/
│  └─ test_api.py   API 테스트 46건
├─ data/club.db     SQLite 파일 (자동 생성, 백업 대상)
├─ .env.example     환경변수 예시
├─ run.bat          원클릭 실행
└─ QA-리포트.md     QA 결과
```

---

## 데이터베이스

SQLite (WAL 모드). 파일 하나라 **복사만으로 백업**됩니다.

| 테이블 | 용도 | 비고 |
|---|---|---|
| `posts` | 게시글 | 소프트 삭제(`deleted`), 고정(`pinned`) |
| `comments` | 댓글 | 글 삭제 시 CASCADE |
| `post_likes` | 좋아요 | (글, 클라이언트) 복합키로 중복 차단 |
| `trials` | **무료 체험 신청** | 상태: new → contacted → booked → done |
| `write_log` | 쓰기 로그 | 레이트리밋용, IP는 해시로만 저장 |
| `schema_meta` | 스키마 버전 | 마이그레이션 기준 |

백업 예시:
```bash
copy data\club.db backup\club-20260729.db
```

---

## API

인증이 필요한 엔드포인트는 `x-admin-token` 헤더를 사용합니다.

| 메서드 | 경로 | 설명 | 인증 |
|---|---|---|---|
| GET | `/api/health` | 상태 확인 | – |
| GET | `/api/posts` | 목록 (분류·검색·정렬·페이지) | – |
| GET | `/api/posts/{id}` | 상세 + 댓글 (조회수 +1) | – |
| POST | `/api/posts` | 글쓰기 | – |
| POST | `/api/posts/{id}/comments` | 댓글 | – |
| POST | `/api/posts/{id}/like` | 좋아요 | – |
| DELETE | `/api/posts/{id}` | 글 삭제(소프트) | 🔑 |
| POST | `/api/trials` | 무료 체험 신청 | – |
| GET | `/api/admin/verify` | 토큰 확인(관리자 로그인) | 🔑 |
| GET | `/api/admin/trials` | 신청 목록 | 🔑 |
| PATCH | `/api/admin/trials/{id}` | 신청 상태·메모 변경 | 🔑 |
| GET | `/api/admin/posts` | 글 목록(삭제글 포함) | 🔑 |
| PATCH | `/api/admin/posts/{id}/pin` | 상단 고정/해제 | 🔑 |
| POST | `/api/admin/posts/{id}/restore` | 삭제 글 복구 | 🔑 |
| GET | `/api/admin/stats` | 글·댓글·신청 통계 | 🔑 |

---

## 관리자 페이지 — <http://localhost:8000/admin.html>

운영에 필요한 일은 이 화면에서 전부 처리할 수 있습니다. 로그인은 관리자 토큰
(`JGPC_ADMIN_TOKEN`, 기본값 `changeme-dev-token`) 하나만 입력하면 됩니다.
토큰은 브라우저 세션에만 저장되어 탭을 닫으면 사라집니다.

**대시보드**
- 확인 필요한 신규 신청 / 최근 7일 / 누적 신청 / 게시판 현황 4개 카드

**🎾 무료 체험 신청 관리**
- 이름·연락처·희망 시간·인원·경험 한눈에 확인 (연락처는 눌러서 바로 전화)
- 상태 5단계 관리: 🆕 신규 → 📞 연락함 → 📅 예약확정 → ✅ 방문완료 / ✖ 취소
- 상태별 필터, 건별 메모 (예: "무릎 통증 있음 — 저강도 안내")
- **CSV 내려받기** — 엑셀에서 한글이 깨지지 않도록 BOM 포함

**💬 게시판 관리**
- 삭제된 글까지 포함한 전체 목록
- 공지 **상단 고정 / 해제**
- 글 삭제(숨김 처리)와 **복구** — 실수로 지워도 되돌릴 수 있습니다

> ⚠️ 관리자 페이지 주소는 공개되어 있지만 토큰 없이는 아무 데이터도 보이지 않습니다.
> 더 강하게 막으려면 리버스 프록시에서 IP 제한이나 Basic Auth를 추가하세요.
> 검색 색인에서는 `noindex` 로 제외되어 있습니다.

### 터미널에서 확인하기 (선택)

```bash
curl -H "x-admin-token: 발급받은토큰" http://localhost:8000/api/admin/trials
```

---

## 오프라인(데모) 모드

서버 없이 `public/index.html`을 그냥 열어도 사이트가 동작합니다.
게시판은 이때 **데모 모드**로 전환되어 브라우저 저장소에 임시 저장되며, 화면 상단에 `● 데모 모드` 배지가 표시됩니다.
서버가 켜져 있으면 자동으로 `● 서버 연결됨`으로 바뀌고 DB에 저장됩니다.

---

## 배포 전 체크리스트

- [ ] `JGPC_ADMIN_TOKEN` 을 긴 랜덤 문자열로 교체
- [ ] `JGPC_IP_SALT` 교체
- [ ] `JGPC_ORIGINS` 를 실제 도메인으로 설정
- [ ] HTTPS 적용 (Nginx/Caddy 리버스 프록시)
- [ ] `public/` 안의 `○○로 00`, `051-000-0000`, 요금·좌표를 실제 값으로 교체
- [ ] 네이버 플레이스·카카오맵과 상호·주소·전화번호 **글자 단위 일치** (기획서 §09)
- [ ] 예시 사진을 실제 촬영본으로 교체 (`public/assets/README.md` 참고)
- [ ] 네이버 서치어드바이저 · 구글 서치콘솔 등록, sitemap.xml · robots.txt 추가
- [ ] `data/club.db` 정기 백업 스케줄

---

## 테스트

```bash
.venv\Scripts\python.exe -m pytest -v      # 46건
```

결과는 [QA-리포트.md](QA-리포트.md) 참고.
