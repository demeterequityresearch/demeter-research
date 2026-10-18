"""Stock analysis reports의 최종본 PDF를 회원 전용 보관함(Supabase)에 올리고, 웹사이트 reports/ 에 목록(.json)을 남깁니다.

최종본은 각 기업 profile.json의 latest_reports(리포트 에이전트가 register_report()로 기록)를 따릅니다.
docx·초안·수정본(_수정, _검토 등)은 올리지 않고, 최종본과 같은 이름의 PDF만 올립니다.
PDF는 공개 저장소에 두지 않습니다(회원만 열람·다운로드, 2026-10-18). reports/ 에는 표준 파일명의 .json(제목 정보)만 남습니다.
보관함에 올릴 때 Supabase secret key가 필요합니다: 웹사이트 폴더의 .secrets.env (gitignore) 에
  SUPABASE_SECRET_KEY=sb_secret_...
한 줄을 사용자가 직접 넣어 둡니다. 이 키는 화면에 출력하거나 다른 곳에 복사하지 않습니다.

사용법 (웹사이트 폴더에서):
  python scripts/publish.py --list            올릴 수 있는 최종본 목록
  python scripts/publish.py 코세스             코세스의 모든 종류 최종본
  python scripts/publish.py 089890 --type BO  종목코드 + 종류(BO/WR/QR) 지정
  python scripts/publish.py --all             모든 기업의 최종본
  python scripts/publish.py --disclaimer      면책 문구만 다시 가져오기
올린 뒤 git commit & push 하면 사이트에 반영됩니다.

리포트 제목(헤드라인)은 원본 docx 첫 장의 'Equity Research | …' 줄 바로 다음 문단이다.
올릴 때 reports/<표준 파일명>.json 에 기록하고, scripts/convert.py가 front matter로 옮긴다.

면책 문구는 리포트와 한 벌이다: 원본은 Stock analysis reports/shared/report_utils.py의 DISCLAIMER_TEXT이고,
올릴 때마다(또는 --disclaimer) data/disclaimer.json으로 옮겨 바닥글(layouts/_partials/footer.html)이 읽는다.
"""
import argparse, ast, json, pathlib, re, sys, tomllib, urllib.error, urllib.parse, urllib.request

# 리포트 폴더는 이 웹사이트 폴더의 옆 폴더 (둘 다 Documents/Demeter Equity Research 아래)
SITE = pathlib.Path(__file__).resolve().parent.parent
STOCK = SITE.parent / "Stock analysis reports"
DEST = SITE / "reports"
SECRETS = SITE / ".secrets.env"
CODES = {"business_overview": "BO", "weekly_monitoring": "WR", "quarterly_review": "QR"}

sys.path.insert(0, str(SITE / "scripts"))
from convert import parse  # noqa: E402  표준 파일명 -> 페이지 주소·보관함 파일 이름 (convert.py 한 곳에서 정함)


def sync_disclaimer():
    """report_utils.DISCLAIMER_TEXT를 문단별로 나눠 data/disclaimer.json에 쓴다 (python-docx 없이 문자열만 읽음)."""
    src = STOCK / "shared" / "report_utils.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    text = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and any(getattr(t, "id", None) == "DISCLAIMER_TEXT" for t in n.targets))
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    data = {"ko": [p for p in paras if re.search(r"[가-힣]", p)],
            "en": [p for p in paras if not re.search(r"[가-힣]", p)]}
    out = SITE / "data" / "disclaimer.json"
    out.parent.mkdir(exist_ok=True)
    new = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if not out.is_file() or out.read_text(encoding="utf-8") != new:
        out.write_text(new, encoding="utf-8")
        print(f"[면책 문구] data/disclaimer.json 갱신 <- {src.relative_to(STOCK).as_posix()}")


def headline(docx_path):
    """docx 첫 장의 헤드라인. 'Equity Research | 종류 | 업종' 줄 바로 다음 문단 (없으면 None)."""
    try:
        import docx
    except ImportError:
        print("[주의] python-docx가 없어 리포트 제목을 읽지 못했습니다 (pip install python-docx)")
        return None
    paras = [p.text.strip() for p in docx.Document(docx_path).paragraphs if p.text.strip()][:6]
    for a, b in zip(paras, paras[1:]):
        if a.startswith("Equity Research") and "|" in a:
            return re.sub(r"\s+", " ", b)
    return None


def secret_key():
    """.secrets.env의 SUPABASE_SECRET_KEY (값은 출력하지 않음)"""
    if SECRETS.is_file():
        for line in SECRETS.read_text(encoding="utf-8-sig").splitlines():
            k, _, v = line.partition("=")
            if k.strip() == "SUPABASE_SECRET_KEY" and v.strip():
                return v.strip()
    sys.exit("Supabase secret key가 없습니다. 웹사이트 폴더의 .secrets.env 에 SUPABASE_SECRET_KEY=sb_secret_... 를 넣어 주세요.")


def upload(pdf, name, key):
    """PDF를 회원 전용 보관함(hugo.toml params.supabase.bucket)에 name으로 올림 (같은 이름이면 덮어씀)"""
    sb = tomllib.loads((SITE / "hugo.toml").read_text(encoding="utf-8"))["params"]["supabase"]
    url = f'{sb["url"]}/storage/v1/object/{sb["bucket"]}/{urllib.parse.quote(name)}'
    req = urllib.request.Request(url, data=pdf.read_bytes(), method="POST", headers={
        "apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/pdf", "x-upsert": "true"})
    try:
        urllib.request.urlopen(req, timeout=120).close()
    except urllib.error.HTTPError as e:
        sys.exit(f"보관함에 올리지 못했습니다 ({e.code}): {e.read().decode('utf-8', 'replace')[:300]}")


def companies():
    """(회사명, 종목코드, profile) 목록. 폴더 이름은 <종목코드>_<회사명>."""
    out = []
    for d in sorted((STOCK / "_data" / "companies").iterdir()):
        p = d / "profile.json"
        if d.is_dir() and p.is_file():
            code, name = d.name.split("_", 1)
            out.append((name, code, json.loads(p.read_text(encoding="utf-8"))))
    return out


def candidates(name, code, prof, types):
    """최종본마다 (원본 PDF, 웹사이트용 표준 파일명(확장자 없음), 원본 경로) — PDF가 없으면 원본 PDF는 None."""
    for agent, entry in (prof.get("latest_reports") or {}).items():
        t = CODES.get(agent)
        if not t or (types and t not in types) or not entry.get("report"):
            continue
        src = (STOCK / entry["report"]).with_suffix(".pdf")
        m = re.match(r"(\d{8})", src.name)
        date = m.group(1) if m else entry.get("date", "").replace("-", "")
        parts = [date, name, code, t]
        if t == "QR" and entry.get("period"):
            # '2026 3Q' 또는 '2026Q3' -> '2026Q3'
            q = re.search(r"(\d{4})\s*(?:Q(\d)|(\d)Q)", entry["period"])
            if q:
                parts.append(f"{q.group(1)}Q{q.group(2) or q.group(3)}")
        yield (src if src.is_file() else None), "_".join(parts), entry["report"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("company", nargs="?", help="회사명 또는 종목코드")
    ap.add_argument("--type", action="append", choices=list(CODES.values()), help="BO / WR / QR (여러 번 가능)")
    ap.add_argument("--all", action="store_true", help="모든 기업")
    ap.add_argument("--list", action="store_true", help="목록만 보기")
    ap.add_argument("--disclaimer", action="store_true", help="면책 문구만 다시 가져오기")
    a = ap.parse_args()
    if not (a.company or a.all or a.list or a.disclaimer):
        ap.error("회사명·종목코드, --all, --list, --disclaimer 중 하나가 필요합니다")
    if not a.list:
        sync_disclaimer()
    if a.disclaimer and not (a.company or a.all):
        return

    targets = [c for c in companies() if a.all or a.list or a.company in (c[0], c[1])]
    if not targets:
        sys.exit(f"'{a.company}'에 해당하는 기업 프로필이 없습니다 (Stock analysis reports/_data/companies)")

    DEST.mkdir(exist_ok=True)
    key = None
    for name, code, prof in targets:
        for src, stem, report in candidates(name, code, prof, a.type):
            entry = DEST / f"{stem}.json"
            if a.list:
                state = "게시됨" if entry.is_file() else ("PDF 있음" if src else "PDF 없음")
                print(f"[{state}] {stem}  <-  {report}")
                continue
            if not src:
                print(f"[건너뜀] PDF가 없습니다: {report}")
                continue
            file = parse(stem)[1]["file"]
            key = key or secret_key()
            upload(src, file, key)
            print(f"[보관함] {file}  <-  {src.relative_to(STOCK).as_posix()}")
            doc = (STOCK / report).with_suffix(".docx")
            h = headline(doc) if doc.is_file() else None
            entry.write_text(json.dumps({"headline": h} if h else {}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"[목록] reports/{entry.name}" + (f"  제목: {h}" if h else "  (제목을 찾지 못함: 기본 이름으로 표시)"))


if __name__ == "__main__":
    main()
