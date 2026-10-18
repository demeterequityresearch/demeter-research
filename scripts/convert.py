"""reports/ 폴더의 .docx / .pdf 를 Hugo 페이지로 변환합니다.

파일명 규칙 (Stock analysis reports와 공통, 2026-10-18):
  <YYYYMMDD>_<회사명>_<종목코드>_<BO|WR|QR>[_<기간>][_vN].pdf
  예: 20261018_코세스_089890_BO_v5.pdf      ->  '코세스 사업 개요', /reports/20261018-089890-bo/
      20261115_코세스_089890_QR_2026Q3.pdf  ->  '코세스 2026 3Q 실적 리뷰', /reports/20261115-089890-qr-2026q3/
같은 리포트의 버전이 여러 개 있으면 가장 높은 버전만 올립니다.
규칙에 맞지 않는 이름(예: 2026-10-18_제목.pdf)은 날짜와 제목만 읽습니다.
같은 이름의 docx와 pdf가 함께 있으면 본문은 docx, PDF는 다운로드 링크로 붙습니다.
"""
import pathlib, re, shutil, subprocess

SRC = pathlib.Path("reports")
DST = pathlib.Path("content/reports")

TYPES = {
    "BO": ("사업 개요", "Business Overview"),
    "WR": ("주간 리포트", "Weekly Report"),
    "QR": ("실적 리뷰", "Quarterly Review"),
}
STD = re.compile(
    r"(?P<date>\d{8}|\d{4}-\d{2}-\d{2})_(?P<company>[^_]+)_(?P<code>\d[0-9A-Z]{4}\d)_(?P<type>BO|WR|QR)"
    r"(?:_(?P<period>\d{4}Q[1-4]))?(?:_v(?P<ver>\d+))?"
)

# 리포트가 하나도 없어도 메뉴의 '리포트' 목록 페이지가 404가 나지 않도록 섹션 페이지를 만들어 둡니다
DST.mkdir(parents=True, exist_ok=True)
(DST / "_index.md").write_text('---\ntitle: "리포트"\n---\n', encoding="utf-8")


def parse(stem):
    """파일 이름 -> (페이지 폴더 이름, 버전, front matter 값)"""
    m = STD.fullmatch(stem)
    if m:
        d = m["date"].replace("-", "")
        date = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        ko, en = TYPES[m["type"]]
        period = m["period"]
        # 기간 2026Q3 -> 제목에는 국내 표기 '2026 3Q'
        title = f'{m["company"]} {period[:4]} {period[5]}Q {ko}' if period else f'{m["company"]} {ko}'
        slug = "-".join(filter(None, [d, m["code"], m["type"].lower(), (period or "").lower()]))
        meta = {"title": title, "date": date, "company": m["company"], "code": m["code"],
                "type": m["type"], "typeName": en}
        if period:
            meta["period"] = period
        return slug, int(m["ver"] or 1), meta
    # 예전 형식: 2026-10-18_제목
    m = re.match(r"(\d{4}-\d{2}-\d{2})_(.+)", stem)
    date, title = (m.group(1), m.group(2)) if m else (None, stem)
    meta = {"title": title.replace("_", " ")}
    if date:
        meta["date"] = date
    return stem, 1, meta


# 같은 리포트(같은 폴더 이름)끼리 모으고, 버전이 가장 높은 파일들만 남깁니다
reports = {}
for f in SRC.iterdir():
    ext = f.suffix.lower()
    if ext not in (".docx", ".pdf"):
        continue
    slug, ver, meta = parse(f.stem)
    cur = reports.get(slug)
    if cur is None or ver > cur["ver"]:
        reports[slug] = {"ver": ver, "meta": meta, "files": {ext: f}}
    elif ver == cur["ver"]:
        cur["files"][ext] = f

for slug, r in sorted(reports.items()):
    files, meta = r["files"], r["meta"]
    bundle = DST / slug
    shutil.rmtree(bundle, ignore_errors=True)
    bundle.mkdir(parents=True)

    front = "---\n" + "".join(
        f"{k}: {v}\n" if k == "date" else f'{k}: "{v}"\n' for k, v in meta.items()
    ) + "---\n\n"

    body = ""
    if ".docx" in files:
        # 이미지는 페이지 번들 안의 media/ 로 추출되어 상대경로로 연결됩니다
        body = subprocess.run(
            ["pandoc", str(files[".docx"].resolve()), "-t", "gfm", "--extract-media=."],
            cwd=bundle, capture_output=True, text=True, check=True,
        ).stdout
    if ".pdf" in files:
        shutil.copy(files[".pdf"], bundle / "report.pdf")
        if not body:
            body = '<iframe src="report.pdf" width="100%" height="900" style="border:0"></iframe>\n\n'
        body += f'\n\n<a href="report.pdf" download="{files[".pdf"].name}">📄 PDF 다운로드</a>\n'

    (bundle / "index.md").write_text(front + body, encoding="utf-8")
    print(f"converted: {slug}  <-  {', '.join(sorted(p.name for p in files.values()))}")
