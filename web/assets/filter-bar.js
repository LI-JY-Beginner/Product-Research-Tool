/* filter-bar.js — 全局筛选条：市场（含全部）+ 罗盘式级联类目（多选）+ 周期。
 * 任何变化触发 onFilterChange，所有看板订阅重算。 */

window.FilterState = {
  market: "全部",
  categories: [],   // 选中的三级类目名数组；空 = 全部有数据类目
  period: "近7天",
};
window._filterSubs = [];
window.onFilterChange = function (fn) { window._filterSubs.push(fn); };
function emitFilter() { window._filterSubs.forEach(function (f) { f(window.FilterState); }); }

/* ---------- 类目树工具 ---------- */
function l3Nodes() {
  // 从 view.category_tree 拿三级类目列表（个护家清/个人护理 下）
  var tree = window.VIEW.category_tree;
  var out = [];
  (tree.children || []).forEach(function (l2) {
    (l2.children || []).forEach(function (l3) {
      out.push({ name: l3.name, cid: l3.cid, has_data: !!l3.has_data,
                 path: tree.name + "/" + l2.name + "/" + l3.name });
    });
  });
  return out;
}
function dataCategories() { return l3Nodes().filter(function (n) { return n.has_data; }).map(function (n) { return n.name; }); }

/* 当前筛选命中的三级类目（空选 = 全部有数据类目） */
window.activeCategories = function () {
  var sel = window.FilterState.categories;
  return sel.length ? sel : dataCategories();
};

/* ---------- 级联多选组件 ---------- */
function buildCasc(container) {
  var nodes = l3Nodes();
  container.innerHTML =
    '<div class="casc-box"><span class="casc-path"></span><span class="casc-caret">▾</span></div>' +
    '<div class="casc-flyouts"><div class="casc-col"></div></div>';
  var box = container.querySelector(".casc-box");
  var col = container.querySelector(".casc-col");
  nodes.forEach(function (n) {
    var opt = document.createElement("div");
    opt.className = "casc-opt";
    opt.innerHTML = '<span><input type="checkbox" style="margin-right:6px;vertical-align:-1px" ' +
      (n.has_data ? "" : "disabled") + '> ' + n.name +
      (n.has_data ? "" : '<span class="tbs">待采集</span>') + '</span>';
    if (n.has_data) {
      opt.querySelector("input").addEventListener("change", function (e) {
        var sel = window.FilterState.categories;
        if (e.target.checked) { if (sel.indexOf(n.name) < 0) sel.push(n.name); }
        else { window.FilterState.categories = sel.filter(function (x) { return x !== n.name; }); }
        renderCascPath(box);
        syncAllCasc();
        emitFilter();
      });
    }
    opt.dataset.cname = n.name;
    col.appendChild(opt);
  });
  box.addEventListener("click", function () { container.classList.toggle("open"); });
  document.addEventListener("click", function (e) {
    if (!container.contains(e.target)) container.classList.remove("open");
  });
  renderCascPath(box);
}
function renderCascPath(box) {
  var sel = window.FilterState.categories;
  var path = box.querySelector(".casc-path");
  if (!sel.length) { path.innerHTML = '<span class="placeholder">全部有数据类目（默认）</span>'; return; }
  path.innerHTML = sel.map(function (c) {
    return '<span class="sel-pill">' + c + ' <i data-c="' + c + '">×</i></span>';
  }).join("");
  path.querySelectorAll("i").forEach(function (x) {
    x.addEventListener("click", function (e) {
      e.stopPropagation();
      window.FilterState.categories = window.FilterState.categories.filter(function (c) { return c !== x.dataset.c; });
      syncAllCasc(); emitFilter();
    });
  });
}
function syncAllCasc() {
  document.querySelectorAll(".casc").forEach(function (c) {
    renderCascPath(c.querySelector(".casc-box"));
    c.querySelectorAll(".casc-opt").forEach(function (opt) {
      var cb = opt.querySelector("input");
      if (cb) cb.checked = window.FilterState.categories.indexOf(opt.dataset.cname) >= 0;
    });
  });
}

/* ---------- 筛选条装配 ---------- */
window.mountFilterBar = function (el) {
  var markets = window.VIEW.meta.markets;
  el.innerHTML =
    '<span class="f-label">市场</span><select class="f-market"></select>' +
    '<span class="f-label">品类</span><div class="casc"></div>' +
    '<span class="f-label">周期</span><select class="f-period"></select>' +
    '<button class="f-reset">重置</button>' +
    '<span class="f-label f-echo" style="margin-left:auto;font-family:var(--mono)"></span>';
  var ms = el.querySelector(".f-market");
  markets.forEach(function (m) {
    var o = document.createElement("option");
    o.textContent = m; if (m === window.FilterState.market) o.selected = true;
    ms.appendChild(o);
  });
  ms.addEventListener("change", function () { window.FilterState.market = ms.value; emitFilter(); });
  var ps = el.querySelector(".f-period");
  window.VIEW.meta.periods.forEach(function (p) {
    var o = document.createElement("option"); o.textContent = p;
    if (p === window.FilterState.period) o.selected = true;
    ps.appendChild(o);
  });
  ps.addEventListener("change", function () { window.FilterState.period = ps.value; emitFilter(); });
  el.querySelector(".f-reset").addEventListener("click", function () {
    window.FilterState.categories = [];
    window.FilterState.market = window.VIEW.meta.default_market;
    ms.value = window.FilterState.market;
    syncAllCasc(); emitFilter();
  });
  buildCasc(el.querySelector(".casc"));
};

function updateEcho() {
  var txt = window.FilterState.market + " · " +
    (window.FilterState.categories.length ? window.FilterState.categories.join("+") : "全部类目") +
    " · " + window.FilterState.period;
  document.querySelectorAll(".f-echo").forEach(function (e) { e.textContent = txt; });
}
window.onFilterChange(updateEcho);

/* ---------- 共享渲染小件 ---------- */
window.momCell = function (momStr) {
  if (!momStr) return '<span class="tag tag-pending">待积累</span>';
  var cls = momStr[0] === "+" ? "up" : "down";
  return '<span class="' + cls + '">' + momStr + "</span>";
};
window.prodCell = function (r) {
  var img = r.image_url
    ? '<div class="prod-img real"><img src="' + r.image_url + '" loading="lazy" onerror="this.parentNode.textContent=\'图\'"></div>'
    : '<div class="prod-img">图</div>';
  return '<div class="prod">' + img + '<div><div class="t-name">' + (r.name || "—") + "</div></div></div>";
};
window.rankBadge = function (i) {
  var cls = i === 1 ? "r1" : i === 2 ? "r2" : i === 3 ? "r3" : "";
  return '<span class="rank-badge ' + cls + '">' + i + "</span>";
};
window.togglePanel = function (id) { document.getElementById(id).classList.toggle("collapsed"); };
