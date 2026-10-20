"""Stock analysis reports의 최종본 PDF를 게시합니다: ../Published에 영구 보관 → Cloudflare R2(회원 전용)에 올림 → reports/ 에 목록(.json).

최종본은 각 기업 profile.json의 latest_reports(리포트 에이전트가 register_report()로 기록)를 따릅니다.
docx·초안·수정본(_수정, _검토 등)은 올리지 않고, 최종본과 같은 이름의 PDF만 올립니다.
PDF는 공개 저장소에 두지 않습니다(회원만 열람, 2026-10-18). reports/ 에는 표준 파일명의 .json(제목 정보)만 남습니다.

보관(2026-10-19 사용자 결정):
  - ../Published/<종목코드>_<회사명>/<BO|WU|QR>/<표준 파일명>.pdf 에 모든 게시본을 남김 (지우지 않음)
  - R2에는 종목별로 KEEP 개수(BO 5, QR 8, WU 12)만 둠. 넘으면 가장 오래된 것을 R2와 reports/*.json 둘 다에서 지움
    (사이트에는 R2에 있는 리포트만 보임). 같은 날짜·종류를 다시 올리면 덮어씀
R2에 올릴 때 Cloudflare API 토큰이 필요합니다: .secrets.env의 CLOUDFLARE_API_TOKEN (scripts/cloudflare.py, 출력하지 않음)

사용법 (웹사이트 폴더에서):
  python scripts/publish.py --list            올릴 수 있는 최종본 목록
  python scripts/publish.py 코세스             코세스의 모든 종류 최종본
  python scripts/publish.py 089890 --type BO  종목코드 + 종류(BO/WU/QR) 지정
  python scripts/publish.py --all             모든 기업의 최종본
  python scripts/publish.py --profiles        회사 정보(data/companies/*.json)만 다시 만듦 (게시된 회사)
올린 뒤 git commit & push 하면 사이트에 반영됩니다.

리포트 제목(헤드라인)은 원본 docx 첫 장의 'Equity Research | …' 줄 바로 다음 문단이다.
올릴 때 reports/<표준 파일명>.json 에 기록하고, scripts/convert.py가 front matter로 옮긴다.

회사 페이지의 회사 정보(2026-10-20): 리포트를 올릴 때 profile.json에서 공개해도 되는 항목만 골라 data/companies/<종목코드>.json에 씀.
사실 위주(업종·사업 구성·주요 고객·비교 기업·성장 요인·위험의 이름). 전망 표시(outlook)·가능성 평가, 지켜볼 지표(외부 추정치가 섞임),
고객 메모 같은 내부 분석 메모는 넣지 않음. 회사 페이지는 로그인 없이 공개되므로 항목을 늘릴 때 같은 기준으로 고를 것.

사이트 바닥글의 면책 문구는 리포트와 따로 쓴다(2026-10-20 사용자 결정): data/disclaimer.json을 이 폴더에서 직접 고친다.
리포트 Disclaimer(report_utils.DISCLAIMER_TEXT)와 핵심(투자 권유 아님, 목표주가·투자의견 미제시, 책임은 투자자)은 같게 유지한다.
"""
import argparse, json, pathlib, re, shutil, sys

# 리포트 폴더는 이 웹사이트 폴더의 옆 폴더 (둘 다 Documents/Demeter Equity Research 아래)
SITE = pathlib.Path(__file__).resolve().parent.parent
STOCK = SITE.parent / "Stock analysis reports"
DEST = SITE / "reports"
PUBLISHED = SITE.parent / "Published"
CODES = {"business_overview": "BO", "weekly_update": "WU", "quarterly_review": "QR"}
KEEP = {"BO": 5, "QR": 8, "WU": 12}  # R2·사이트에 남기는 종목별 개수

sys.path.insert(0, str(SITE / "scripts"))
from convert import parse  # noqa: E402  표준 파일명 -> 페이지 주소·보관함 파일 이름 (convert.py 한 곳에서 정함)
from cloudflare import r2_delete, r2_put  # noqa: E402


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


def prune(code, type_):
    """R2·사이트에 같은 종목·종류가 KEEP개를 넘으면 가장 오래된 것부터 지움 (Published에는 남음)"""
    entries = []
    for f in DEST.glob("*.json"):
        p = parse(f.stem)
        if p and p[1]["code"] == code and p[1]["reportType"] == type_:
            entries.append((f.stem, f, p[1]["file"]))
    entries.sort(reverse=True)  # 표준 파일명은 날짜로 시작하므로 이름순 = 날짜순
    for _, f, key in entries[KEEP[type_]:]:
        r2_delete(key)
        f.unlink()
        print(f"[정리] {f.stem}: 보관 개수({KEEP[type_]}개)를 넘어 R2와 사이트 목록에서 뺌 (Published에는 남음)")


def companies():
    """(회사명, 종목코드, profile) 목록. 폴더 이름은 <종목코드>_<회사명>."""
    out = []
    for d in sorted((STOCK / "_data" / "companies").iterdir()):
        p = d / "profile.json"
        if d.is_dir() and p.is_file():
            code, name = d.name.split("_", 1)
            out.append((name, code, json.loads(p.read_text(encoding="utf-8"))))
    return out


def customer_names(c):
    """주요 고객 이름 목록. profile마다 형식이 다름: {"key": [이름...]} 또는 [{"name": ...}, ...]"""
    if isinstance(c, dict):
        c = c.get("key") or []
    return [x.get("name") if isinstance(x, dict) else x for x in c or [] if x]


def export_profile(code, prof):
    """profile.json에서 공개 항목만 data/companies/<종목코드>.json에 씀 (회사 페이지, 로그인 없이 공개)"""
    co, ind = prof.get("company") or {}, prof.get("industry") or {}
    card = {
        "market": co.get("market"),
        "homepage": co.get("homepage"),
        "industry": ind.get("primary"),
        "definition": ind.get("definition"),
        "secondary": ind.get("secondary") or [],
        "segments": [{"name": s["name"], "share": s.get("revenue_share_pct"), "basis": s.get("basis")}
                     for s in prof.get("segments") or [] if s.get("name")],
        "customers": customer_names(prof.get("customers")),
        "peers": [{"name": p["name"], "code": p.get("stock_code"), "market": p.get("market")}
                  for p in prof.get("peers") or [] if p.get("name")],
        "drivers": [d["driver"] for d in prof.get("growth_drivers") or [] if d.get("driver")],
        "risks": [r["risk"] for r in prof.get("risks") or [] if r.get("risk")],
    }
    out = SITE / "data" / "companies" / f"{code}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[회사 정보] data/companies/{code}.json")


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
    ap.add_argument("--type", action="append", choices=list(CODES.values()), help="BO / WU / QR (여러 번 가능)")
    ap.add_argument("--all", action="store_true", help="모든 기업")
    ap.add_argument("--list", action="store_true", help="목록만 보기")
    ap.add_argument("--profiles", action="store_true", help="게시된 회사의 회사 정보만 다시 만듦")
    a = ap.parse_args()
    if not (a.company or a.all or a.list or a.profiles):
        ap.error("회사명·종목코드, --all, --list, --profiles 중 하나가 필요합니다")

    if a.profiles:
        published = {parse(f.stem)[1]["code"] for f in DEST.glob("*.json") if parse(f.stem)}
        for name, code, prof in companies():
            if code in published:
                export_profile(code, prof)
        return

    targets = [c for c in companies() if a.all or a.list or a.company in (c[0], c[1])]
    if not targets:
        sys.exit(f"'{a.company}'에 해당하는 기업 프로필이 없습니다 (Stock analysis reports/_data/companies)")

    DEST.mkdir(exist_ok=True)
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
            meta = parse(stem)[1]
            keep = PUBLISHED / f"{code}_{name}" / meta["reportType"] / f"{stem}.pdf"
            keep.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, keep)
            print(f"[Published] {keep.relative_to(SITE.parent).as_posix()}  <-  {src.relative_to(STOCK).as_posix()}")
            r2_put(meta["file"], src)
            print(f"[R2] {meta['file']}")
            doc = (STOCK / report).with_suffix(".docx")
            h = headline(doc) if doc.is_file() else None
            entry.write_text(json.dumps({"headline": h} if h else {}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"[목록] reports/{entry.name}" + (f"  제목: {h}" if h else "  (제목을 찾지 못함: 기본 이름으로 표시)"))
            prune(code, meta["reportType"])
            export_profile(code, prof)


if __name__ == "__main__":
    main()
