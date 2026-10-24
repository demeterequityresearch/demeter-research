"""reports/ 폴더의 리포트 목록(.json)을 Hugo 페이지로 변환합니다.

리포트 PDF는 공개 저장소에 두지 않습니다(회원만 열람, 2026-10-18). scripts/publish.py가 PDF를 Supabase 비공개 보관함에 올리고,
reports/ 에는 표준 파일명의 작은 .json(제목 정보)만 남깁니다. 페이지는 보관함의 PDF를 로그인한 회원에게만 보여 줍니다.

파일명 규칙 (Stock analysis reports와 공통, 2026-10-18):
  <YYYYMMDD>_<회사명>_<종목코드>_<BO|WU|QR>[_<기간>].json
  예: 20261018_코세스_089890_BO.json         ->  '코세스 기업 분석', /reports/20261018-089890-bo/, 보관함 20261018-089890-bo.pdf
      20261115_코세스_089890_QR_2026Q3.json  ->  '코세스 2026 3Q 실적 리뷰', /reports/20261115-089890-qr-2026q3/
.json 내용: {"headline": "리포트 첫 장의 헤드라인"} ('주제: 설명'이면 콜론 앞이 제목, 뒤가 부제)
회사마다 회사 페이지(/companies/<종목코드>/)도 만듭니다. 화면은 layouts/companies/list.html.
data/universe.json에 적은 종목은 리포트가 없어도 회사 페이지를 만듭니다(시세·재무·회사 정보만, 2026-10-21).
"""
import json, pathlib, re, shutil

SRC = pathlib.Path("reports")
DST = pathlib.Path("content/reports")
COMPANIES = pathlib.Path("content/companies")
EXT_DST = pathlib.Path("content/extreports")
EXTERNAL = pathlib.Path("data/external")
UNIVERSE = pathlib.Path("data/universe.json")

# 사이트에 보이는 이름 (약자 BO/WU/QR는 화면에 쓰지 않음). 회사 페이지의 칸 이름·설명은 hugo.toml의 params.reportTypes
TYPES = {
    "BO": ("기업 분석", "Business Overview"),
    "WU": ("주간 업데이트", "Weekly Update"),
    "QR": ("실적 리뷰", "Quarterly Performance Review"),  # 화면 이름만 '실적 리뷰'(2026-10-20), 종류 코드·파일명은 QR 그대로
}
STD = re.compile(
    r"(?P<date>\d{8})_(?P<company>[^_]+)_(?P<code>\d[0-9A-Z]{4}\d)_(?P<type>BO|WU|QR)"
    r"(?:_(?P<period>\d{4}Q[1-4]))?"
)


def slug_of(date, code, type_, period=None):
    """페이지 주소이자 보관함 파일 이름(확장자 제외). scripts/publish.py도 이 함수를 씀"""
    return "-".join(filter(None, [date, code, type_.lower(), (period or "").lower()]))


def parse(stem):
    """표준 파일명 -> (slug, front matter 값). 규칙에 안 맞으면 None"""
    m = STD.fullmatch(stem)
    if not m:
        return None
    d = m["date"]
    ko, en = TYPES[m["type"]]
    period = m["period"]
    # 기간 2026Q3 -> 제목에는 국내 표기 '2026 3Q'
    title = f'{m["company"]} {period[:4]} {period[5]}Q {ko}' if period else f'{m["company"]} {ko}'
    slug = slug_of(d, m["code"], m["type"], period)
    meta = {"title": title, "date": f"{d[:4]}-{d[4:6]}-{d[6:]}", "company": m["company"], "code": m["code"],
            "reportType": m["type"], "typeName": en,  # "type"은 Hugo 예약어(화면 종류)라 쓰지 않음
            "file": slug + ".pdf"}
    if period:
        meta["period"] = period
    return slug, meta


def main():
    # 리포트가 하나도 없어도 메뉴의 '리포트' 목록 페이지가 404가 나지 않도록 섹션 페이지를 만들어 둡니다
    shutil.rmtree(DST, ignore_errors=True)
    DST.mkdir(parents=True)
    (DST / "_index.md").write_text('---\ntitle: "리포트"\n---\n', encoding="utf-8")
    shutil.rmtree(COMPANIES, ignore_errors=True)
    COMPANIES.mkdir(parents=True)
    (COMPANIES / "_index.md").write_text('---\ntitle: "기업"\n---\n', encoding="utf-8")

    companies = {}
    for f in sorted(SRC.glob("*.json")):
        parsed = parse(f.stem)
        if not parsed:
            print(f"skipped (파일명 규칙에 안 맞음): {f.name}")
            continue
        slug, meta = parsed
        h = json.loads(f.read_text(encoding="utf-8")).get("headline")
        if h:
            main_, _, sub = h.partition(": ")
            meta["headline"] = main_.strip()
            if sub:
                meta["subhead"] = sub.strip()
        front = "---\n" + "".join(
            f"{k}: {v}\n" if k == "date" else f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in meta.items()
        ) + "---\n"
        (DST / slug).mkdir()
        (DST / slug / "index.md").write_text(front, encoding="utf-8")
        companies[meta["code"]] = meta["company"]  # 날짜순이라 가장 늦은 리포트의 회사명이 남음
        print(f"converted: {slug}  <-  {f.name}")

    # 증권사 리포트 상세 페이지(2026-10-24): data/external/<코드>.json의 항목마다 /reports/<날짜>-<코드>-ext-<n>/ (n = 파일 안 순번).
    # 섹션은 extreports(우리 리포트 목록·집계에 섞이지 않게), 주소만 url로 /reports/ 아래. 원문 PDF는 받아 두지 않고 링크만
    shutil.rmtree(EXT_DST, ignore_errors=True)
    EXT_DST.mkdir(parents=True)
    (EXT_DST / "_index.md").write_text('---\ntitle: "증권사 리포트"\nbuild:\n  render: never\n  list: never\n---\n', encoding="utf-8")
    for f in sorted(EXTERNAL.glob("*.json")):
        code = f.stem
        for n, it in enumerate(json.loads(f.read_text(encoding="utf-8")).get("items", []), 1):
            slug = f'{it["date"].replace("-", "")}-{code}-ext-{n}'
            meta = {"title": it["title"], "url": f"/reports/{slug}/", "code": code, "broker": it["broker"],
                    "source_url": it.get("url", ""), "summary": it.get("summary", ""), "summary_short": it.get("summary_short", ""),
                    "opinion": it.get("opinion", ""), "target_price": it.get("target_price") or 0,
                    "sitemap": {"disable": True}, "robotsNoIndex": True}
            front = "---\n" + f"date: {it['date']}\n" + "".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in meta.items()) + "---\n"
            (EXT_DST / slug).mkdir()
            (EXT_DST / slug / "index.md").write_text(front, encoding="utf-8")
            print(f"external: {slug}")

    # 회사 페이지: 종목코드마다 하나. 리포트가 없는 종목은 data/universe.json에서
    with_reports = set(companies)
    if UNIVERSE.is_file():
        for c in json.loads(UNIVERSE.read_text(encoding="utf-8")).get("companies", []):
            companies.setdefault(c["code"], c["name"])
    for code, name in sorted(companies.items()):
        (COMPANIES / code).mkdir()
        # 검색 결과 제목(seoTitle)·설명(description): 사람들이 찾는 말로, 권유처럼 읽히는 말(유망·추천·대장주 등)은 쓰지 않음 (2026-10-21)
        # 화면의 회사 이름(h1)은 title 그대로
        seo = f"{name}({code}) 주가·실적·사업 분석"
        desc = f"{name}({code}) 주가 차트, 실적·재무정보, 주요주주, 사업 구성"
        if code in with_reports:
            desc += "과 기업 분석·주간 업데이트·실적 리뷰 리포트"
        meta = {"title": name, "code": code, "seoTitle": seo, "description": desc}
        (COMPANIES / code / "_index.md").write_text(
            "---\n" + "".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in meta.items()) + "---\n", encoding="utf-8")
        print(f"company page: {code} {name}{'' if code in with_reports else ' (리포트 없음)'}")


if __name__ == "__main__":
    main()
