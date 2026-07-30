# 배포 가이드 — GitHub Pages + 도메인 연결

**선택한 방식: GitHub Pages** (정적 배포 / 관리자 페이지는 데모 모드로 동작)

> ⚠️ **저장소를 Public 으로 전환해야 합니다.** 무료 플랜에서 Private 저장소는 Pages 배포가 되지 않습니다.
> 전환 전에 아래 **"공개 전 점검"** 을 먼저 읽어 주세요.

## 순서 요약

```
1. 공개 전 점검 (아래)         →  2. 저장소 Public 전환
3. Settings → Pages 설정        →  4. 도메인 구입 + DNS 연결
5. python set-domain.py 도메인  →  6. commit & push  →  끝
```

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

---

## 공개 전 점검 (Public 전환 전에 반드시)

저장소를 공개하면 **코드와 커밋 히스토리 전체가 전 세계에 공개**됩니다. 아래는 점검 완료 항목입니다.

| 항목 | 상태 |
|---|---|
| 실제 비밀값(토큰·API 키·인증서) | ✅ 없음 — 전체 히스토리 스캔 완료 |
| `data/*.db` (신청자 개인정보) | ✅ 한 번도 커밋된 적 없음 (`.gitignore`) |
| `.env` 실제 파일 | ✅ 없음 (`.env.example` 만 존재) |
| `changeme-dev-token` | ⚠️ 개발 기본값이며 공개돼도 무해. **단 실서버에서는 반드시 변경** |
| 관리자 데모 비밀번호 `demo` | ⚠️ 공개 전제 — 데모 데이터만 보이므로 보안 목적 아님 |

**직접 판단하셔야 할 두 가지**

1. **커밋 작성자 이메일이 공개됩니다** — 현재 `leechangkoo2128@gmail.com` 으로 기록돼 있습니다.
   숨기시려면 Public 전환 **전에** 아래를 실행하세요. (GitHub 이 제공하는 noreply 주소로 교체)

   ```bash
   git config user.email "TripdocCEO@users.noreply.github.com"
   git rebase -r --root --exec "git commit --amend --no-edit --reset-author"
   git push --force-with-lease
   ```
   GitHub → Settings → Emails → *Keep my email addresses private* 도 함께 켜 두시면 좋습니다.

2. **플레이스홀더 정보가 공개됩니다** — `○○로 00`, `051-000-0000`, 예시 요금, AI 생성 히어로 이미지.
   실제 정보가 아니어서 위험하진 않지만, 검색에 잡히기 전에 교체하시는 편이 낫습니다.

---

## 방법 A. GitHub Pages ← **선택하신 방식**

`.github/workflows/pages.yml` 은 이미 커밋돼 있습니다. 저장소만 공개로 바꾸면 됩니다.

### 1) 저장소 Public 전환
**Settings → General → 맨 아래 Danger Zone → Change repository visibility → Make public**

### 2) Pages 활성화
**Settings → Pages → Build and deployment → Source** 를 **`GitHub Actions`** 로 선택

전환 직후 워크플로가 자동으로 돌고, **Actions** 탭에서 진행 상황을 볼 수 있습니다.
1~2분 뒤 `https://tripdocceo.github.io/pickleball/` 에서 사이트가 열립니다.

### 3) 도메인 연결
1. 도메인 구입 (가비아·후이즈·Cloudflare Registrar 등)
2. DNS 설정
   - **서브도메인**(`www.도메인.com`) → `CNAME` 레코드를 `tripdocceo.github.io` 로
   - **최상위**(`도메인.com`) → `A` 레코드 4개
     `185.199.108.153` / `185.199.109.153` / `185.199.110.153` / `185.199.111.153`
3. **Settings → Pages → Custom domain** 에 도메인 입력 후 Save
4. DNS 전파(수분~수시간) 후 **Enforce HTTPS** 체크

### 4) 사이트에 도메인 반영
JSON-LD·robots·sitemap 안의 `example.com` 을 한 번에 바꿉니다.

```bash
python set-domain.py 도메인.com
git add -A && git commit -m "chore: 도메인 설정" && git push
```

`public/CNAME` 파일도 자동 생성되어 Pages 커스텀 도메인 설정이 유지됩니다.

> 💡 **커스텀 도메인 없이 `github.io/pickleball/` 만 쓰실 경우**
> `robots.txt` 는 도메인 최상위에 있어야 크롤러가 읽습니다. 서브경로에서는 무시되니
> 검색 노출까지 챙기시려면 커스텀 도메인을 붙이시는 걸 권합니다.
> 이 경우엔 `python set-domain.py tripdocceo.github.io/pickleball --no-cname` 로 실행하세요.

---

## 방법 B. Cloudflare Pages ← Private 저장소를 유지하고 싶다면

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

---

## 도메인 구입

| 등록기관 | 특징 |
|---|---|
| 가비아 / 후이즈 | 국내, 한국어 지원, `.co.kr` 가능 |
| Cloudflare Registrar | 원가 판매(마진 0), 방법 A와 궁합 좋음 |

추천 도메인 예시: `jeonggwan-pickleball.com`, `jgpickleball.kr`

---

## 배포 후 반드시 할 일

1. **도메인 반영** — `python set-domain.py 도메인.com` (JSON-LD·robots·sitemap·CNAME 일괄 처리)

2. **실제 정보 입력** — 전 페이지의 `○○로 00`, `051-000-0000`, 좌표(35.322/129.183), 요금
   기획서 §09대로 **네이버 플레이스·카카오맵과 글자 단위로 일치**시킬 것

3. **검색엔진 등록**
   - 네이버 서치어드바이저 → 사이트 등록 → `sitemap.xml` 제출
   - 구글 서치콘솔 → 속성 추가 → `sitemap.xml` 제출

4. **히어로 이미지 교체** — 현재 AI 생성본. `public/assets/hero.jpg` 를 실제 촬영본으로

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
