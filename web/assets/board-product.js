/* board-product.js — 商品榜：全量明细，随筛选联动 */
(function () {
  function render() {
    var cats = window.activeCategories();
    var rows = window.VIEW.boards.product.rows.filter(function (r) {
      return cats.indexOf(r.category_name) >= 0;
    });
    rows.sort(function (a, b) {
      return (a.category_name > b.category_name ? 1 : -1) || ((a.rank || 9999) - (b.rank || 9999));
    });
    document.getElementById("pr-sub").innerHTML =
      "罗盘商品榜 · 当前筛选 <b>" + rows.length + "</b> 款 · 点击商品行跳转真实链接";
    document.getElementById("prBody").innerHTML = rows.map(function (r) {
      return "<tr onclick=\"window.open('" + (r.detail_url || "") + "','_blank')\" style=\"cursor:pointer\">" +
        "<td>" + window.rankBadge(r.rank) + "</td>" +
        "<td>" + window.prodCell(r) + "</td>" +
        "<td>" + (r.brand || "—") + "</td>" +
        '<td class="num">' + (r.price_bin || "—") + "</td>" +
        '<td class="num">' + window.momCell(r.mom_str) + "</td>" +
        '<td><span class="tag tag-cat">' + r.category_name + "</span>" +
          (r.leaf_category_name ? '<div class="t-sub">' + r.leaf_category_name + "</div>" : "") + "</td>" +
        '<td class="num">' + (r.pay_range || "—") + "</td></tr>";
    }).join("") || '<tr><td colspan="7" class="t-sub" style="padding:24px">当前筛选范围无商品</td></tr>';
  }
  window.onFilterChange(function () {
    if (document.getElementById("product-rank").classList.contains("active")) render();
  });
  window.renderProduct = render;
})();
