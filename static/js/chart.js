/* 회사 페이지 주가 차트 (2026-10-20): static/market/<코드>.json(scripts/market.py가 매일 만듦)을 읽어 종가 선 + 거래량 막대.
   기간 버튼(1M~5Y), 손가락·마우스로 날짜별 값 보기. 차트 그리기는 TradingView Lightweight Charts(공개 라이브러리) */
(function () {
  var box = document.querySelector('[data-chart]');
  if (!box || !window.LightweightCharts) return;
  var plot = box.querySelector('.ch-plot');
  var tip = box.querySelector('.ch-tip');
  var ret = box.querySelector('.ch-ret');
  var css = getComputedStyle(document.documentElement);
  function v(name) { return css.getPropertyValue(name).trim(); }
  var fmt = new Intl.NumberFormat('ko-KR');

  fetch(box.dataset.chart).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
    if (!d || !d.prices || !d.prices.length) { box.hidden = true; return; }
    var rows = d.prices;  // [날짜, 종가, 고가, 저가, 거래량]
    var chart = LightweightCharts.createChart(plot, {
      autoSize: true,
      layout: { background: { color: 'transparent' }, textColor: v('--muted'), fontFamily: v('--font-data') || 'monospace', fontSize: 11 },
      grid: { vertLines: { visible: false }, horzLines: { color: v('--rule'), style: LightweightCharts.LineStyle.Dashed } },
      rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.08, bottom: 0.26 } },
      timeScale: { borderVisible: true, borderColor: v('--muted'), fixLeftEdge: true, fixRightEdge: true },
      crosshair: { mode: 1, vertLine: { labelVisible: false }, horzLine: { labelVisible: false } },
      handleScroll: false, handleScale: false,
      localization: { priceFormatter: function (p) { return fmt.format(Math.round(p)); } }
    });
    var line = v('--green');
    var area = chart.addAreaSeries({
      lineColor: line, lineWidth: 2, topColor: line + '33', bottomColor: line + '00',
      priceLineVisible: false, lastValueVisible: true
    });
    var vol = chart.addHistogramSeries({ color: v('--rule'), priceScaleId: 'vol', priceFormat: { type: 'volume' }, lastValueVisible: false, priceLineVisible: false });
    chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 }, visible: false });

    function show(period) {
      var last = new Date(rows[rows.length - 1][0]);
      var from = new Date(last);
      var n = parseInt(period, 10);
      if (period.slice(-1) === 'M') from.setMonth(from.getMonth() - n); else from.setFullYear(from.getFullYear() - n);
      var cut = from.toISOString().slice(0, 10);
      var part = rows.filter(function (r) { return r[0] >= cut; });
      area.setData(part.map(function (r) { return { time: r[0], value: r[1] }; }));
      vol.setData(part.map(function (r) { return { time: r[0], value: r[4] || 0 }; }));
      chart.timeScale().fitContent();
      var first = part[0][1], end = part[part.length - 1][1];
      var pct = (end - first) / first * 100;
      ret.textContent = (pct > 0 ? '+' : '') + pct.toFixed(2) + '%';
      ret.className = 'ch-ret ' + (pct > 0 ? 'up' : pct < 0 ? 'down' : '');
      box.querySelectorAll('[data-period]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.period === period)); });
    }
    box.querySelectorAll('[data-period]').forEach(function (b) {
      b.addEventListener('click', function () { show(b.dataset.period); });
    });
    show('1Y');

    // 날짜별 값: 차트 위를 누르거나 마우스를 올리면 위쪽에 표시. 자리는 늘 잡아 두고 글자만 보였다 감춤(차트가 밀리지 않게)
    var byDate = {};
    rows.forEach(function (r) { byDate[r[0]] = r; });
    chart.subscribeCrosshairMove(function (p) {
      var t = p && p.time;
      if (t && typeof t === 'object') t = t.year + '-' + String(t.month).padStart(2, '0') + '-' + String(t.day).padStart(2, '0');
      var r = t && byDate[t];
      if (!r) { tip.classList.remove('on'); return; }
      tip.classList.add('on');
      tip.textContent = r[0] + '  종가 ' + fmt.format(r[1]) + '원  거래량 ' + fmt.format(r[4] || 0);
    });

    // 휴대폰(2026-10-23): handleScroll을 꺼 두면 라이브러리가 터치로는 십자선을 안 그림. 터치(누르기·좌우로 끌기)는 직접 받아 같은 십자선·값 표시를 함.
    // 세로로 끄는 동작은 페이지 스크롤에 넘김(CSS touch-action: pan-y). 마우스는 라이브러리 기본 동작
    function onTouch(e) {
      if (e.pointerType === 'mouse') return;
      var x = e.clientX - plot.getBoundingClientRect().left;
      var t = chart.timeScale().coordinateToTime(x);
      if (t && typeof t === 'object') t = t.year + '-' + String(t.month).padStart(2, '0') + '-' + String(t.day).padStart(2, '0');
      var r = t && byDate[t];
      if (!r) return;
      chart.setCrosshairPosition(r[1], t, area);
      tip.classList.add('on');
      tip.textContent = r[0] + '  종가 ' + fmt.format(r[1]) + '원  거래량 ' + fmt.format(r[4] || 0);
    }
    plot.addEventListener('pointerdown', onTouch);
    plot.addEventListener('pointermove', onTouch);
  }).catch(function () { box.hidden = true; });
})();
