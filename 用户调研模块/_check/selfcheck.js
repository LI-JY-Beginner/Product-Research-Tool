// 页面自检：用 Node 跑一遍内联脚本，验证 render() 是否真的产出内容
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
global.window = { addEventListener: () => {}, location: { hash: '' }, localStorage: { getItem: () => null, setItem: () => {} } };
global.localStorage = global.window.localStorage;
global.setTimeout = f => { try { f(); } catch (e) { console.log('TIMEOUT_CB_ERR', e.message); } };

try {
  eval(js);
} catch (e) {
  console.log('JS_RUNTIME_ERROR:', e.message);
  console.log(e.stack.split('\n').slice(0, 5).join('\n'));
  process.exit(1);
}

const body = _els['body'] || {};
console.log('BODY innerHTML 长度:', (body.innerHTML || '').length);
const all = Object.entries(_els).map(([k, v]) => [k, (v.innerHTML || '').length]);
console.log('各元素:', JSON.stringify(all));

const html_all = Object.values(_els).map(v => v.innerHTML || '').join('\n');
console.log('scard 卡片数:', (html_all.match(/class="scard"/g) || []).length);
console.log('栏目 p0~p6:', (html_all.match(/id="p[0-6]"/g) || []));
console.log('是否出现登录过期警告:', /login-warn|登录态已过期|expired/.test(html_all));
