"""Cloudflare(R2 버킷·Worker)를 Python 표준 라이브러리만으로 다루는 도구. publish.py와 deploy_worker.py가 씁니다.

설정은 hugo.toml의 [params.cloudflare](계정 ID·버킷·Worker 주소, 공개값)와 [params.supabase].
API 토큰은 웹사이트 폴더의 .secrets.env (gitignore) 에 사용자가 직접 넣은 한 줄에서만 읽고, 출력하지 않습니다:
  CLOUDFLARE_API_TOKEN=...
토큰 권한: Account > Workers Scripts > Edit, Account > Workers R2 Storage > Edit (대상 계정 하나)
"""
import json, pathlib, sys, tomllib, urllib.error, urllib.parse, urllib.request, uuid

SITE = pathlib.Path(__file__).resolve().parent.parent
SECRETS = SITE / ".secrets.env"
API = "https://api.cloudflare.com/client/v4"


def config():
    params = tomllib.loads((SITE / "hugo.toml").read_text(encoding="utf-8"))["params"]
    return params["cloudflare"], params["supabase"]


def secret(name):
    """.secrets.env의 값 (출력하지 않음)"""
    if SECRETS.is_file():
        for line in SECRETS.read_text(encoding="utf-8-sig").splitlines():
            k, _, v = line.partition("=")
            if k.strip() == name and v.strip():
                return v.strip()
    sys.exit(f"{name}가 없습니다. 웹사이트 폴더의 .secrets.env 에 {name}=... 한 줄을 넣어 주세요.")


def call(method, path, data=None, content_type=None):
    """Cloudflare API 호출. 실패하면 이유를 보여 주고 멈춤"""
    headers = {"Authorization": f"Bearer {secret('CLOUDFLARE_API_TOKEN')}"}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"Cloudflare API 오류 {e.code} ({method} {path}): {e.read().decode('utf-8', 'replace')[:400]}")
    try:
        return json.loads(body)
    except ValueError:
        return {}


def _object_path(key):
    cf, _ = config()
    return f"/accounts/{cf['accountId']}/r2/buckets/{cf['bucket']}/objects/{urllib.parse.quote(key)}"


def r2_put(key, pdf):
    """PDF를 R2 버킷에 key 이름으로 올림 (같은 이름이면 덮어씀)"""
    call("PUT", _object_path(key), pdf.read_bytes(), "application/pdf")


def r2_delete(key):
    call("DELETE", _object_path(key))


def deploy_worker():
    """worker/index.js를 R2 바인딩과 함께 배포하고 workers.dev 주소를 켬. 주소를 돌려줌"""
    cf, sb = config()
    acct = cf["accountId"]
    meta = {
        "main_module": "index.js",
        "compatibility_date": "2025-01-01",
        "bindings": [
            {"type": "r2_bucket", "name": "REPORTS", "bucket_name": cf["bucket"]},
            {"type": "plain_text", "name": "SUPABASE_URL", "text": sb["url"]},
            {"type": "plain_text", "name": "SUPABASE_KEY", "text": sb["key"]},
            {"type": "plain_text", "name": "ALLOWED_ORIGINS", "text": cf["allowedOrigins"]},
        ],
    }
    code = (SITE / "worker" / "index.js").read_bytes()
    b = uuid.uuid4().hex
    body = (
        f'--{b}\r\nContent-Disposition: form-data; name="metadata"\r\nContent-Type: application/json\r\n\r\n'.encode()
        + json.dumps(meta).encode() + b"\r\n"
        + f'--{b}\r\nContent-Disposition: form-data; name="index.js"; filename="index.js"\r\n'
          f'Content-Type: application/javascript+module\r\n\r\n'.encode()
        + code + f"\r\n--{b}--\r\n".encode()
    )
    call("PUT", f"/accounts/{acct}/workers/scripts/{cf['workerName']}", body, f"multipart/form-data; boundary={b}")
    call("POST", f"/accounts/{acct}/workers/scripts/{cf['workerName']}/subdomain",
         json.dumps({"enabled": True}).encode(), "application/json")
    sub = call("GET", f"/accounts/{acct}/workers/subdomain").get("result", {}).get("subdomain")
    return f"https://{cf['workerName']}.{sub}.workers.dev" if sub else None
