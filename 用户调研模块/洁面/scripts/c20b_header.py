# -*- coding: utf-8 -*-
"""c20b_header.py — 读出商品榜的真实表头字段顺序 + 一行数据的完整 DOM 结构"""
import json, os, subprocess, sys, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(os.path.dirname(BASE))
TMP = os.path.join(WORKSPACE, "tmp")
WB = "http://127.0.0.1:10086/command"
SESSION = "fg-cleanser-hd"
REQ = os.path.join(TMP, "req_c20b.json")
HELPER = os.path.join(BASE, "tmp", "_helper.js")

sys.path.insert(0, os.path.join(BASE, "scripts"))
import c20_feigua_rank as C


def ev(code, wait=0):
    return C.ev(code, wait=wait)


def main():
    C.open_rank()
    t, acts = C.search("洗面奶")
    print("len:", len(t), "| 共:", C.parse_total(t), flush=True)

    # 表头：找含「带货达人」的祖先容器，列出其直接子元素文本
    hd = """(function(){
      var all=[].slice.call(document.querySelectorAll('*'));
      var hit=all.filter(function(e){return e.children.length<=2 && (e.innerText||'').trim()==='带货达人';});
      if(!hit.length) return JSON.stringify({err:'nf'});
      var p=hit[0]; for(var i=0;i<3&&p.parentElement;i++) p=p.parentElement;
      var cells=[].slice.call(p.children).map(function(c){return (c.innerText||'').trim().replace(/\\n/g,'/');});
      return JSON.stringify({tag:p.tagName, cls:String(p.className).slice(0,60), cells:cells});
    })()"""
    print("\n[表头容器]", ev(hd), flush=True)

    # 表头全量文本
    print("\n[全表头]", ev("""(function(){
      var i=document.body.innerText.indexOf('展示内容');
      return (document.body.innerText||'').slice(i, i+400);
    })()"""), flush=True)

    # 找一行数据容器（含「好评率」或「佣金率」且内文较长）
    row = """(function(){
      var all=[].slice.call(document.querySelectorAll('*'));
      var cand=all.filter(function(e){
        var t=(e.innerText||'').trim();
        return t.length>60 && t.length<600 && /w\\+|-w|好评率|佣金率/.test(t) && e.querySelectorAll('*').length<40;
      });
      cand.sort(function(a,b){return a.querySelectorAll('*').length-b.querySelectorAll('*').length;});
      if(!cand.length) return JSON.stringify({err:'nf'});
      var e=cand[0];
      var kids=[].slice.call(e.children).map(function(c){return (c.innerText||'').trim().replace(/\\n/g,'/');});
      return JSON.stringify({tag:e.tagName, cls:String(e.className).slice(0,60),
        nKids:e.children.length, txt:(e.innerText||'').replace(/\\n/g,'|').slice(0,400), kids:kids});
    })()"""
    print("\n[数据行容器]", ev(row), flush=True)


if __name__ == "__main__":
    main()
