/* 회원 로그인 공통 (모든 페이지). 설정은 window.DEMETER (layouts/_partials/member.html)
   - 상단 '로그인 / 로그아웃' 링크
   - 회원만 보는 곳에서 로그인이 풀려 있으면 로그인 페이지로
   - 준비가 끝나면 'demeter:ready' 이벤트로 페이지 스크립트(로그인 페이지, 리포트 페이지)에 { sb, session }을 넘김 */
(function () {
  var C = window.DEMETER;
  var sb = window.supabase.createClient(C.url, C.key, {
    // 인증 메일 링크를 다른 기기·브라우저에서 열어도 되도록 implicit 방식
    auth: { flowType: 'implicit', detectSessionInUrl: true, persistSession: true, storageKey: C.storageKey }
  });

  function toLogin() {
    location.replace(C.login + '?next=' + encodeURIComponent(location.pathname + location.search + location.hash));
  }

  function setNav(session) {
    document.querySelectorAll('[data-auth-link]').forEach(function (a) {
      if (session) {
        a.textContent = '로그아웃';
        a.href = '#';
        a.onclick = function (e) {
          e.preventDefault();
          sb.auth.signOut().finally(function () { location.href = C.home; });
        };
      } else {
        a.textContent = '로그인';
        a.href = C.login;
        a.onclick = null;
      }
    });
  }

  sb.auth.getSession().then(function (r) {
    var session = r.data.session;
    setNav(session);
    if (C.gated && !session) return toLogin();
    document.dispatchEvent(new CustomEvent('demeter:ready', { detail: { sb: sb, session: session } }));
  });

  sb.auth.onAuthStateChange(function (event, session) {
    setNav(session);
    if (event === 'SIGNED_OUT' && C.gated) toLogin();
  });
})();
