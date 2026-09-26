"""LLM 接入：Kimi API，策略台综合研判。

- API key 从环境变量或项目根 .env 读（KIMI_API_KEY），绝不硬编码
- llm_conclude(structured_data)：结构化数据 → prompt → Kimi 自然语言综合研判
- 失败降级：调用失败时返回 None，调用方用规则引擎结论兜底
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector import config


def _load_api_key():
    key = os.environ.get(config.LLM["env_key"])
    if key:
        return key
    env_fp = os.path.join(config.BASE_DIR, ".env")
    if os.path.exists(env_fp):
        with open(env_fp, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(config.LLM["env_key"] + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _build_prompt(d):
    """把策略台结构化数据组装成 prompt。"""
    def p(x):
        return "未知" if x is None else ("%.0f%%" % (x * 100))
    size = d.get("market_size") or {}
    conc = d.get("concentration") or {}
    players = d.get("player_structure") or {}
    price = d.get("price_band") or {}
    rule = d.get("rule_conclusion") or {}
    sku_lines = []
    for e in (d.get("sku_matrix") or [])[:5]:
        sku_lines.append("- %s：引流款 %s(%s) / 利润款 %s(%s)" % (
            e["brand"],
            (e.get("引流款") or {}).get("name", "—"), (e.get("引流款") or {}).get("price_bin", "—"),
            (e.get("利润款") or {}).get("name", "—"), (e.get("利润款") or {}).get("price_bin", "—")))
    bands_raw = price.get("bands") or []
    # 价格带过碎时按商品数聚合到 TOP8 展示，避免 prompt 过长
    bands_sorted = sorted(bands_raw, key=lambda b: b["cnt"], reverse=True)
    bands = "、".join("%s(%d款)" % (b["price_bin"], b["cnt"]) for b in bands_sorted[:8])
    if len(bands_sorted) > 8:
        bands += " 等共 %d 个价格带" % len(bands_sorted)
    prompt = """你是美妆电商选品顾问。基于以下抖音罗盘实测数据，对「%s」类目给出能否进入的综合研判。

【市场规模】GMV 区间：%s；环比增速：%s
【竞争集中度】CR4（前4名金额占比）：%s；CR10：%s
【玩家结构】国际大牌金额占比 %s / 新锐品牌 %s / 白牌 %s（样本 %d 款上榜商品）
【价格带分布】%s；最卷价格带：%s；空白带：%s
【TOP玩家 SKU 结构】
%s
【规则引擎初判】%s（理由：%s）

请输出：
1. GO 或 NOGO 结论（一行，加粗）
2. 3-5 条核心理由（引用上面的具体数据）
3. 建议的细分方向（结合成分/功效趋势，如数据中无成分信息则说明）
4. 建议的目标客单价带（具体价格区间）
要求：只依据给定数据，不编造数字；语言精炼，面向业务决策。""" % (
        d.get("category"),
        size.get("range_str") or "未知",
        ("%.1f%%" % (d["mom"] * 100)) if d.get("mom") is not None else "未知",
        p(conc.get("cr4")), p(conc.get("cr10")),
        p((players.get("intl") or {}).get("pay_ratio")),
        p((players.get("new") or {}).get("pay_ratio")),
        p((players.get("white") or {}).get("pay_ratio")),
        d.get("sample_size") or 0,
        bands or "未知",
        (price.get("hottest") or {}).get("price_bin", "未知"),
        (price.get("gap") or {}).get("price_bin", "无明显空白"),
        "\n".join(sku_lines) or "—",
        rule.get("verdict", "—"), "；".join(rule.get("reasons") or []) or "—",
    )
    return prompt


def llm_conclude(structured_data, timeout=60):
    """调 Kimi 输出综合研判。失败返回 None（调用方用规则引擎兜底）。"""
    key = _load_api_key()
    if not key:
        print("[llm] 未找到 %s，走规则引擎兜底" % config.LLM["env_key"])
        return None
    import urllib.request
    payload = {
        "model": config.LLM["model"],
        "messages": [
            {"role": "system", "content": "你是美妆电商选品顾问，只依据给定数据做研判，不编造数字。"},
            {"role": "user", "content": _build_prompt(structured_data)},
        ],
        "temperature": 0.3,
    }
    req = urllib.request.Request(
        config.LLM["base_url"] + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read().decode("utf-8"))
        text = resp["choices"][0]["message"]["content"]
        return {"text": text, "engine": "kimi:" + config.LLM["model"]}
    except Exception as e:
        print("[llm] 调用失败：%s，走规则引擎兜底" % e)
        return None
