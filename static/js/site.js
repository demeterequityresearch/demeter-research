/* 사이트 공통 동작
   - ul[data-more="N"]: 처음엔 N개만, 바로 다음의 [data-more-btn] 버튼으로 N개씩 더 보임
   - [data-filters] 거르기 버튼(data-f="all|BO|WU|QR")이 같은 묶음([data-filter-scope]) 안 목록의 .row/.card를 거름 */
(function () {
  // 홈 첫 화면 높이 계산: 상단 바 높이(휴대폰은 메뉴가 두 줄일 수 있음)와 바닥글 'DISCLAIMER' 제목 줄 아래까지의 높이
  var nav = document.querySelector('.site-nav');
  var footH = document.querySelector('.site-foot h2');
  function navH() {
    var root = document.documentElement.style;
    if (nav) root.setProperty('--nav-h', nav.offsetHeight + 'px');
    if (footH) root.setProperty('--foot-peek', Math.ceil(footH.getBoundingClientRect().bottom - footH.closest('.site-foot').getBoundingClientRect().top + 10) + 'px');
  }
  navH();
  window.addEventListener('resize', navH);
  if (window.ResizeObserver && nav) new ResizeObserver(navH).observe(nav);

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
