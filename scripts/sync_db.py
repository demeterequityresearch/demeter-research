"""파일 <-> Supabase DB 맞추기 (2026-10-22). 표 정의는 _drafts/db_schema_draft.sql, 연결은 scripts/supa.py.

  python scripts/sync_db.py backfill     지금 있는 회사·리포트 목록·시세·요약을 DB에 채움 (SQL 실행 뒤 한 번)
  python scripts/sync_db.py reports      reports/*.json 전체를 DB에 맞춤 (publish.py가 게시 때 자동으로 함)
  python scripts/sync_db.py export       DB의 시세·요약을 data/market·static/market 파일로 만듦 (사이트 빌드 때)
  python scripts/sync_db.py check        DB 내용이 지금 파일과 같은지 비교 (파일은 건드리지 않음)
"""
import json, pathlib, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import supa  # noqa: E402


def drop_none(d):
    return {k: v for k, v in d.items() if v is not None}


def same(a, b):
    """숫자는 값이 같으면 같게 봄(1.0 == 1), 빈 값(None)은 없는 것과 같게 봄"""
    return json.loads(json.dumps(a)) == json.loads(json.dumps(b))


def check():
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        for f in sorted(supa.SUMMARY.glob("*.json")):
            code = f.stem
            if not supa.export_market(code, tmp / "m", tmp / "s"):
                print(f"[다름] {code}: DB에 요약이 없음")
                bad += 1
                continue
            local, db = json.loads(f.read_text(encoding="utf-8")), json.loads((tmp / "m" / f"{code}.json").read_text(encoding="utf-8"))
            for part in ("price", "holders", "financials"):
                a, b = local.get(part), db.get(part)
                if part == "price":
                    a, b = dict(a or {}), dict(b or {})
                    b.pop("pos52", None)  # 파일에는 아직 없음 (DB가 새로 계산한 값)
                    a.pop("pos52", None)
                if part == "holders":
                    a = {"holders": [drop_none({k: h.get(k) for k in ("name", "shares", "pct")}) for h in (a or {}).get("holders", [])],
                         "asof": (a or {}).get("asof")}
                    b = {"holders": (b or {}).get("holders", []), "asof": (b or {}).get("asof")}
                if not same(a, b):
                    print(f"[다름] {code}: {part}")
                    bad += 1
            if not same(drop_none(local.get("valuation") or {}), db.get("valuation") or {}):
                print(f"[다름] {code}: valuation")
                bad += 1
            sf = supa.SERIES / f"{code}.json"
            if sf.is_file():
                a = json.loads(sf.read_text(encoding="utf-8"))["prices"]
                b = json.loads((tmp / "s" / f"{code}.json").read_text(encoding="utf-8"))["prices"]
                if not same(a, b):
                    print(f"[다름] {code}: 일별 시세 (파일 {len(a)}일, DB {len(b)}일)")
                    bad += 1
            print(f"[확인] {code}")
    print("모두 같음" if not bad else f"다른 항목 {bad}개")
    return bad


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd not in ("backfill", "reports", "export", "check"):
        sys.exit(__doc__)
    if not supa.configured():
        sys.exit("SUPABASE_SECRET_KEY가 없습니다 (.secrets.env 또는 환경 변수)")
    if cmd == "backfill":
        supa.sync_companies()
        supa.sync_reports()
        supa.backfill_market(sys.argv[2:] or None)
    elif cmd == "reports":
        supa.sync_companies()
        supa.sync_reports()
    elif cmd == "export":
        codes = sys.argv[2:] or [r["code"] for r in supa.select("market_snapshot", select="code")]
        n = sum(supa.export_market(c) for c in codes)
        print(f"[export] {n}개 종목의 data/market·static/market 파일을 DB에서 만듦")
    else:
        sys.exit(1 if check() else 0)


if __name__ == "__main__":
    main()
