# 배포 가이드 — Git 연동 + 도메인 연결

현재 선택: **정적 배포** (백엔드는 올리지 않고 화면만 공개, 관리자 페이지는 데모 모드로 동작)

---

## 지금 상태에서 되는 것 / 안 되는 것

| 기능 | 정적 배포 | 비고 |
|---|---|---|
| 23개 페이지 열람 | ✅ | 전부 정상 |
| 검색 노출(AEO) | ✅ | JSON-LD·sitemap·robots 포함 |
| 게시판 읽기·쓰기 | ⚠️ 데모 | 방문자 브라우저에만 저장, 서로 공유되지 않음 |
| **관리자 로그인** | ✅ **데모** | 비밀번호 `demo`, 예시 데이터로 화면 시연 가능 |
| 무료 체험 신청 접수 | ❌ | 폼은 뜨지만 저장되지 않음 (데모 안내 문구 표시) |

> 실제 신청을 **받아야 할 때**가 되면 Render 등 백엔드 호스팅으로 옮기면 됩니다.
> 코드 수정 없이 그대로 동작합니다 — 아래 "나중에 백엔드까지" 참고.

---

## 방법 A. Cloudflare Pages ← **Private 저장소 유지 가능, 추천**

저장소를 공개하지 않아도 되고, 도메인·HTTPS·트래픽 모두 무료입니다.

1. <https://dash.cloudflare.com> → **Workers & Pages** → **Create** → **Pages** → **Connect to Git**
2. GitHub 계정 연결 후 `TripdocCEO/pickleball` 선택
3. 빌드 설정 — **빌드 명령은 비워 두세요** (빌드 과정이 없는 정적 사이트입니다)

   | 항목 | 값 |
   |---|---|
   | Framework preset | `None` |
   | Build command | *(비움)* |
   | Build output directory | `public` |
   | Root directory | *(비움)* |

4. **Save and Deploy** → `xxx.pages.dev` 주소가 바로 생성됩니다
5. 도메인 연결: 프로젝트 → **Custom domains** → **Set up a domain** → 구입한 도메인 입력
   - 도메인을 Cloudflare에서 관리 중이면 DNS가 자동 설정됩니다
   - 가비아·후이즈 등 외부 등록기관이면 안내되는 CNAME 레코드를 그쪽 DNS에 추가

이후 `main` 브랜치에 push할 때마다 자동 재배포됩니다.

---

## 방법 B. GitHub Pages ← 저장소를 **Public** 으로 바꿔야 함

`.github/workflows/pages.yml` 을 이미 넣어 두었습니다.

1. 저장소 **Settings → General → Danger Zone → Change visibility → Public**
   (무료 플랜에서 Private 저장소는 Pages 배포가 되지 않습니다. GitHub Pro면 Private도 가능)
2. **Settings → Pages → Build and deployment → Source: GitHub Actions**
3. `main` 에 push하면 워크플로가 돌며 `public/` 폴더가 배포됩니다
4. 도메인 연결: **Settings → Pages → Custom domain** 에 도메인 입력 후 저장
   - DNS에 `CNAME` → `tripdocceo.github.io` 추가 (apex 도메인이면 A 레코드 4개)
   - 저장하면 저장소에 `CNAME` 파일이 자동 생성됩니다

> ⚠️ Public 전환 전에 아래 "공개 전 정리" 항목을 먼저 처리하세요.

---

## 도메인 구입

| 등록기관 | 특징 |
|---|---|
| 가비아 / 후이즈 | 국내, 한국어 지원, `.co.kr` 가능 |
| Cloudflare Registrar | 원가 판매(마진 0), 방법 A와 궁합 좋음 |

추천 도메인 예시: `jeonggwan-pickleball.com`, `jgpickleball.kr`

---

## 배포 후 반드시 할 일

1. **도메인 치환** — `public/robots.txt`, `public/sitemap.xml` 의 `example.com` 을 실제 도메인으로

   ```bash
   cd public && sed -i 's|https://example.com|https://실제도메인|g' robots.txt sitemap.xml
   ```

2. **JSON-LD 안의 `https://example.com`** 도 동일하게 교체 (각 페이지 `<script type="application/ld+json">`)

3. **실제 정보 입력** — 전 페이지의 `○○로 00`, `051-000-0000`, 좌표(35.322/129.183), 요금
   기획서 §09대로 **네이버 플레이스·카카오맵과 글자 단위로 일치**시킬 것

4. **검색엔진 등록**
   - 네이버 서치어드바이저 → 사이트 등록 → `sitemap.xml` 제출
   - 구글 서치콘솔 → 속성 추가 → `sitemap.xml` 제출

5. **히어로 이미지 교체** — 현재 AI 생성본. `public/assets/hero.jpg` 를 실제 촬영본으로

---

## 공개 전 정리 (저장소를 Public 으로 바꿀 경우)

저장소에 실제 비밀값은 없지만, 공개 전 아래를 확인하세요.

- [ ] `.env.example` — 예시값만 있는지 (실제 토큰 넣지 말 것)
- [ ] `data/*.db` 가 `.gitignore` 로 빠져 있는지 → **실제 신청자 개인정보가 저장소에 올라가면 안 됩니다**
- [ ] 관리자 데모 비밀번호(`admin.html` 의 `DEMO_PASS`)는 공개돼도 무방한 값인지
      (데모 데이터만 보이므로 보안 목적이 아닙니다)

---

## 나중에 백엔드까지 올리려면 (Render)

신청 접수를 실제로 받게 될 때:

1. <https://render.com> → New → **Web Service** → Private 저장소 그대로 연결
2. 설정
   - Runtime: `Python 3`
   - Build command: `pip install fastapi "uvicorn[standard]"`
   - Start command: `uvicorn server.main:app --host 0.0.0.0 --port $PORT`
3. 환경변수: `JGPC_ADMIN_TOKEN`, `JGPC_IP_SALT`, `JGPC_ORIGINS=https://실제도메인`
4. **Persistent Disk 를 `/opt/render/project/src/data` 에 붙일 것**
   — 붙이지 않으면 재배포 때마다 신청 내역이 사라집니다
5. 도메인을 Render 쪽으로 옮기면 관리자 페이지가 자동으로 실서버 모드로 전환됩니다
   (코드 수정 불필요 — `/api/health` 응답 여부로 판단)
