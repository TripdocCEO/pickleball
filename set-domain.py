"""
도메인 일괄 설정 스크립트

사이트 곳곳에 들어 있는 example.com 을 실제 도메인으로 바꾸고,
GitHub Pages 커스텀 도메인용 CNAME 파일까지 만들어 줍니다.

사용법:
    python set-domain.py jeonggwan-pickleball.com

    # 커스텀 도메인 없이 github.io 주소를 쓸 경우
    python set-domain.py tripdocceo.github.io/pickleball --no-cname

바꾸는 곳: public/*.html 의 JSON-LD, robots.txt, sitemap.xml
"""
import io
import os
import re
import sys

# Windows 기본 콘솔(cp949)에서 한글·기호 출력이 깨지지 않도록
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))
PUB = os.path.join(ROOT, "public")
OLD = "https://example.com"


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    make_cname = "--no-cname" not in sys.argv

    if not args:
        print(__doc__)
        return 1

    domain = args[0].strip().rstrip("/")
    domain = re.sub(r"^https?://", "", domain)
    if not domain or " " in domain:
        print(f"[오류] 도메인 형식이 올바르지 않습니다: {args[0]}")
        return 1

    new = "https://" + domain
    changed, total = [], 0

    targets = [os.path.join(PUB, f) for f in sorted(os.listdir(PUB))
               if f.endswith((".html", ".txt", ".xml"))]

    for path in targets:
        with io.open(path, encoding="utf-8") as f:
            s = f.read()
        n = s.count(OLD)
        if not n:
            continue
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(s.replace(OLD, new))
        changed.append((os.path.basename(path), n))
        total += n

    # GitHub Pages 커스텀 도메인 (apex/서브도메인일 때만 의미 있음)
    cname_path = os.path.join(PUB, "CNAME")
    if make_cname and "/" not in domain and not domain.endswith("github.io"):
        with io.open(cname_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(domain + "\n")
        print(f"[완료] CNAME 생성: public/CNAME → {domain}")
    elif os.path.exists(cname_path) and not make_cname:
        os.remove(cname_path)
        print("[삭제] 기존 public/CNAME 삭제")

    if not changed:
        print("[안내] 바꿀 example.com 이 없습니다. (이미 적용된 상태일 수 있습니다)")
    else:
        print(f"[완료] {new} 로 {total}곳 치환 — 파일 {len(changed)}개")
        for name, n in changed:
            print(f"   · {name} ({n})")

    print("\n다음 단계:")
    print("  git add -A && git commit -m \"chore: 도메인 설정\" && git push")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
