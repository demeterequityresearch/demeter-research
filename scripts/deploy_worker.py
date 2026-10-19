"""리포트 전달 Worker(worker/index.js)를 Cloudflare에 배포합니다. worker/index.js를 고친 뒤에만 다시 실행하면 됩니다.

  python scripts/deploy_worker.py

배포가 끝나면 Worker 주소를 보여 줍니다. hugo.toml의 [params.cloudflare] worker 값과 다르면 그 값을 고칩니다.
처음 배포 때 계정에 workers.dev 하위 주소가 없으면 Cloudflare 대시보드 Workers & Pages 화면에 한 번 들어가 만들어야 합니다.
"""
from cloudflare import config, deploy_worker

url = deploy_worker()
cf, _ = config()
if not url:
    print("배포는 됐지만 workers.dev 주소가 없습니다. Cloudflare 대시보드 > Workers & Pages에 한 번 들어가 하위 주소를 만든 뒤 다시 실행해 주세요.")
elif url != cf.get("worker"):
    print(f"배포 완료: {url}\n→ hugo.toml [params.cloudflare] worker 값을 이 주소로 바꿔야 합니다 (지금: {cf.get('worker') or '비어 있음'})")
else:
    print(f"배포 완료: {url}")
