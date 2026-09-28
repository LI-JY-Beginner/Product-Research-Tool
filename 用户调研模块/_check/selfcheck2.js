// 页面自检（多品类版）：跑内联脚本，分别验证每个品类 tab 都能渲染
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const js = scripts.filter(s => s.trim().length > 1000).sort((a, b) => b.length - a.length)[0];
if (!js) { console.log('NO_INLINE_JS'); process.exit(1); }

function Option(t, v) { this.text = t; this.value = v; }
const _els = {};
const mkEl = id => ({
  id, textContent: '', innerHTML: '', value: '',
  classList: { contains: () => false, add: () => {}, remove: () => {}, toggle: () => {} },
  add: () => {}, appendChild: () => {}, options: [], selectedIndex: 0,
  onchange: null, onclick: null, scrollIntoView: () => {}, style: {}, dataset: {},
});
global.Option = Option;
global.document = {
  getElementById: id => (_els[id] || (_els[id] = mkEl(id))),
  createElement: () => mkEl('tmp'),
  querySelector: () => mkEl('tmp'),
  querySelectorAll: () => [],
  addEventListener: () => {},
  body: mkEl('body'),
};
global.window = {
  addEventListener: () => {}, location: { hash: '' }, scrollTo: () => {},
  localStorage: { getItem: () => null, setItem: () => {} },
};
global.localStorage = global.window.localStorage;
global.setTimeout = f => { try { f(); } catch (e) { console.log('TIMEOUT_CB_ERR', e.message); } };

// const/let 声明在 eval 词法作用域内，暴露出来供外部检查
try {
  eval(js + "\n;global.__CATS=CATS;global.__switch=switchCat;global.__cur=()=>CUR;");
} catch (e) {
  console.log('JS_RUNTIME_ERROR:', e.message);
  console.log(e.stack.split('\n').slice(0, 6).join('\n'));
  process.exit(1);
}

const CATS2 = global.__CATS || [];
const names = CATS2.map(c => c.name);
console.log('品类数:', names.length, '→', names.join(' / '));

function report(tag) {
  const body = _els['body'] || {};
  const h = body.innerHTML || '';
  console.log(`\n--- ${tag} ---`);
  console.log('  BODY innerHTML 长度:', h.length);
  console.log('  速览卡片 scard:', (h.match(/class="scard"/g) || []).length);
  console.log('  明细栏目 p0~p6:', (h.match(/id="p[0-6]"/g) || []).join(','));
  console.log('  品类 Tab 数:', (h.match(/class="tab( on)?"/g) || []).length);
  console.log('  登录过期警告:', /登录态已过期/.test(h));
  console.log('  需求 TOP 命中:', (h.match(/命中 \d+ 条/g) || []).slice(0, 5).join(' | '));
  console.log('  「暂无」占位块:', (h.match(/class="empty"/g) || []).length);
  return h;
}

report('品类1（默认）' + (names[0] ? ' ' + names[0] : ''));
const sw = global.__switch;
if (typeof sw === 'function') {
  for (let i = 1; i < names.length; i++) {
    try { sw(i); report('品类' + (i + 1) + ' ' + names[i]); }
    catch (e) { console.log('switchCat 失败:', e.message); }
  }
} else {
  console.log('未找到 switchCat，跳过切换测试');
}
