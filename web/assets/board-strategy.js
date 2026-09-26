/* board-strategy.js — 初始策略台：四段分析 + LLM 综合研判 */
(function () {
  function mdLite(t) {
    // 极简 markdown：加粗 + 换行
    return t.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
            .split(/\n+/).filter(Boolean).map(function (l) { return "<p>" + l + "</p>"; }).join("");
  }

  function crBar(label, valStr, ratio, warn) {
    var w = Math.round((ratio || 0) * 100);
    return '<div class="cr-bar"><span class="cb-l">' + label + '</span>' +
      '<div class="cb-track"><div class="cb-fill' + (warn ? " warn" : "") + '" style="width:' + w + '%"></div></div>' +
      '<span class="cb-v">' + (valStr || "—") + "</span></div>";
  }

  function render() {
    var cats = window.activeCategories();
    var board = window.VIEW.boards.strategy;
    var box = document.getElementById("strategyBody");
    box.innerHTML = "";
    cats.forEach(function (cname) {
      var s = board[cname];
      if (!s) {
        box.innerHTML += '<div class="empty"><h3>' + cname + "</h3><p>策略分析数据待积累</p></div>";
        return;
      }
      var c = s.rule_conclusion;
      var verdictCls = c.verdict === "GO" ? "go" : "nogo";
      var verdictTxt = { GO: "GO · 建议进入", NOGO: "NOGO · 暂不建议", "观察": "观察 · 信号混合" }[c.verdict];
      var ps = s.player_structure;
      var price = s.price_band;
      // 价格带过多时合并展示（取商品数 TOP12 的带）
      var bands = price.bands.slice().sort(function (a, b) { return b.cnt - a.cnt; }).slice(0, 12);
      bands.sort(function (a, b) { return price.bands.indexOf(a) - price.bands.indexOf(b); });
      var maxCnt = Math.max.apply(null, bands.map(function (b) { return b.cnt; }).concat([1]));
      var hist = bands.map(function (b) {
        var cls = b.price_bin === (price.hottest || {}).price_bin ? " hot"
          : (price.gap && b.price_bin === price.gap.price_bin ? " gap" : "");
        return '<div class="ph-col"><span class="ph-n">' + b.cnt + '</span>' +
          '<div class="ph-bar' + cls + '" style="height:' + Math.max(6, Math.round(b.cnt / maxCnt * 100)) + '%"></div>' +
          '<span class="ph-l">' + b.price_bin + "</span></div>";
      }).join("");
      var skuRows = s.sku_matrix.map(function (e) {
        return "<tr><td class='sku-role'>" + e.brand + "</td>" +
          "<td>引流：" + ((e["引流款"] || {}).price_bin || "—") + "<br><span class='t-sub'>" + (((e["引流款"] || {}).name || "").slice(0, 18)) + "</span></td>" +
          "<td>利润：" + ((e["利润款"] || {}).price_bin || "—") + "<br><span class='t-sub'>" + (((e["利润款"] || {}).name || "").slice(0, 18)) + "</span></td>" +
          "<td>复购：" + ((e["复购款"] || {}).price_bin || "—") + "</td></tr>";
      }).join("");
      var llmHtml = s.llm_conclusion
        ? '<div class="llm-body">' + mdLite(s.llm_conclusion.text) + '</div>' +
          '<div class="t-sub" style="margin-top:8px">来源：' + s.llm_conclusion.engine + "</div>"
        : '<div class="rule-note">LLM 综合研判未启用或调用失败，当前为规则引擎结论。配置 KIMI_API_KEY 后重跑 build_view 即可接入。</div>';

      box.innerHTML +=
        '<div class="strat-hero"><div class="verdict ' + verdictCls + '">' + verdictTxt + "</div>" +
        '<div class="sh-body"><div class="sh-title">' + c.title + "</div>" +
        '<div class="sh-reason">' + c.reasons.map(function (r) { return "· " + r; }).join("<br>") + "</div>" +
        '<div class="sh-meta"><span>目标客单价带：<b>' + (c.price_band || "—") + "</b></span>" +
        "<span>样本：<b>" + s.sample_size + "</b> 款上榜商品</span></div></div></div>" +

        '<div class="analytics">' +
        '<div class="ana-card"><div class="ac-head"><b><span class="ac-idx">01</span>市场规模 · ' + cname + "</b></div>" +
        '<div class="ac-body"><div style="display:flex;gap:24px;align-items:baseline">' +
        "<div><div class='t-sub'>类目 GMV（近7天）</div><div style='font-size:20px;font-weight:800'>" +
          ((s.market_size || {}).range_str || "待接入") + "</div></div>" +
        "<div><div class='t-sub'>环比增速</div><div style='font-size:20px;font-weight:800' class='" +
          ((s.mom_str || "")[0] === "+" ? "up" : "") + "'>" + (s.mom_str || "待接入") + "</div></div>" +
        "</div></div></div>" +

        '<div class="ana-card"><div class="ac-head"><b><span class="ac-idx">02</span>市场竞争程度</b>' +
        '<span class="tag ' + (ps._caliber === "brand_type" ? "tag-real" : "tag-tbs") + '">' +
          (ps._caliber === "brand_type" ? "brand_type 实测" : "品牌名单估算") + "</span></div>" +
        '<div class="ac-body"><div class="cr-bars">' +
          crBar("CR4（前4名占比）", s.concentration.cr4_str, s.concentration.cr4, s.concentration.cr4 > 0.6) +
          crBar("CR10 占比", s.concentration.cr10_str, s.concentration.cr10, false) +
        '</div><div class="t-sub" style="margin:8px 0 2px">玩家结构（金额占比）</div>' +
        '<div class="stack-bar">' +
          '<span class="sb-intl" style="width:' + Math.max(2, Math.round(ps.intl.pay_ratio * 100)) + '%" title="国际大牌 ' + ps.intl.pay_ratio_str + '">' + (ps.intl.pay_ratio > 0.08 ? ps.intl.pay_ratio_str : "") + "</span>" +
          '<span class="sb-new" style="width:' + Math.max(2, Math.round(ps["new"].pay_ratio * 100)) + '%" title="新锐 ' + ps["new"].pay_ratio_str + '">' + (ps["new"].pay_ratio > 0.08 ? ps["new"].pay_ratio_str : "") + "</span>" +
          '<span class="sb-white" style="width:' + Math.max(2, Math.round(ps.white.pay_ratio * 100)) + '%" title="白牌 ' + ps.white.pay_ratio_str + '">' + (ps.white.pay_ratio > 0.08 ? ps.white.pay_ratio_str : "") + "</span>" +
        "</div>" +
        '<div class="stack-legend"><span><i style="background:#3b357a"></i>国际大牌</span>' +
        "<span><i style=\"background:#533afd\"></i>新锐品牌</span>" +
        "<span><i style=\"background:#b6b9c4\"></i>白牌/未区分</span></div></div></div>" +

        '<div class="ana-card full"><div class="ac-head"><b><span class="ac-idx">03</span>供给侧结构</b></div>' +
        '<div class="ac-body"><div style="display:grid;grid-template-columns:1fr 1.4fr;gap:22px">' +
        "<div><div class='t-sub'>价格带分布（商品数）· 红=最卷 " + (price.hottest || {}).price_bin +
          " · 虚线=空白 " + ((price.gap || {}) || {}).price_bin + "</div>" +
          '<div class="price-hist">' + hist + "</div></div>" +
        "<div><div class='t-sub'>TOP 玩家 SKU 矩阵</div>" +
          '<table class="sku-matrix"><thead><tr><th>品牌</th><th>引流款</th><th>利润款</th><th>复购款</th></tr></thead><tbody>' +
          skuRows + "</tbody></table></div>" +
        "</div></div></div>" +

        '<div class="ana-card full"><div class="ac-head"><b><span class="ac-idx">04</span>综合研判（LLM）</b></div>' +
        '<div class="ac-body">' + llmHtml + "</div></div>" +
        "</div>";
    });
    if (!box.innerHTML) box.innerHTML = '<div class="empty"><p>请选择有数据的类目</p></div>';
  }
  window.onFilterChange(function () {
    if (document.getElementById("strategy-cards").classList.contains("active")) render();
  });
  window.renderStrategy = render;
})();
