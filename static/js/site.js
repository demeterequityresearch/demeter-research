/* 목록 공통 동작
   - ul[data-more="N"]: 처음엔 N개만, 바로 다음의 [data-more-btn] 버튼으로 N개씩 더 보임
   - [data-filters] 거르기 버튼(data-f="all|BO|WU|QR")이 같은 묶음([data-filter-scope]) 안 목록의 .row/.card를 거름 */
(function () {
  // 상단 바 높이(휴대폰은 메뉴가 두 줄일 수 있음) → 회사 페이지 탭이 그 바로 아래에 붙도록
  var nav = document.querySelector('.site-nav');
  function navH() { if (nav) document.documentElement.style.setProperty('--nav-h', nav.offsetHeight + 'px'); }
  navH();
  window.addEventListener('resize', navH);
  if (window.ResizeObserver && nav) new ResizeObserver(navH).observe(nav);

  // 회사 페이지 탭: 보고 있는 구역의 탭에 밑줄
  document.querySelectorAll('.co-tabs').forEach(function (tabs) {
    var links = Array.prototype.slice.call(tabs.querySelectorAll('a[href^="#"]'));
    var secs = links.map(function (a) { return document.getElementById(a.getAttribute('href').slice(1)); });
    function spy() {
      var top = tabs.getBoundingClientRect().bottom + 24, cur = 0;
      if (window.scrollY > 8) secs.forEach(function (s, i) { if (s && s.getBoundingClientRect().top <= top) cur = i; });
      if (window.innerHeight + window.scrollY >= document.body.scrollHeight - 4) {
        // 맨 아래까지 내리면 화면 안에 들어온 마지막 구역
        secs.forEach(function (s, i) { if (s && s.getBoundingClientRect().top < window.innerHeight) cur = i; });
      }
      links.forEach(function (a, i) { if (i === cur) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current'); });
    }
    window.addEventListener('scroll', spy, { passive: true });
    spy();
  });

  function visible(list) {
    return Array.prototype.filter.call(list.children, function (li) { return !li.classList.contains('is-out'); });
  }

  // 거르기 결과 중 앞에서 limit개만 보이고 나머지는 접음
  function paint(list) {
    var limit = +list.dataset.limit || Infinity;
    var shown = visible(list);
    shown.forEach(function (li, i) { li.hidden = i >= limit; });
    Array.prototype.forEach.call(list.children, function (li) { if (li.classList.contains('is-out')) li.hidden = true; });
    var btn = list.nextElementSibling;
    if (btn && btn.hasAttribute('data-more-btn')) btn.hidden = shown.length <= limit;
    var empty = list.parentElement.querySelector('[data-empty]');
    if (empty) empty.hidden = shown.length > 0;
  }

  document.querySelectorAll('ul[data-more]').forEach(function (list) {
    var step = +list.dataset.more;
    list.dataset.limit = step;
    paint(list);
    var btn = list.nextElementSibling;
    if (btn && btn.hasAttribute('data-more-btn')) {
      btn.addEventListener('click', function () {
        list.dataset.limit = +list.dataset.limit + step;
        paint(list);
      });
    }
  });

  document.querySelectorAll('[data-filters]').forEach(function (group) {
    var scope = group.closest('[data-filter-scope]') || document;
    var list = scope.querySelector('ul[data-more], .report-list');
    group.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-f]');
      if (!b) return;
      group.querySelectorAll('button[data-f]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      Array.prototype.forEach.call(list.children, function (li) {
        li.classList.toggle('is-out', b.dataset.f !== 'all' && li.dataset.type !== b.dataset.f);
      });
      if (list.dataset.more) list.dataset.limit = list.dataset.more;
      paint(list);
    });
    // 주소에 ?type=WU 처럼 오면 그 종류부터 (리포트 페이지 경로의 종류 링크)
    var t = (new URLSearchParams(location.search).get('type') || '').toUpperCase().replace(/[^A-Z]/g, '');
    var start = t && group.querySelector('button[data-f="' + t + '"]');
    if (start) start.click();
  });
})();
