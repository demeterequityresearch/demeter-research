"""Supabase DB 연결과 표 변환 (2026-10-22). publish.py·market.py·sync_db.py가 씀. 표준 라이브러리만 사용.

DB 표 정의는 _drafts/db_schema_draft.sql (Supabase SQL Editor에서 한 번 실행). 읽기는 누구나(공개 데이터), 쓰기는 서버(이 파일)만.
화면(Hugo)은 지금처럼 data/market·static/market·reports/ 파일을 읽는다. DB는 같은 내용을 담는 곳이고, 파일은 필요할 때 DB에서 다시 만든다(sync_db.py export).

키: SUPABASE_SECRET_KEY (환경 변수, 없으면 웹사이트 폴더의 .secrets.env). 값은 출력하지 않는다.
주소: hugo.toml [params.supabase] url (환경 변수 SUPABASE_URL이 있으면 그것).
키가 없으면 configured()가 False라서 DB 기록은 건너뛴다(예: 키를 아직 못 넣은 GitHub Actions).
"""
import datetime as dt
import json, os, pathlib, sys, tomllib, urllib.error, urllib.parse, urllib.request

SITE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SITE / "scripts"))
from convert import parse  # noqa: E402  표준 파일명 해석은 convert.py 한 곳에서

REPORTS = SITE / "reports"
COMPANIES = SITE / "data" / "companies"
UNIVERSE = SITE / "data" / "universe.json"
SUMMARY = SITE / "data" / "market"
SERIES = SITE / "static" / "market"
PAGE = 1000  # Supabase가 한 번에 돌려주는 최대 행 수


# ── 연결 ──
def _secret():
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if key:
        return key.strip()
    f = SITE / ".secrets.env"
    if f.is_file():
        for line in f.read_text(encoding="utf-8-sig").splitlines():
            k, _, v = line.partition("=")
            if k.strip() == "SUPABASE_SECRET_KEY" and v.strip():
                return v.strip()
    return None


def _url():
    if os.environ.get("SUPABASE_URL"):
        return os.environ["SUPABASE_URL"].rstrip("/")
    return tomllib.loads((SITE / "hugo.toml").read_text(encoding="utf-8"))["params"]["supabase"]["url"].rstrip("/")


def configured():
    return bool(_secret())


def _call(method, table, params=None, rows=None, prefer=None, extra_headers=None):
    key = _secret()
    if not key:
        raise RuntimeError("SUPABASE_SECRET_KEY가 없습니다")
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):  # 예전 형식(JWT) 키는 Authorization에도 붙임. 새 sb_secret_ 키는 apikey만
        headers["Authorization"] = "Bearer " + key
    if prefer:
        headers["Prefer"] = prefer
    headers.update(extra_headers or {})
    url = f"{_url()}/rest/v1/{table}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(rows, ensure_ascii=False).encode("utf-8") if rows is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Supabase 오류 {e.code} ({method} {table}): {e.read().decode('utf-8', 'replace')[:300]}") from None
    return json.loads(body) if body else None


def upsert(table, rows, on_conflict):
    """rows를 넣고, 기본키(on_conflict)가 같은 행은 덮어씀"""
    for i in range(0, len(rows), PAGE):
        _call("POST", table, {"on_conflict": on_conflict}, rows[i:i + PAGE],
              prefer="resolution=merge-duplicates,return=minimal")


def select(table, **params):
    """조건에 맞는 행을 모두 (PAGE개씩 이어서) 가져옴. 조건은 PostgREST 형식: code="eq.089890", order="date.asc" """
    out, offset = [], 0
    while True:
        part = _call("GET", table, dict(params, limit=PAGE, offset=offset))
        out += part
        if len(part) < PAGE:
            return out
        offset += PAGE


def delete(table, **params):
    _call("DELETE", table, params, prefer="return=minimal")


def try_sync(label, fn, *args):
    """DB 기록 실패가 게시·시세 갱신을 멈추지 않게 함 (실패하면 알리고 계속)"""
    if not configured():
        print(f"[DB] {label}: SUPABASE_SECRET_KEY가 없어 건너뜀")
        return
    try:
        fn(*args)
    except Exception as e:  # noqa: BLE001
        print(f"[DB 주의] {label} 실패: {e}")


# ── 로컬 파일에서 읽기 ──
def _json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def company_names():
    """{종목코드: (회사명, 리포트 있음)}. 리포트 파일 이름에서, 없으면 data/universe.json에서"""
    out = {}
    for f in sorted(REPORTS.glob("*.json")):
        p = parse(f.stem)
        if p:
            out[p[1]["code"]] = (p[1]["company"], True)
    for c in (_json(UNIVERSE, {}) or {}).get("companies", []):
        out.setdefault(c["code"], (c["name"], False))
    return out


# ── 표 행 만들기 ──
def company_row(code, name, has_reports, info, universe=None):
    info = info or universe or {}
    fm = info.get("fiscal_month")
    return {
        "code": code, "name": name, "market": info.get("market"), "corp_code": info.get("corp_code"),
        "industry": info.get("industry"), "definition": info.get("definition"), "ceo": info.get("ceo"),
        "hq": info.get("hq"), "homepage": info.get("homepage"),
        "fiscal_month": int(fm) if str(fm or "").isdigit() else None,
        "segments": info.get("segments") or [], "peers": info.get("peers") or [],
        "has_reports": has_reports, "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def report_row(stem):
    p = parse(stem)
    if not p:
        return None
    slug, meta = p
    h = (_json(REPORTS / f"{stem}.json", {}) or {}).get("headline")
    head, _, sub = (h or "").partition(": ")
    return {
        "id": slug, "company_code": meta["code"], "type": meta["reportType"], "period": meta.get("period"),
        "published_at": meta["date"], "headline": head.strip() or None, "subhead": sub.strip() or None,
        "file": meta["file"],
    }


def pos52(price):
    """52주 범위 안 위치(0~100). 화면이 계산하던 것을 엔진이 계산 (2026-10-22)"""
    hi, lo, close = price.get("hi52"), price.get("lo52"), price.get("close")
    if hi is None or lo is None or close is None:
        return None
    return round((close - lo) / (hi - lo) * 100, 1) if hi > lo else 50


PRICE_KEYS = ("asof", "close", "change", "change_pct", "open", "high", "low", "prev_close", "volume", "value",
              "mktcap", "shares", "hi52", "lo52")
VAL_KEYS = ("eps", "eps_basis", "per", "bps", "bps_basis", "pbr")


def snapshot_row(code, out):
    price = out.get("price")
    if not price:
        return None
    row = {"code": code, **{k: price.get(k) for k in PRICE_KEYS}, "pos52": price.get("pos52", pos52(price)),
           **{k: (out.get("valuation") or {}).get(k) for k in VAL_KEYS}}
    for k in ("volume", "shares"):  # bigint 칸
        if row[k] is not None:
            row[k] = int(row[k])
    row["updated_at"] = f"{out.get('updated') or dt.date.today().isoformat()}T00:00:00+00:00"
    return row


def holder_rows(code, holders):
    return [{"code": code, "rank": i, "asof_label": holders.get("asof"), "name": h["name"],
             "shares": h.get("shares"), "pct": h.get("pct")} for i, h in enumerate(holders.get("holders") or [])]


def fin_rows(code, fin):
    return [{"code": code, "period": r["period"], "sort": i, "fs": r.get("fs"),
             "data": {k: v for k, v in r.items() if k not in ("period", "fs")}} for i, r in enumerate(fin or [])]


def price_rows(code, rows):
    """일별 시세 [날짜, 종가, 고가, 저가, 거래량, ...] -> prices_daily 행"""
    return [{"code": code, "date": r[0], "close": r[1], "high": r[2], "low": r[3], "volume": r[4]} for r in rows]


# ── DB에 쓰기 ──
def sync_companies():
    uni = {c["code"]: c for c in (_json(UNIVERSE, {}) or {}).get("companies", [])}
    rows = [company_row(code, name, has, _json(COMPANIES / f"{code}.json"), uni.get(code))
            for code, (name, has) in company_names().items()]
    upsert("companies", rows, "code")
    print(f"[DB] companies {len(rows)}건")


def sync_reports():
    """reports/*.json 전체를 DB에 맞춤. 사이트 목록에서 빠진(보관 개수 초과 등) 리포트는 DB에서도 지움"""
    rows = [r for r in (report_row(f.stem) for f in sorted(REPORTS.glob("*.json"))) if r]
    upsert("reports", rows, "id")
    keep = {r["id"] for r in rows}
    for old in select("reports", select="id"):
        if old["id"] not in keep:
            delete("reports", id=f"eq.{old['id']}")
            print(f"[DB] reports에서 뺌: {old['id']}")
    print(f"[DB] reports {len(rows)}건")


def save_market(code, out, new_price_rows=()):
    """한 종목의 시세·요약·주주·재무를 DB에 씀. new_price_rows는 새로 받은 일별 시세만(없으면 시세 표는 그대로)"""
    if new_price_rows:
        upsert("prices_daily", price_rows(code, new_price_rows), "code,date")
    snap = snapshot_row(code, out)
    if snap:
        upsert("market_snapshot", [snap], "code")
    if "holders" in out:
        delete("holders", code=f"eq.{code}")
        upsert("holders", holder_rows(code, out["holders"]), "code,rank")
    if "financials" in out:
        delete("financials", code=f"eq.{code}")
        upsert("financials", fin_rows(code, out["financials"]), "code,period")


def backfill_market(codes=None):
    """지금 있는 data/market·static/market 파일을 DB로 옮김 (한 번 실행하면 됨)"""
    for f in sorted(SUMMARY.glob("*.json")):
        code = f.stem
        if codes and code not in codes:
            continue
        out = _json(f)
        if out.get("price"):
            out["price"]["pos52"] = pos52(out["price"])
        series = _json(SERIES / f"{code}.json", {}) or {}
        save_market(code, out, series.get("prices") or [])
        print(f"[DB] {code}: 시세 {len(series.get('prices') or [])}일, 주주 {len((out.get('holders') or {}).get('holders') or [])}명, "
              f"재무 {len(out.get('financials') or [])}개 기간")


# ── DB에서 읽기 (시세 이어 받기 / 화면용 파일 만들기) ──
def get_prices(code):
    """prices_daily -> [[날짜, 종가, 고가, 저가, 거래량], ...] 날짜순"""
    return [[r["date"], r["close"], r["high"], r["low"], r["volume"]]
            for r in select("prices_daily", select="date,close,high,low,volume", code=f"eq.{code}", order="date.asc")]


def get_snapshot(code):
    rows = select("market_snapshot", select="*", code=f"eq.{code}")
    return rows[0] if rows else None


def summary_from_db(code):
    """DB -> data/market/<코드>.json 내용 (화면 템플릿이 읽는 모양). 스냅샷이 없으면 None"""
    snap = get_snapshot(code)
    if not snap:
        return None
    out = {"code": code, "price": {k: snap.get(k) for k in PRICE_KEYS + ("pos52",)},
           "updated": (snap.get("updated_at") or "")[:10]}
    val = {k: snap[k] for k in VAL_KEYS if snap.get(k) is not None}
    hs = select("holders", select="*", code=f"eq.{code}", order="rank.asc")
    out["holders"] = {"holders": [{k: h[k] for k in ("name", "shares", "pct") if h.get(k) is not None} for h in hs],
                      "asof": hs[0]["asof_label"] if hs else None,
                      "source": "DART 최대주주 현황" if hs else None}
    out["valuation"] = val
    fins = select("financials", select="*", code=f"eq.{code}", order="sort.asc")
    out["financials"] = [{"period": r["period"], "fs": r.get("fs"), **r["data"]} for r in fins]
    return out


def export_market(code, dest_summary=SUMMARY, dest_series=SERIES):
    """DB의 시세·요약을 Hugo가 읽는 파일로 씀 (빌드 때 실행, 저장소에는 올리지 않음)"""
    out = summary_from_db(code)
    if not out:
        return False
    dest_summary.mkdir(parents=True, exist_ok=True)
    dest_series.mkdir(parents=True, exist_ok=True)
    (dest_summary / f"{code}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    rows = get_prices(code)
    if rows:
        (dest_series / f"{code}.json").write_text(
            json.dumps({"code": code, "asof": rows[-1][0], "prices": rows}, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")
    return True
