/* 회사 검색 (회사명 일부·종목코드 앞자리) → 회사 페이지로 이동. 홈 큰 검색창과 상단 바 검색창이 함께 씀
   검색창마다 <form data-search data-index="index.json 주소">, 안에 input[type=search]와 ul.suggest
   상단 바 휴대폰 화면: [data-search-toggle] 돋보기 버튼이 검색창을 펼침 */
(function () {
  var companies = null, loading = null;

  function load(url) {
    if (!loading) loading = fetch(url).then(function (r) { return r.json(); }).then(function (d) { companies = d; return d; });
    return loading;
  }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
  }
  function norm(s) { return String(s).toLowerCase().replace(/\s+/g, ''); }

  function setup(form) {
    var q = form.querySelector('input[type=search]');
    var sug = form.querySelector('.suggest');
    var key = form.dataset.search || 'q';
    var matches = [], active = -1;

    function close() { sug.hidden = true; q.setAttribute('aria-expanded', 'false'); }

    // 회사명 일부 또는 종목코드 앞자리로 찾음 (리포트가 있는 회사만)
    function show() {
      if (!companies) { load(form.dataset.index).then(show); return; }
      var t = norm(q.value);
      if (!t) { matches = []; close(); return; }
      matches = companies.filter(function (c) { return norm(c.name).indexOf(t) >= 0 || c.code.indexOf(t) === 0; });
      active = matches.length ? 0 : -1;
      sug.innerHTML = matches.length
        ? matches.map(function (c, i) {
            return '<li role="option" id="' + key + '-opt-' + c.code + '" aria-selected="' + (i === active) + '" data-href="' + esc(c.permalink) + '">' +
              '<span>' + esc(c.name) + '</span><span class="s-code">' + esc(c.code) + '</span>' +
              '<span class="s-count">리포트 ' + c.count + '건</span></li>';
          }).join('')
        : '<li class="s-none" role="option" aria-disabled="true">‘' + esc(q.value.trim()) + '’에 맞는 기업이 없습니다. 리포트가 있는 기업만 검색됩니다.</li>';
      sug.hidden = false;
      q.setAttribute('aria-expanded', 'true');
      q.setAttribute('aria-activedescendant', active >= 0 ? key + '-opt-' + matches[active].code : '');
    }
    function move(d) {
      if (!matches.length) return;
      active = (active + d + matches.length) % matches.length;
      sug.querySelectorAll('[role=option]').forEach(function (li, i) { li.setAttribute('aria-selected', String(i === active)); });
      q.setAttribute('aria-activedescendant', key + '-opt-' + matches[active].code);
    }

    q.addEventListener('input', show);
    q.addEventListener('focus', function () { load(form.dataset.index); if (q.value.trim()) show(); });
    q.addEventListener('blur', function () { setTimeout(close, 120); });
    q.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
      else if (e.key === 'Escape') { close(); form.dispatchEvent(new Event('search-close')); }
    });
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!q.value.trim()) return;
      if (!companies) { load(form.dataset.index).then(function () { form.requestSubmit(); }); return; }
      show();
      if (matches.length) location.href = matches[Math.max(active, 0)].permalink;
    });
    sug.addEventListener('mousedown', function (e) {
      var li = e.target.closest('li[data-href]');
      if (li) { e.preventDefault(); location.href = li.dataset.href; }
    });
    if (q.value.trim()) show();
  }

  document.querySelectorAll('form[data-search]').forEach(setup);

  // 상단 바 (휴대폰): 돋보기를 누르면 검색창이 펼쳐지고 바로 입력
  document.querySelectorAll('[data-search-toggle]').forEach(function (btn) {
    var nav = btn.closest('.site-nav');
    var form = nav.querySelector('.nav-search');
    function set(open) {
      nav.classList.toggle('search-open', open);
      btn.setAttribute('aria-expanded', String(open));
      if (open) form.querySelector('input').focus();
    }
    btn.addEventListener('click', function () { set(!nav.classList.contains('search-open')); });
    form.addEventListener('search-close', function () { set(false); });
  });
})();
