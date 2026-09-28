# -*- coding: utf-8 -*-
"""c25_table_probe.py — 探测商品榜的真实表格结构（tr/td 列对齐），替代脆弱的 innerText 行解析"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import c20_feigua_rank as C

TMP = C.TMP

JS_TABLES = """(function(){
  var ts=[].slice.call(document.querySelectorAll('table'));
  return JSON.stringify({nTables:ts.length, info:ts.map(function(t){
    var trs=[].slice.call(t.querySelectorAll('tr'));
    return {nTr:trs.length, sample:[0,1,2].map(function(i){
      var tr=trs[i]; if(!tr) return null;
      var tds=[].slice.call(tr.querySelectorAll('td,th'));
      return tds.map(function(td){ return (td.innerText||td.textContent||'').trim().replace(/\\s+/g,' ').slice(0,60); });
    })};
  })});
})()"""

JS_ROWS = """(function(){
  // 找包含 gid 链接的那些行容器
  var as=[].slice.call(document.querySelectorAll('a[href*="gid="]'));
  var out=[]; var seen={};
  for(var i=0;i<as.length;i++){
    var a=as[i]; var h=a.getAttribute('href')||'';
    var tr=a.closest('tr'); if(!tr) continue;
    if(seen[h]) continue; seen[h]=1;
    var tds=[].slice.call(tr.querySelectorAll('td'));
    out.push({href:h, nTd:tds.length, tds:tds.map(function(td){
      return (td.innerText||td.textContent||'').trim().replace(/\\s+/g,' ').slice(0,80);})});
    if(out.length>=4) break;
  }
  return JSON.stringify({n:out.length, rows:out});
})()"""


def main():
    C.open_rank()
    t, acts = C.search("洗面奶")
    print("len:", len(t), "动作:", acts[0] if acts else "", flush=True)
    d = C.ev(JS_TABLES)
    try:
        d = json.loads(d) if isinstance(d, str) else d
    except Exception:
        pass
    print("\n=== tables ===", flush=True)
    print(json.dumps(d, ensure_ascii=False, indent=1)[:3000], flush=True)
    d2 = C.ev(JS_ROWS)
    try:
        d2 = json.loads(d2) if isinstance(d2, str) else d2
    except Exception:
        pass
    print("\n=== rows with gid ===", flush=True)
    print(json.dumps(d2, ensure_ascii=False, indent=1)[:3000], flush=True)
    open(os.path.join(TMP, "c25_table.json"), "w", encoding="utf-8").write(
        json.dumps({"tables": d, "rows": d2}, ensure_ascii=False, indent=1))
    print("\n已存 tmp/c25_table.json", flush=True)


if __name__ == "__main__":
    main()
