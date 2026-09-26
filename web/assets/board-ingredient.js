/* board-ingredient.js — 成分增长榜 + 成分库（双 Tab）+ 成分关联弹层 */
(function () {
  // 按当前筛选类目过滤成分（成分关联商品的 category_name 命中）
  function filtered() {
    var cats = window.activeCategories();
    return window.VIEW.boards.ingredient.all.map(function (ing) {
      var prods = ing.products.filter(function (p) { return cats.indexOf(p.category_name) >= 0; });
      if (!prods.length) return null;
      var o = Object.assign({}, ing, { products: prods, product_cnt: prods.length });
      return o;
    }).filter(Boolean);
  }

  window.openIngModal = function (name) {
    var ing = window.VIEW.boards.ingredient.all.find(function (x) { return x.name === name; });
    if (!ing) return;
    document.getElementById("ingModalTitle").textContent = "成分关联 · " + name +
      (ing.multi_category ? "（多类目）" : "");
    var trees = (ing.category_paths || []).map(function (p) {
      return '<div class="cat-tree">' + p.split("/").map(function (n) {
        return '<span class="ct-node">' + n + "</span>";
      }).join('<span class="ct-sep">/</span>') + "</div>";
    }).join("");
    var rows = (ing.products || []).map(function (p) {
      return "<tr onclick=\"window.open('" + (p.detail_url || "") + "','_blank')\" style=\"cursor:pointer\">" +
        "<td>" + window.prodCell(p) + "</td><td>" + (p.brand || "—") + "</td>" +
        '<td><span class="tag tag-cat">' + (p.leaf_category_name || p.category_name || "—") + "</span></td>" +
        '<td class="num">' + (p.price_bin || "—") + "</td></tr>";
    }).join("");
    document.getElementById("ingModalBody").innerHTML =
      '<div style="font-size:12px;color:var(--ink-2);margin-bottom:6px">关联 <b>' +
      (ing.category_paths || []).length + " 个类目</b> · " + ing.product_cnt + " 款商品：</div>" +
      trees +
      '<div class="ing-modal-list"><table class="tbl" style="margin-top:8px"><thead><tr><th>关联商品</th><th>品牌</th><th>所属类目</th><th class="num">价格带</th></tr></thead><tbody>' +
      rows + "</tbody></table></div>";
    document.getElementById("ingModal").classList.add("show");
  };
  window.closeIngModal = function () { document.getElementById("ingModal").classList.remove("show"); };

  /* ---------- 成分增长榜 ---------- */
  function renderRank() {
    var list = filtered().sort(function (a, b) {
      return (b.mom === null ? -9 : b.mom) - (a.mom === null ? -9 : a.mom);
    });
    var body = document.getElementById("ingRankBody");
    body.innerHTML = list.slice(0, 30).map(function (ing, i) {
      return '<tr style="cursor:pointer" onclick="openIngModal(\'' + ing.name + "')\">" +
        "<td>" + window.rankBadge(i + 1) + "</td>" +
        '<td class="t-name">' + ing.name +
          (ing["new"] ? ' <span class="tag tag-cat">新上榜</span>' : "") + "</td>" +
        '<td class="num">' + ing.product_cnt + "</td>" +
        '<td class="num">' + (ing.share_str || "—") + "</td>" +
        '<td class="num">' + window.momCell(ing.mom_str) + "</td></tr>";
    }).join("") || '<tr><td colspan="5" class="t-sub" style="padding:20px">当前筛选范围未检出成分</td></tr>';
    // KPI
    var withMom = list.filter(function (x) { return x.mom_str; });
    var k1 = withMom[0], k2 = list.slice().sort(function (a, b) { return b.product_cnt - a.product_cnt; })[0];
    var newCnt = list.filter(function (x) { return x["new"]; }).length;
    document.getElementById("ingKpis").innerHTML =
      '<div class="kpi"><div class="k-label">增速最高成分</div><div class="k-value up">' +
        (k1 ? k1.name + " " + k1.mom_str : "待积累") + '</div><div class="k-note">' +
        (k1 ? "关联商品 " + k1.product_cnt + " 款" : "需 7 天前快照") + "</div></div>" +
      '<div class="kpi"><div class="k-label">覆盖最广成分</div><div class="k-value">' +
        (k2 ? k2.name + " · " + k2.product_cnt + " 款" : "—") + '</div><div class="k-note">按关联商品数</div></div>' +
      '<div class="kpi"><div class="k-label">本期新上榜成分</div><div class="k-value">' + newCnt +
        ' 个</div><div class="k-note">今天上榜、7 天前未上榜</div></div>';
  }

  /* ---------- 成分库双 Tab ---------- */
  function renderLib() {
    var list = filtered();
    var g = list.slice().sort(function (a, b) {
      return (b.mom === null ? -9 : b.mom) - (a.mom === null ? -9 : a.mom);
    }).slice(0, 30);
    document.getElementById("libGrowthBody").innerHTML = g.map(function (ing, i) {
      return '<tr style="cursor:pointer" onclick="openIngModal(\'' + ing.name + "')\">" +
        "<td>" + window.rankBadge(i + 1) + "</td>" +
        '<td class="t-name">' + ing.name + "</td>" +
        '<td class="num">' + window.momCell(ing.mom_str) + "</td>" +
        '<td class="num">' + ing.product_cnt + "</td>" +
        '<td class="num">' + (ing.share_str || "—") + "</td>" +
        '<td style="text-align:center">' + (ing.multi_category ? '<span class="tag tag-cat">多类目</span>' : "—") + "</td></tr>";
    }).join("");
    var h = list.slice().sort(function (a, b) { return (b.heat || 0) - (a.heat || 0); }).slice(0, 30);
    document.getElementById("libHeatBody").innerHTML = h.map(function (ing, i) {
      return '<tr style="cursor:pointer" onclick="openIngModal(\'' + ing.name + "')\">" +
        "<td>" + window.rankBadge(i + 1) + "</td>" +
        '<td class="t-name">' + ing.name + "</td>" +
        '<td class="num">' + (ing.heat != null ? ing.heat : "—") + "</td>" +
        '<td class="num">' + ing.product_cnt + "</td>" +
        '<td class="num">' + (ing.on_rank_freq || "—") + "</td>" +
        '<td style="text-align:center">' + (ing.multi_category ? '<span class="tag tag-cat">多类目</span>' : "—") + "</td></tr>";
    }).join("");
  }

  // Tab 切换
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("#libTabs button");
    if (!btn) return;
    document.querySelectorAll("#libTabs button").forEach(function (b) { b.classList.remove("on"); });
    btn.classList.add("on");
    document.querySelectorAll("#ingredient-lib .ptab-pane").forEach(function (p) { p.classList.remove("on"); });
    document.getElementById(btn.dataset.pane).classList.add("on");
  });

  window.onFilterChange(function () {
    if (document.getElementById("global-ingredient-rank").classList.contains("active")) renderRank();
    if (document.getElementById("ingredient-lib").classList.contains("active")) renderLib();
  });
  window.renderIngRank = renderRank;
  window.renderIngLib = renderLib;
})();
