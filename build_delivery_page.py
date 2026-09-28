# -*- coding: utf-8 -*-
"""
把 xhs-scraper 工具包（zip）内嵌进一个自包含 HTML 下载页。

用途：聊天窗口发不出 zip / 网盘不方便时，把这个 HTML 上传到资料库拿到分享链接，
对方点开链接按一个按钮就能还原出完整的 zip；下载按钮万一被拦，
页面底部还内嵌了每个文件的源码，可以直接手动复制。

用法：
    python build_delivery_page.py
产出：
    _交接包/xhs-scraper_下载页.html
"""
import base64
import html
import io
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, "xhs-scraper")
ZIP = os.path.join(HERE, "xhs-scraper_小红书采集工具包_v1.zip")
OUT = os.path.join(HERE, "xhs-scraper_下载页.html")

# zip 里要一起内嵌源码的文件后缀
SRC_EXT = (".py", ".yaml", ".bat", ".md")


def esc(s):
    return html.escape(s, quote=True)


def main():
    with open(ZIP, "rb") as f:
        raw = f.read()
    b64 = base64.b64encode(raw).decode("ascii")
    zsize_kb = len(raw) / 1024.0

    z = zipfile.ZipFile(io.BytesIO(raw))
    names = z.namelist()

    # ---- 文件树 + 每个文件的源码 ----
    tree_rows = []
    src_blocks = []
    for n in sorted(names):
        base = n.split("/", 1)[1] if "/" in n else n
        info = z.getinfo(n)
        tree_rows.append(
            '<tr><td class="mono">%s</td><td class="num">%s</td></tr>'
            % (esc(base), esc("%.1f KB" % (info.file_size / 1024.0)))
        )
        if n.lower().endswith(SRC_EXT):
            try:
                txt = z.read(n).decode("utf-8")
            except UnicodeDecodeError:
                txt = z.read(n).decode("utf-8", "replace")
            src_blocks.append(
                '<details class="file"><summary><span class="mono">%s</span>'
                '<span class="sz">%.1f KB</span></summary>'
                '<pre class="code">%s</pre></details>'
                % (esc(base), info.file_size / 1024.0, esc(txt))
            )

    readme = z.read("xhs-scraper/README.md").decode("utf-8")

    css = """
*{box-sizing:border-box}
body{margin:0;background:#f6f7f9;color:#1f2328;
 font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
 line-height:1.7;-webkit-font-smoothing:antialiased}
.wrap{max-width:900px;margin:0 auto;padding:32px 20px 72px}
header{background:#fff;border:1px solid #e6e8eb;border-radius:14px;padding:28px 28px 24px;margin-bottom:18px}
h1{margin:0 0 6px;font-size:24px;letter-spacing:.2px}
.sub{color:#6b7280;font-size:14px;margin:0}
.badges{margin-top:14px;display:flex;flex-wrap:wrap;gap:8px}
.badge{background:#eef2ff;color:#3b4ea0;border:1px solid #dbe2ff;border-radius:999px;
 padding:3px 11px;font-size:12.5px}
.card{background:#fff;border:1px solid #e6e8eb;border-radius:14px;padding:24px 26px;margin-bottom:18px}
h2{margin:0 0 14px;font-size:17px;padding-left:11px;border-left:3px solid #4f6ef7}
h3{margin:20px 0 8px;font-size:15px;color:#374151}
p{margin:9px 0}
ul,ol{margin:9px 0;padding-left:22px}
li{margin:5px 0}
.mono{font-family:ui-monospace,SFMono-Regular,Consolas,"Courier New",monospace}
code{background:#f2f4f7;border:1px solid #e6e8eb;border-radius:4px;padding:1px 5px;
 font-size:13px;font-family:ui-monospace,SFMono-Regular,Consolas,monospace}
pre{background:#f8f9fb;border:1px solid #e6e8eb;border-radius:8px;padding:12px 14px;
 overflow:auto;font-size:12.5px;line-height:1.6}
.dl{text-align:center;padding:8px 0 4px}
button.dlbtn{display:inline-block;background:#4f6ef7;color:#fff;border:0;border-radius:10px;
 padding:14px 34px;font-size:16px;font-weight:600;cursor:pointer;box-shadow:0 2px 8px rgba(79,110,247,.25)}
button.dlbtn:hover{background:#3f5ce0}
button.dlbtn:active{transform:translateY(1px)}
.dlhint{color:#6b7280;font-size:13px;margin-top:12px}
.dlstate{margin-top:12px;font-size:13.5px;min-height:20px}
.dlstate.ok{color:#15803d}
.dlstate.err{color:#b91c1c}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{border:1px solid #e6e8eb;padding:7px 10px;text-align:left;vertical-align:top}
th{background:#f2f4f7;font-weight:600}
td.num{text-align:right;white-space:nowrap;color:#6b7280;width:80px}
td.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12.5px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:700px){.grid{grid-template-columns:1fr}}
.box{background:#f8f9fb;border:1px solid #e6e8eb;border-radius:10px;padding:14px 16px}
.box .t{font-weight:600;margin-bottom:6px;font-size:14px}
.box .d{font-size:13.5px;color:#4b5563}
details.file{border:1px solid #e6e8eb;border-radius:8px;margin-bottom:8px;background:#fff}
details.file>summary{cursor:pointer;padding:9px 14px;font-size:13.5px;
 display:flex;justify-content:space-between;align-items:center}
details.file>summary .sz{color:#9ca3af;font-size:12px}
pre.code{max-height:420px;font-size:12px;background:#fbfcfd;border:0;border-top:1px solid #eef0f3}
.warn{background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;padding:12px 16px;font-size:13.5px;color:#7c2d12}
.ok-note{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:12px 16px;font-size:13.5px;color:#166534}
footer{color:#9ca3af;font-size:12.5px;text-align:center;margin-top:30px}
.step{display:flex;gap:10px;margin-bottom:10px}
.step .n{flex:0 0 24px;height:24px;border-radius:50%;background:#4f6ef7;color:#fff;
 font-size:13px;display:flex;align-items:center;justify-content:center;font-weight:600}
.step .c{font-size:14px}
"""

    js = """
var B64 = "__B64__";
function b64ToBytes(s){
  var bin = atob(s);
  var len = bin.length;
  var arr = new Uint8Array(len);
  for (var i = 0; i < len; i++) arr[i] = bin.charCodeAt(i);
  return arr;
}
function download(){
  var st = document.getElementById('dlstate');
  try{
    var bytes = b64ToBytes(B64);
    var blob = new Blob([bytes], {type:'application/zip'});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'xhs-scraper_小红书采集工具包_v1.zip';
    document.body.appendChild(a);
    a.click();
    setTimeout(function(){
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 1500);
    st.className = 'dlstate ok';
    st.textContent = '已触发下载（__SIZE__）。若浏览器没反应，看下方「备用方式」。';
  }catch(e){
    st.className = 'dlstate err';
    st.textContent = '下载失败：' + e.message + ' —— 请用下方备用方式。';
  }
}
function fallbackCopy(id){
  var pre = document.getElementById(id);
  var t = pre.textContent;
  var ta = document.createElement('textarea');
  ta.value = t;
  document.body.appendChild(ta);
  ta.select();
  try{ document.execCommand('copy'); alert('已复制，新建同名文件粘贴即可。'); }
  catch(e){ alert('复制失败，请手动全选复制。'); }
  document.body.removeChild(ta);
}
document.addEventListener('DOMContentLoaded', function(){
  var b = document.getElementById('dlbtn');
  if (b) b.addEventListener('click', download);
});
"""

    js = js.replace("__B64__", b64).replace("__SIZE__", "%.0f KB" % zsize_kb)

    html_out = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>小红书采集工具包 v1 · 下载</title>
<style>__CSS__</style>
</head>
<body>
<div class="wrap">

<header>
  <h1>小红书采集工具包 v1 · 下载</h1>
  <p class="sub">搜关键词 → 抓笔记正文与评论 → 过滤水军 → 出需求/痛点洞察文档。换一个类目只要改一份 YAML。</p>
  <div class="badges">
    <span class="badge">17 个文件</span>
    <span class="badge">__SIZE__</span>
    <span class="badge">内置 洁面 / 眼油 两套配置</span>
    <span class="badge">已实测：115 篇笔记 / 802 条评论</span>
  </div>
</header>

<div class="card">
  <h2>① 下载工具包</h2>
  <div class="dl">
    <button class="dlbtn" id="dlbtn">⬇ 下载 zip（__SIZE__）</button>
    <div class="dlhint">点一下即可，zip 已完整内嵌在本页面里，不依赖任何网盘。</div>
    <div class="dlstate" id="dlstate"></div>
  </div>
  <div class="warn" style="margin-top:18px">
    <b>备用方式</b>：如果上面这个按钮点了没反应（部分内置浏览器会拦下载），翻到本页最下面
    <b>「全部源码」</b>，按目录结构逐个新建文件、复制粘贴即可，效果完全一样。
  </div>
</div>

<div class="card">
  <h2>② 这是什么</h2>
  <p>一套用来<b>批量抓小红书笔记和评论、并做成用户调研语料</b>的命令行工具包。整个流程配置驱动：
  类目相关的词（关键词、品牌、需求词、痛点词）全部写在一份 YAML 里，换品类时脚本一行都不用改。</p>
  <div class="grid">
    <div class="box"><div class="t">能拿到什么</div><div class="d">
      笔记标题 / 正文 / 作者 / 点赞 / 评论数，以及每条评论的作者、内容、点赞、时间、IP 属地。</div></div>
    <div class="box"><div class="t">会产出什么</div><div class="d">
      清洗后的有效语料 JSON、需求 TOP5、痛点排行、词条表，以及一份 Markdown + HTML 的评论汇总文档。</div></div>
    <div class="box"><div class="t">靠什么抓</div><div class="d">
      本地浏览器真实登录态（Kimi WebBridge），不需要 cookie 也不碰接口签名。</div></div>
    <div class="box"><div class="t">质量控制</div><div class="d">
      内置 R1–R12 共 12 条水军/无效评论过滤规则，实测 802 条原始评论保留 450 条有效语料。</div></div>
  </div>
</div>

<div class="card">
  <h2>③ 四步上手</h2>
  <div class="step"><div class="n">1</div><div class="c">
    双击 <code>环境自检.bat</code> —— 检查 Python，自动补装 pyyaml，并确认浏览器插件已连上、小红书已登录。</div></div>
  <div class="step"><div class="n">2</div><div class="c">
    复制 <code>config/_template.yaml</code> 改名为你的类目，比如 <code>config/shampoo.yaml</code>，
    照着里面 6 处 <code>__改这里__</code> 的提示填词。</div></div>
  <div class="step"><div class="n">3</div><div class="c">
    双击 <code>开始采集.bat</code>，输入类目名（如 <code>shampoo</code>），回车，全程自动跑完。</div></div>
  <div class="step"><div class="n">4</div><div class="c">
    去 <code>产出/&lt;你的目录名&gt;/</code> 拿结果：<code>评论汇总.md</code> / <code>评论汇总.html</code>
    直接能看，<code>data/</code> 里是结构化数据。</div></div>
  <div class="ok-note" style="margin-top:16px">
    <b>想先看看效果？</b> 不动配置直接跑 <code>开始采集.bat</code> 输入 <code>cleanser</code>，
    就是用洁面类目现成配置跑一遍，跑通了再改成自己的类目。
  </div>
</div>

<div class="card">
  <h2>④ 包里有什么</h2>
  <table>
    <thead><tr><th>文件</th><th>大小</th></tr></thead>
    <tbody>__TREE__</tbody>
  </table>
  <p style="font-size:13.5px;color:#6b7280;margin-top:12px">
    <code>config/</code> 是唯一需要你改的地方；<code>scripts/</code> 通用，不同类目共用同一套。
  </p>
</div>

<div class="card">
  <h2>⑤ 换类目要填的 6 处</h2>
  <p>打开 <code>config/_template.yaml</code>，按注释填：</p>
  <ol>
    <li><b>keywords</b>：搜索用的关键词，20 个左右最好（例：洗面奶、氨基酸洁面、油皮洗面奶）</li>
    <li><b>categoryWords</b>：判定「这篇笔记说的是不是这个类目」的词</li>
    <li><b>brands</b>：这个类目的品牌名，命中会加分</li>
    <li><b>noiseWords</b>：看到就丢掉的干扰词（比如别的品类的词）</li>
    <li><b>needs / pains</b>：你想统计的需求维度和痛点维度，每个维度下面挂同义词</li>
    <li><b>outputDir</b>：产出目录名，写 <code>./产出/你的类目</code></li>
  </ol>
  <div class="warn"><b>一个坑先说在前面</b>：
  <code>outputDir</code> 写相对路径时，是按<b>工具包根目录</b>算的，不是按你命令行当前位置算的，
  所以在哪个目录下敲命令都不会跑偏。</div>
</div>

<div class="card">
  <h2>⑥ 已知限制</h2>
  <ul>
    <li>必须先在浏览器里登录小红书，且 Kimi WebBridge 守护进程处于运行状态（<code>环境自检.bat</code> 会替你确认）。</li>
    <li>小红书搜索结果的 <code>xsec_token</code> 会过期，已经抓过的笔记再抓一遍基本抓不到新东西 ——
        想扩量就换关键词再搜一轮。</li>
    <li>评论默认每篇最多取 120 条，脚本内部还会滚动加载 3 轮；特别热门的笔记可能取不全。</li>
    <li>抓太快容易被限流，脚本已按类目配置里的间隔参数限速，不要手动改小。</li>
    <li>只抓公开可见内容，不做任何登录态绕过或反爬对抗。</li>
  </ul>
</div>

<div class="card">
  <h2>⑦ 完整 README</h2>
  <details class="file"><summary><span class="mono">README.md</span><span class="sz">展开</span></summary>
    <pre class="code">__README__</pre></details>
</div>

<div class="card">
  <h2>⑧ 全部源码（备用：手动复制）</h2>
  <p style="font-size:13.5px;color:#6b7280">
    万一下载按钮用不了，就按 <code>xhs-scraper/&lt;路径&gt;</code> 建同名文件，展开下面每一项、点右上角复制粘贴。
  </p>
  __SRC__
</div>

<footer>小红书采集工具包 v1 · 全部内容已内嵌在本页面，离线可用</footer>

</div>
<script>__JS__</script>
</body>
</html>
"""

    html_out = (html_out
                .replace("__CSS__", css)
                .replace("__JS__", js)
                .replace("__TREE__", "\n".join(tree_rows))
                .replace("__README__", esc(readme))
                .replace("__SRC__", "\n".join(src_blocks))
                .replace("__SIZE__", "%.0f KB" % zsize_kb))

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html_out)

    print("OK ->", OUT)
    print("size: %.1f KB" % (os.path.getsize(OUT) / 1024.0))
    print("zip : %.1f KB / %d files" % (zsize_kb, len(names)))


if __name__ == "__main__":
    main()
