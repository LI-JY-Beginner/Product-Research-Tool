# -*- coding: utf-8 -*-
"""09 · 图片本地化
飞瓜的商品图 CDN 在本环境不可用（详情页/榜单里的商品图都是 140x140 占位图），
所以卡面统一改用「该链接 TOP 带货视频封面」——真实图、已本地化，离线可看。
产出: assets/covers/<gid>.jpg（卡面） + assets/video/<awemeId>.jpg（详情页视频缩略图）
"""
import os, sys, json, subprocess, time
import urllib.parse as up

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
COV = os.path.join(BASE, "assets", "covers")
VID = os.path.join(BASE, "assets", "video")
os.makedirs(COV, exist_ok=True)
os.makedirs(VID, exist_ok=True)

TOPN = int(os.environ.get("VID_TOPN", "8"))          # 每个链接本地化几条视频封面
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

deep = json.load(open(os.path.join(DATA, "deep.json"), encoding="utf-8"))
cards = json.load(open(os.path.join(DATA, "cards.json"), encoding="utf-8"))


def candidates(u):
    """★ 抖音 CDN 部分 URL 会 403（签名分机型），但每个封面都带飞瓜自己的 CDN 兜底：?$$dyurl=...
       优先用兜底地址，实测稳定 200。"""
    out = []
    try:
        q = up.parse_qs(up.urlparse(u).query)
        dy = (q.get("$$dyurl") or [None])[0]
        if dy:
            out.append(dy)
    except Exception:
        pass
    out.append(u)
    return out


def get(url, path):
    """先下到 .part，成功再改名 —— 不做任何删除动作"""
    if os.path.exists(path) and os.path.getsize(path) > 3000:
        return os.path.getsize(path)
    tmp = path + ".part"
    for u in candidates(url):
        for _ in range(2):
            r = subprocess.run(["curl.exe", "-s", "-o", tmp, "-w", "%{http_code} %{size_download}",
                                "--max-time", "30", "--noproxy", "*", "-L",
                                "-H", "Referer: https://dy.feigua.cn/",
                                "-H", "User-Agent: " + UA, u],
                               capture_output=True, text=True)
            try:
                code, size = r.stdout.split()
                if code == "200" and int(size) > 3000:
                    os.replace(tmp, path)
                    return int(size)
            except Exception:
                pass
            time.sleep(0.6)
    return 0


n_card, n_vid, n_fail = 0, 0, 0
for gid, d in deep.items():
    vs = d.get("videos") or []
    if not vs:
        continue
    # 视频封面
    ok_first = 0
    for v in vs[:TOPN]:
        aw = v.get("awemeId")
        u = v.get("cover")
        if not (aw and u):
            continue
        s = get(u, os.path.join(VID, "%s.jpg" % aw))
        if s:
            n_vid += 1
            if not ok_first:
                ok_first = s
                # 卡面 = TOP1 视频封面
                open(os.path.join(COV, gid + ".jpg"), "wb").write(
                    open(os.path.join(VID, "%s.jpg" % aw), "rb").read())
                n_card += 1
        else:
            n_fail += 1
    print("%s 视频%s 条 → 本地 %s 张，卡面 %s" % (gid[:12], len(vs[:TOPN]), ok_first and "OK" or "-",
                                            "OK" if os.path.exists(os.path.join(COV, gid + ".jpg")) else "-"))

print("\n卡面图 %d/%d，视频缩略图 %d 张，失败 %d" % (n_card, len(cards), n_vid, n_fail))
print("assets/covers 大小 %.1f MB，assets/video 大小 %.1f MB" % (
    sum(os.path.getsize(os.path.join(COV, f)) for f in os.listdir(COV)) / 1e6,
    sum(os.path.getsize(os.path.join(VID, f)) for f in os.listdir(VID)) / 1e6))
