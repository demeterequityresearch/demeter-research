"""Stock analysis reports의 최종본 PDF를 웹사이트 reports/ 폴더로 가져옵니다.

최종본은 각 기업 profile.json의 latest_reports(리포트 에이전트가 register_report()로 기록)를 따릅니다.
docx·초안·수정본(_수정, _검토 등)은 가져오지 않고, 최종본과 같은 이름의 PDF만 표준 파일명으로 복사합니다.

사용법 (웹사이트 폴더에서):
  python scripts/publish.py --list            올릴 수 있는 최종본 목록
  python scripts/publish.py 코세스             코세스의 모든 종류 최종본
  python scripts/publish.py 089890 --type BO  종목코드 + 종류(BO/WR/QR) 지정
  python scripts/publish.py --all             모든 기업의 최종본
복사 후 git commit & push 하면 사이트에 반영됩니다.
"""
import argparse, json, pathlib, re, shutil, sys

STOCK = pathlib.Path.home() / "Documents" / "Stock analysis reports"
DEST = pathlib.Path(__file__).resolve().parent.parent / "reports"
CODES = {"business_overview": "BO", "weekly_monitoring": "WR", "quarterly_review": "QR"}


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
    """최종본마다 (원본 PDF, 웹사이트용 표준 파일명) — PDF가 없으면 원본 PDF는 None."""
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
        yield (src if src.is_file() else None), "_".join(parts) + ".pdf", entry["report"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("company", nargs="?", help="회사명 또는 종목코드")
    ap.add_argument("--type", action="append", choices=list(CODES.values()), help="BO / WR / QR (여러 번 가능)")
    ap.add_argument("--all", action="store_true", help="모든 기업")
    ap.add_argument("--list", action="store_true", help="목록만 보기")
    a = ap.parse_args()
    if not (a.company or a.all or a.list):
        ap.error("회사명·종목코드, --all, --list 중 하나가 필요합니다")

    targets = [c for c in companies() if a.all or a.list or a.company in (c[0], c[1])]
    if not targets:
        sys.exit(f"'{a.company}'에 해당하는 기업 프로필이 없습니다 (Stock analysis reports/_data/companies)")

    DEST.mkdir(exist_ok=True)
    for name, code, prof in targets:
        for src, dest_name, report in candidates(name, code, prof, a.type):
            if a.list:
                state = "게시됨" if (DEST / dest_name).is_file() else ("PDF 있음" if src else "PDF 없음")
                print(f"[{state}] {dest_name}  <-  {report}")
                continue
            if not src:
                print(f"[건너뜀] PDF가 없습니다: {report}")
                continue
            shutil.copy2(src, DEST / dest_name)
            print(f"[복사] {dest_name}  <-  {src.relative_to(STOCK).as_posix()}")


if __name__ == "__main__":
    main()
