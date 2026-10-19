// Demeter 리포트 전달 Worker (Cloudflare, 이름 demeter-reports)
// 회원만 R2 비공개 버킷의 리포트 PDF를 받게 하는 중간 장치. 배포: python scripts/deploy_worker.py
//   GET /report/<파일>.pdf  (Authorization: Bearer <Supabase 로그인 토큰>)
//   1) R2에서 파일을 찾고  2) 그 회원 이름으로 Supabase 기록표(downloads)에 남기고  3) 성공해야 PDF를 보냄
//   기록은 회원 토큰으로 넣으므로 Supabase가 토큰을 확인하고(가짜·만료면 거절) 행 수준 규칙이 user_id·email을 맞춤 (supabase/setup.sql)
// 설정(배포 때 넣음): REPORTS = R2 버킷 바인딩, SUPABASE_URL·SUPABASE_KEY(공개용 publishable key), ALLOWED_ORIGINS

export default {
  async fetch(req, env) {
    const origin = req.headers.get('Origin') || '';
    const allowed = env.ALLOWED_ORIGINS.split(',').includes(origin) || /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin);
    const cors = allowed ? {
      'Access-Control-Allow-Origin': origin,
      'Access-Control-Allow-Headers': 'Authorization, Range',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Max-Age': '86400',
      'Vary': 'Origin',
    } : { 'Vary': 'Origin' };
    const reply = (status, text) => new Response(text, { status, headers: cors });

    if (req.method === 'OPTIONS') return new Response(null, { status: allowed ? 204 : 403, headers: cors });
    if (req.method !== 'GET') return reply(405, 'Method not allowed');

    const m = new URL(req.url).pathname.match(/^\/report\/([0-9a-z-]+\.pdf)$/);
    if (!m) return reply(404, 'Not found');
    const file = m[1];

    const auth = req.headers.get('Authorization') || '';
    if (!/^Bearer [\w.-]+$/.test(auth)) return reply(401, 'Login required');

    const obj = await env.REPORTS.get(file);
    if (!obj) return reply(404, 'Not found');

    const log = await fetch(`${env.SUPABASE_URL}/rest/v1/downloads`, {
      method: 'POST',
      headers: { apikey: env.SUPABASE_KEY, Authorization: auth, 'Content-Type': 'application/json', Prefer: 'return=minimal' },
      body: JSON.stringify({ report: file, kind: 'view' }),
    });
    if (!log.ok) {
      await obj.body.cancel();
      return reply(401, 'Login required');
    }

    return new Response(obj.body, {
      headers: {
        ...cors,
        'Content-Type': 'application/pdf',
        'Content-Disposition': 'inline',
        'Cache-Control': 'private, no-store',
      },
    });
  },
};
