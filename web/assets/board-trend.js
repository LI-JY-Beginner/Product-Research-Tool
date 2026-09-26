/* board-trend.js — 类目增长趋势：三级全列 + 点行展开四级（真实增速/供需比） */
(function () {
  function render() {
    var b = window.VIEW.boards.trend;
    // 顶部最快类目（优先四级最快）
    var top = document.getElementById("trendTop");
    var feat = b.fastest_leaf || b.fastest;
    if (feat) {
      top.style.display = "";
      document.getElementById("trendFastName").innerHTML = feat.name +
        (b.fastest_leaf ? ' <span class="t-sub" style="font-weight:400">（四级 · 归属：' + b.fastest.name + "）</span>" : "");
      document.getElementById("trendFastMom").textContent = feat.mom_str || "待采集";
      document.getElementById("trendFastAmt").textContent = feat.pay_range || "—";
      var svg = document.getElementById("trendSpark");
      var mom = feat.mom || 0;
      var y = 60 - Math.max(-40, Math.min(40, mom * 60));
      svg.innerHTML =
        '<line x1="0" y1="100" x2="560" y2="100" stroke="#e7e8ee"/>' +
        '<polyline points="0,' + y + ' 560,' + y + '" fill="none" stroke="#533afd" stroke-width="2.5"/>' +
        '<circle cx="560" cy="' + y + '" r="4" fill="#533afd"/>' +
        '<text x="500" y="112" font-size="9" fill="#8a8d99">' + window.VIEW.meta.date + "</text>";
    } else {
      top.style.display = "none";
    }
    var tbody = document.getElementById("trendTbody");
    tbody.innerHTML = "";
    b.rows.forEach(function (r) {
      var tr = document.createElement("tr");
      tr.className = "l3-row";
      var momHtml = r.mom_str
        ? '<span class="' + (r.mom_str[0] === "+" ? "up" : "down") + '">' + r.mom_str + "</span>"
        : '<span class="tag tag-tbs">待采集</span>';
      tr.innerHTML =
        "<td><span class=\"caret\">▶</span><span class=\"t-name\">" + r.name + "</span>" +
        '<div class="t-sub">个护家清 / 个人护理</div></td>' +
        '<td><span class="tag tag-cat">三级</span></td>' +
        '<td class="num">—</td>' +
        '<td class="num">' + momHtml + (r.has_data ? ' <span class="tag tag-real">实测</span>' : "") + "</td>" +
        "<td>—</td>" +
        '<td>' + (r.has_data
          ? '<button class="link-act" data-cat="' + r.name + '">看商品榜</button>'
          : '<span class="tag tag-tbs">待采集</span>') + "</td>";
      var sub = document.createElement("tr");
      sub.className = "subcat-row";
      sub.style.display = "none";
      var leafRows = (r.children || []).map(function (c) {
        var cm = c.mom_str
          ? '<span class="' + (c.mom_str[0] === "+" ? "up" : "down") + '">' + c.mom_str + "</span>"
          : '<span class="tag tag-tbs">待采集</span>';
        return "<tr><td>" + c.name + '</td><td class="num">' + cm + '</td>' +
          '<td class="num">' + (c.demand_supply_rate != null ? c.demand_supply_rate.toFixed(2) : "—") + "</td></tr>";
      }).join("");
      sub.innerHTML = '<td colspan="6"><table class="subcat-tbl"><thead><tr><th>四级类目</th>' +
        '<th style="text-align:right">环比增速</th><th style="text-align:right">需求供给比</th></tr></thead><tbody>' +
        (leafRows || '<tr><td colspan="3" class="t-sub">无四级子类目</td></tr>') + "</tbody></table></td>";
      tr.addEventListener("click", function () {
        tr.classList.toggle("open");
        sub.style.display = sub.style.display === "none" ? "" : "none";
      });
      var btn = tr.querySelector(".link-act");
      if (btn) btn.addEventListener("click", function (e) {
        e.stopPropagation();
        window.FilterState.categories = [btn.dataset.cat];
        window.switchView("product-rank");
        window._filterSubs.forEach(function (f) { f(window.FilterState); });
      });
      tbody.appendChild(tr);
      tbody.appendChild(sub);
    });
  }
  window.onFilterChange(function () {
    if (document.getElementById("global-category-trend").classList.contains("active")) render();
  });
  window.renderTrend = render;
})();
