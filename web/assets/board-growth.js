/* board-growth.js — 增速产品看板：结论 hero + 每类目 TOP3 */
(function () {
  function render(fs) {
    var b = window.VIEW.boards.growth;
    var cats = window.activeCategories();
    // hero：当前筛选范围内 mom 最高商品（无 mom 则取第一类目第一名）
    var all = [];
    b.groups.forEach(function (g) {
      if (cats.indexOf(g.category) < 0) return;
      g.top3.forEach(function (r) { all.push(r); });
    });
    var hero = document.getElementById("ggHero");
    var withMom = all.filter(function (r) { return r.mom !== null && r.mom !== undefined; });
    var top = withMom.length
      ? withMom.sort(function (a, c) { return c.mom - a.mom; })[0]
      : (all[0] || null);
    if (top) {
      hero.style.display = "";
      document.getElementById("ggHeroName").textContent = top.name;
      document.getElementById("ggHeroSub").textContent =
        (withMom.length ? "七天内增速最快的产品" : "榜单第 1 名（商品级环比待积累）") +
        " · 类目：" + (top.leaf_category_name || top.category_name);
      document.getElementById("ggHeroGmv").innerHTML =
        top.mom_str ? top.mom_str : '<span class="tag tag-pending" style="font-size:12px">待积累</span>';
      document.getElementById("ggHeroCountry").textContent = "中国";
      document.getElementById("ggHeroPrice").textContent = top.price_bin || "—";
    } else {
      hero.style.display = "none";
    }
    // 分组
    var box = document.getElementById("ggGroups");
    box.innerHTML = "";
    b.groups.forEach(function (g) {
      if (cats.indexOf(g.category) < 0) return;
      var rows = g.top3.map(function (r, i) {
        return "<tr onclick=\"window.open('" + (r.detail_url || "") + "','_blank')\" style=\"cursor:pointer\">" +
          "<td>" + window.rankBadge(i + 1) + "</td>" +
          "<td>" + window.prodCell(r) + "</td>" +
          "<td>" + (r.brand || "—") + "</td>" +
          '<td class="num">' + (r.price_bin || "—") + "</td>" +
          '<td class="num">' + window.momCell(r.mom_str) + "</td>" +
          '<td><span class="tag tag-cat">' + (r.leaf_category_name || "—") + "</span></td>" +
          '<td class="num">' + (r.pay_range || "—") + "</td></tr>";
      }).join("");
      var momHtml = g.mom_str
        ? '<span class="' + (g.mom_str[0] === "+" ? "up" : "down") + '">' + g.mom_str + "</span>"
        : '<span class="tag tag-pending">待积累</span>';
      box.innerHTML +=
        '<div class="panel"><div class="panel-head" onclick="togglePanel(\'pnl-g-' + g.category + '\')">' +
        '<span class="caret">▼</span><h3>' + g.category + ' · 增速 TOP3</h3>' +
        '<span class="tag tag-cat">三级类目</span>' +
        '<span class="p-meta">类目环比 ' + momHtml + ' · 上榜 ' + g.total + ' 款</span></div>' +
        '<div class="panel-body" style="padding:0" id="pnl-g-' + g.category + '">' +
        '<table class="tbl"><thead><tr><th style="width:64px">名次</th><th>商品</th><th>品牌</th><th>价格带</th>' +
        '<th class="num">环比增速</th><th>所属类目</th><th class="num">支付金额区间</th></tr></thead>' +
        '<tbody>' + rows + '</tbody></table></div></div>';
    });
    if (!box.innerHTML) box.innerHTML = '<div class="empty"><p>当前筛选范围无数据</p></div>';
  }
  window.onFilterChange(function (fs) {
    if (document.getElementById("global-growth").classList.contains("active")) render(fs);
  });
  window.renderGrowth = render;
})();
