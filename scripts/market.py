"""회사 페이지의 시세·주요주주·재무 데이터를 매일 만듭니다 (2026-10-20 사용자 결정: 매 거래일 자동 갱신).

GitHub Actions(.github/workflows/deploy.yml)가 매일 아침 실행합니다. Claude는 쓰지 않습니다.
키는 GitHub 저장소의 Actions 비밀값에만 있습니다: KRX_API_KEY(KRX Open API), DART_API_KEY(OpenDART).
리포트 폴더의 .env와는 별개이고, 키 값은 출력하지 않습니다.

대상: 사이트에 리포트가 있는 회사(reports/*.json의 종목코드). DART 고유번호는 data/companies/<코드>.json의 corp_code.
만드는 파일
  data/market/<코드>.json    화면 템플릿용 요약: 종가·전일 대비·시세 정보·주요주주·주요 재무정보 (layouts/companies/list.html)
  static/market/<코드>.json  주가 차트용 일별 시세(최근 5년): [날짜, 종가, 고가, 저가, 거래량] (static/js/chart.js)
시세는 KRX 일별매매정보(종가 기준)라 장중 실시간이 아니며, 화면에 기준일을 함께 보여 줍니다.

사용법 (웹사이트 폴더에서, 키는 환경 변수로)
  python scripts/market.py              모든 회사 갱신 (처음 보는 회사는 5년치를 채움)
  python scripts/market.py 089890       한 회사만
"""
import datetime as dt
import json, os, pathlib, sys, time, urllib.parse, urllib.request

SITE = pathlib.Path(__file__).resolve().parent.parent
REPORTS = SITE / "reports"
COMPANIES = SITE / "data" / "companies"
SUMMARY = SITE / "data" / "market"
SERIES = SITE / "static" / "market"
YEARS = 5

KRX = "https://data-dbg.krx.co.kr/svc/apis/sto/"
KRX_SERVICES = {"KOSPI": "stk_bydd_trd", "KOSDAQ": "ksq_bydd_trd"}
DART = "https://opendart.fss.or.kr/api/"
REPRT = {"11011": "사업보고서", "11014": "3분기보고서", "11012": "반기보고서", "11013": "1분기보고서"}


def get_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # 일시적 오류는 두 번 더 시도
            if attempt == 2:
                raise RuntimeError(f"요청 실패: {url.split('?')[0]} ({e})") from None
            time.sleep(2 * (attempt + 1))


def num(v):
    """KRX·DART 숫자 문자열('1,234', '-', '') -> int/float, 없으면 None"""
    if v is None:
        return None
    s = str(v).replace(",", "").strip()
    if s in ("", "-"):
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    return int(f) if f.is_integer() else f


# ── KRX 일별 시세 ──
def krx_day(key, market, day):
    """그날 그 시장 전 종목 시세 {종목코드: row}. 휴장일이면 빈 dict"""
    url = KRX + KRX_SERVICES[market] + "?" + urllib.parse.urlencode({"basDd": day.strftime("%Y%m%d")})
    data = get_json(url, {"AUTH_KEY": key})
    return {r.get("ISU_CD"): r for r in data.get("OutBlock_1") or []}


def update_prices(key, targets):
    """targets: 종목코드 목록. static/market/<코드>.json의 일별 시세를 오늘까지 채움 (처음 보는 종목은 5년치)"""
    today = dt.date.today()
    start_new = today - dt.timedelta(days=365 * YEARS + 10)
    hist, need_from = {}, {}
    for code in targets:
        f = SERIES / f"{code}.json"
        rows = json.loads(f.read_text(encoding="utf-8"))["prices"] if f.is_file() else []
        hist[code] = rows
        last = dt.date.fromisoformat(rows[-1][0]) if rows else start_new - dt.timedelta(days=1)
        need_from[code] = last + dt.timedelta(days=1)
    day = min(need_from.values())
    calls = 0
    while day <= today:
        if day.weekday() < 5 and any(need_from[c] <= day for c in targets):  # 주말은 건너뜀 (공휴일은 빈 응답)
            # 시장을 옮긴 종목(예: 엘앤에프 2024.01 코스닥 → 코스피)도 있으므로 두 시장을 모두 보고 종목코드로 찾음
            rows = {}
            for market in KRX_SERVICES:
                rows.update(krx_day(key, market, day))
                calls += 1
                time.sleep(0.15)
            for code in targets:
                r = rows.get(code)
                if need_from[code] <= day and r and num(r.get("TDD_CLSPRC")):
                        hist[code].append([day.isoformat(), num(r["TDD_CLSPRC"]), num(r.get("TDD_HGPRC")),
                                           num(r.get("TDD_LWPRC")), num(r.get("ACC_TRDVOL")),
                                           {k: r.get(k) for k in ("TDD_OPNPRC", "CMPPREVDD_PRC", "FLUC_RT", "ACC_TRDVAL",
                                                                  "MKTCAP", "LIST_SHRS", "ISU_NM", "MKT_NM")}])
        day += dt.timedelta(days=1)
    print(f"[KRX] 호출 {calls}회")
    cut = (today - dt.timedelta(days=365 * YEARS + 10)).isoformat()
    for code, rows in hist.items():
        rows = [r for r in rows if r[0] >= cut]
        hist[code] = rows
    return hist


def price_summary(rows):
    """일별 시세 -> 머리·시세 정보에 쓰는 값 (마지막 거래일 기준)"""
    if not rows:
        return None
    last = rows[-1]
    extra = last[5] if len(last) > 5 and isinstance(last[5], dict) else {}
    year_ago = (dt.date.fromisoformat(last[0]) - dt.timedelta(days=365)).isoformat()
    yr = [r for r in rows if r[0] > year_ago]
    highs = [r[2] or r[1] for r in yr]
    lows = [r[3] or r[1] for r in yr]
    prev = rows[-2][1] if len(rows) > 1 else None
    change = num(extra.get("CMPPREVDD_PRC"))
    if change is None and prev:
        change = last[1] - prev
    rate = num(extra.get("FLUC_RT"))
    if rate is None and prev:
        rate = round((last[1] - prev) / prev * 100, 2)
    return {
        "asof": last[0], "close": last[1], "change": change, "change_pct": rate,
        "open": num(extra.get("TDD_OPNPRC")), "high": last[2], "low": last[3], "prev_close": prev,
        "volume": last[4], "value": num(extra.get("ACC_TRDVAL")),
        "mktcap": num(extra.get("MKTCAP")), "shares": num(extra.get("LIST_SHRS")),
        "hi52": max(highs) if highs else None, "lo52": min(lows) if lows else None,
    }


# ── DART 주요주주·재무 ──
def dart(key, path, **params):
    data = get_json(DART + path + "?" + urllib.parse.urlencode(dict(crtfc_key=key, **params)))
    return (data.get("list") or []) if data.get("status") == "000" else []  # 013 = 자료 없음


def latest_reports(today):
    """가장 최근 것부터 (사업연도, 보고서 코드) 후보"""
    out = []
    for y in range(today.year, today.year - 3, -1):
        for code in ("11014", "11012", "11013", "11011"):
            out.append((y if code != "11011" else y - 1, code))
    return out


def holder_key(name):
    """주주 이름 비교용: '(주)', '주식회사', 띄어쓰기를 뺌"""
    for t in ("(주)", "㈜", "주식회사", " "):
        name = name.replace(t, "")
    return name


def shareholders(key, corp, today):
    """최대주주 및 특수관계인 합계 + 5% 이상 대량보유자 (가장 최근 정기보고서·보고 기준)"""
    out = {"holders": [], "asof": None, "source": None}
    for y, rc in latest_reports(today):
        rows = dart(key, "hyslrSttus.json", corp_code=corp, bsns_year=y, reprt_code=rc)
        rows = [r for r in rows if (r.get("stock_knd") or "").startswith("보통")]
        if not rows:
            continue
        total = next((r for r in rows if (r.get("nm") or "").strip() in ("계", "합계")), None)
        named = [r for r in rows if r is not total]
        main = max(named, key=lambda r: num(r.get("trmend_posesn_stock_co")) or 0) if named else None
        if main:
            n = len(named) - 1
            out["holders"].append({
                "name": main["nm"].strip() + (f" 외 {n}인" if n > 0 else ""),
                "shares": num((total or main).get("trmend_posesn_stock_co")),
                "pct": num((total or main).get("trmend_posesn_stock_qota_rt")),
            })
        out["asof"] = f"{y} {REPRT[rc]}"
        out["source"] = "DART 최대주주 현황"
        break
    seen = {holder_key(h["name"].split(" 외 ")[0]) for h in out["holders"]}
    for r in dart(key, "majorstock.json", corp_code=corp):  # 대량보유 상황보고: 보고자별 가장 최근 것
        name = (r.get("repror") or "").strip()
        if not name or holder_key(name) in seen:
            continue
        seen.add(holder_key(name))
        pct = num(r.get("stkrt"))
        if pct and pct >= 5:
            out["holders"].append({"name": name, "shares": num(r.get("stkqy")), "pct": pct,
                                   "date": r.get("rcept_dt")})
    out["holders"] = out["holders"][:6]
    return out


ACCOUNTS = {
    "revenue": ["ifrs-full_Revenue"],
    "op": ["dart_OperatingIncomeLoss"],
    "net": ["ifrs-full_ProfitLoss"],
    "net_owner": ["ifrs-full_ProfitLossAttributableToOwnersOfParent"],
    "assets": ["ifrs-full_Assets"],
    "liab": ["ifrs-full_Liabilities"],
    "equity": ["ifrs-full_Equity"],
    "equity_owner": ["ifrs-full_EquityAttributableToOwnersOfParent"],
    "cash": ["ifrs-full_CashAndCashEquivalents"],
    "borrow": ["ifrs-full_ShorttermBorrowings", "ifrs-full_CurrentPortionOfLongtermBorrowings",
               "ifrs-full_LongtermBorrowings", "dart_ShortTermBorrowings", "dart_LongTermBorrowingsGross",
               "ifrs-full_BondsIssued", "dart_BondsIssued", "ifrs-full_CurrentPortionOfBondsIssued"],
    "interest": ["ifrs-full_InterestExpense", "dart_InterestExpenseFinanceExpense"],
    "cfo": ["ifrs-full_CashFlowsFromUsedInOperatingActivities"],
    "cfi": ["ifrs-full_CashFlowsFromUsedInInvestingActivities"],
    "cff": ["ifrs-full_CashFlowsFromUsedInFinancingActivities"],
}
SUM = {"borrow"}  # 여러 계정을 더하는 것
# 표준 계정 ID가 없을 때 계정 이름으로 찾음 (회사마다 '이자비용'을 자체 계정으로 공시하는 경우가 많음)
NAMES = {"interest": ("이자비용",)}


def statements(key, corp, year, rc):
    """한 보고서의 연결(없으면 별도) 재무제표 -> {항목: 값(원)}. 손익·현금흐름은 누적(thstrm_add_amount가 있으면 그것)"""
    for fs in ("CFS", "OFS"):
        rows = dart(key, "fnlttSinglAcntAll.json", corp_code=corp, bsns_year=year, reprt_code=rc, fs_div=fs)
        if not rows:
            continue
        got = {}
        for k, ids in ACCOUNTS.items():
            vals = []
            for r in rows:
                if r.get("account_id") in ids:
                    v = r.get("thstrm_add_amount") if r.get("sj_div") in ("IS", "CIS") and r.get("thstrm_add_amount") else r.get("thstrm_amount")
                    v = num(v)
                    if v is not None:
                        vals.append((r.get("sj_div"), v))
            if not vals and k in NAMES:
                for r in rows:
                    nm = (r.get("account_nm") or "").replace(" ", "")
                    if r.get("sj_div") in ("IS", "CIS") and any(nm.startswith(n) for n in NAMES[k]):
                        v = num(r.get("thstrm_add_amount") or r.get("thstrm_amount"))
                        if v is not None:
                            vals.append((r.get("sj_div"), abs(v)))
                            break
            if not vals:
                continue
            if k in SUM:
                got[k] = sum(v for _, v in vals)
            else:
                # 손익은 IS가 있으면 IS, 아니면 CIS
                vals.sort(key=lambda x: 0 if x[0] in ("IS", "BS", "CF") else 1)
                got[k] = vals[0][1]
        if got:
            got["fs"] = "연결" if fs == "CFS" else "별도"
            return got
    return None


def financials(key, corp, today):
    """최근 3개 사업연도(사업보고서) + 가장 최근 분기 누적. 금액은 억원"""
    years = []
    for y in range(today.year - 1, today.year - 5, -1):
        st = statements(key, corp, y, "11011")
        if st:
            years.append((f"{y}", st))
        if len(years) == 3:
            break
    years.reverse()
    latest = None
    for y, rc in latest_reports(today):
        if rc == "11011":
            continue
        st = statements(key, corp, y, rc)
        if st:
            label = {"11013": "1Q", "11012": "2Q", "11014": "3Q"}[rc]
            latest = (f"{y} {label} 누적", st, y, rc)
            break
    if latest and years and latest[2] <= int(years[-1][0]):
        latest = None  # 사업보고서보다 오래된 분기는 쓰지 않음
    cols = years + ([latest[:2]] if latest else [])

    def eok(v):
        return round(v / 1e8) if v is not None else None

    def pct(a, b):
        return round(a / b * 100, 1) if a is not None and b else None

    table = []
    for label, st in cols:
        net_debt = (st["borrow"] - st["cash"]) if "borrow" in st and "cash" in st else None
        table.append({
            "period": label, "fs": st.get("fs"),
            "revenue": eok(st.get("revenue")), "op": eok(st.get("op")), "net": eok(st.get("net")),
            "op_margin": pct(st.get("op"), st.get("revenue")), "net_margin": pct(st.get("net"), st.get("revenue")),
            "debt_ratio": pct(st.get("liab"), st.get("equity")),
            "net_debt_ratio": pct(net_debt, st.get("equity")),
            "interest_cover": round(st["op"] / st["interest"], 1) if st.get("op") is not None and st.get("interest") else None,
            "cfo": eok(st.get("cfo")), "cfi": eok(st.get("cfi")), "cff": eok(st.get("cff")),
            "_net_owner": st.get("net_owner", st.get("net")), "_equity_owner": st.get("equity_owner", st.get("equity")),
        })
    return table


def valuation(price, fin):
    """PER·PBR·EPS·BPS: 직전 사업연도 지배주주 순이익, 가장 최근 지배주주 자본 기준 (단순 계산)"""
    if not price or not price.get("shares") or not fin:
        return {}
    shares = price["shares"]
    annual = [r for r in fin if "누적" not in r["period"]]
    out = {}
    if annual and annual[-1]["_net_owner"] is not None:
        eps = annual[-1]["_net_owner"] / shares
        out["eps"] = round(eps)
        out["eps_basis"] = annual[-1]["period"]
        out["per"] = round(price["close"] / eps, 1) if eps > 0 else None
    if fin[-1]["_equity_owner"]:
        bps = fin[-1]["_equity_owner"] / shares
        out["bps"] = round(bps)
        out["bps_basis"] = fin[-1]["period"]
        out["pbr"] = round(price["close"] / bps, 2) if bps > 0 else None
    return out


def main():
    krx_key, dart_key = os.environ.get("KRX_API_KEY"), os.environ.get("DART_API_KEY")
    if not krx_key and not dart_key:
        sys.exit("KRX_API_KEY·DART_API_KEY가 없습니다 (GitHub 저장소 Settings → Secrets and variables → Actions)")
    only = sys.argv[1:]
    codes = sorted({f.stem.split("_")[2] for f in REPORTS.glob("*.json") if len(f.stem.split("_")) > 3})
    targets = {}
    for code in codes:
        if only and code not in only:
            continue
        info_f = COMPANIES / f"{code}.json"
        info = json.loads(info_f.read_text(encoding="utf-8")) if info_f.is_file() else {}
        targets[code] = info
    SUMMARY.mkdir(parents=True, exist_ok=True)
    SERIES.mkdir(parents=True, exist_ok=True)

    hist = {}
    if krx_key:
        hist = update_prices(krx_key, list(targets))
    today = dt.date.today()
    for code, info in targets.items():
        old_f = SUMMARY / f"{code}.json"
        old = json.loads(old_f.read_text(encoding="utf-8")) if old_f.is_file() else {}
        rows = hist.get(code)
        # 오늘 새로 받은 시세(마지막 줄에 시가총액 등 부가 값이 있음)가 있으면 다시 계산, 없으면 지난 값 유지
        fresh = rows and len(rows[-1]) > 5
        price = price_summary(rows) if fresh else (old.get("price") or (price_summary(rows) if rows else None))
        out = {"code": code, "price": price, "updated": today.isoformat()}
        corp = info.get("corp_code")
        if dart_key and corp:
            out["holders"] = shareholders(dart_key, corp, today)
            fin = financials(dart_key, corp, today)
            out["valuation"] = valuation(price, fin)
            out["financials"] = [{k: v for k, v in r.items() if not k.startswith("_")} for r in fin]
        else:
            for k in ("holders", "valuation", "financials"):
                if k in old:
                    out[k] = old[k]
        if rows:
            (SERIES / f"{code}.json").write_text(
                json.dumps({"code": code, "asof": rows[-1][0], "prices": [r[:5] for r in rows]}, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8")
        old_f.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"[{code}] 종가 {price and price.get('close')} ({price and price.get('asof')}), "
              f"주주 {len(out.get('holders', {}).get('holders', []))}명, 재무 {len(out.get('financials', []))}개 기간")


if __name__ == "__main__":
    main()
