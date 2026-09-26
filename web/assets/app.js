/* app.js — 装配：加载 view.json、导航切换、初始化筛选条与看板 */
(function () {
  window.switchView = function (id) {
    document.querySelectorAll("section.view").forEach(function (s) { s.classList.remove("active"); });
    document.getElementById(id).classList.add("active");
    // 导航高亮
    document.querySelectorAll(".nav-item[data-target], .nav-more-item[data-target]").forEach(function (b) {
      b.classList.toggle("active", b.dataset.target === id);
    });
    // 子 Tab 显隐
    var subtabs = document.getElementById("globalSubtabs");
    var isGlobal = id.indexOf("global-") === 0;
    subtabs.classList.toggle("show", isGlobal);
    if (isGlobal) {
      document.querySelectorAll(".subtab").forEach(function (b) {
        b.classList.toggle("active", b.dataset.target === id);
      });
    }
    // 渲染当前看板
    var map = {
      "global-growth": window.renderGrowth,
      "global-category-trend": window.renderTrend,
      "global-ingredient-rank": window.renderIngRank,
      "product-rank": window.renderProduct,
      "ingredient-lib": window.renderIngLib,
      "strategy-cards": window.renderStrategy,
    };
    if (map[id]) map[id](window.FilterState);
    updateEchoOnly();
  };
  function updateEchoOnly() {
    var txt = window.FilterState.market + " · " +
      (window.FilterState.categories.length ? window.FilterState.categories.join("+") : "全部类目") +
      " · " + window.FilterState.period;
    document.querySelectorAll(".f-echo").forEach(function (e) { e.textContent = txt; });
  }

  fetch("data/view.json")
    .then(function (r) { return r.json(); })
    .then(function (v) {
      window.VIEW = v;
      // 数据信息
      document.getElementById("dataInfoPop").innerHTML =
        "数据截止 <b>" + v.meta.date + "</b><br>窗口 <b>" + (v.meta.window || []).join(" ~ ") +
        "</b><br>商品级环比基期 <b>" + (v.meta.growth_base || "无·待积累") + "</b>";
      document.getElementById("gg-window").textContent = (v.meta.window || []).join(" ~ ");
      document.getElementById("siteFooter").innerHTML =
        "数据源：抖音电商罗盘（实测）· 快照 " + v.meta.date + " · 样本 " +
        v.boards.product.rows.length + " 款商品 · 成分 " + v.boards.ingredient.all.length +
        " 个 · <b>禁止编造</b>：算不出的标「待积累/待接入」";
      // 装配筛选条
      document.querySelectorAll(".filters[data-board]").forEach(function (el) {
        window.mountFilterBar(el);
      });
      // 导航
      document.querySelectorAll(".nav-item[data-target], .nav-more-item[data-target]").forEach(function (b) {
        b.addEventListener("click", function () { window.switchView(b.dataset.target); });
      });
      document.querySelectorAll(".subtab").forEach(function (b) {
        b.addEventListener("click", function () { window.switchView(b.dataset.target); });
      });
      // hash 路由：支持 #页id 深链接 + 浏览器前进后退
      var VALID = ["global-growth","global-category-trend","global-ingredient-rank","product-rank","ingredient-lib","strategy-cards"];
      function fromHash() {
        var h = (location.hash || "").replace(/^#/, "");
        window.switchView(VALID.indexOf(h) >= 0 ? h : "global-growth");
      }
      window.addEventListener("hashchange", fromHash);
      // switchView 内同步 hash（不触发 hashchange 循环）
      var origSwitch = window.switchView;
      window.switchView = function (id) {
        if (("#" + id) !== location.hash) { try { history.replaceState(null, "", "#" + id); } catch (e) {} }
        origSwitch(id);
      };
      fromHash();
    })
    .catch(function (e) {
      document.body.innerHTML = '<div style="padding:60px;text-align:center;color:#64748d">' +
        "view.json 加载失败：" + e + "<br>请先跑 python3 data-mart/build_view.py</div>";
    });
})();
