"""罗盘 / 蝉妈妈 采集与计算配置（单一事实源）。

所有 cid、接口、口径常量集中在此，改动只动这里。
"""
import os

# ---------- 罗盘 ----------
INDUSTRY_ID = 5  # 个护家清

COMPASS = {
    "base": "https://compass.jinritemai.com",
    "product_rank": "/compass_api/shop/product/product_rank/market_hot_sale",
    "category_overview": "/compass_api/shop/product/product_chance_market/category_overview_price_band_distribution",
    "category_mining_list": "/compass_api/shop/product/product_chance_market/dig_cate_list",
    "category_mining_cards": "/compass_api/shop/product/product_chance_market/dig_cate_cards",
    "cate_list": "/compass_api/config_center/category/cate_list",
}

# 商品榜 date_type 预设值（罗盘不支持自然日自定义 date_type=7）
DATE_TYPE = {"近1天": 2, "近7天": 21, "近30天": 23}

# 商品榜翻页：服务端固定 page_size=10，TOP200 需 20 页
RANK_PAGE_SIZE = 10
RANK_MAX_PAGE = 20  # 200 / 10

# ---------- 类目树（罗盘实测 cid）----------
# 一级类目（19 个，全列出；仅个护家清有完整树）
LEVEL1 = [
    {"cid": 5, "name": "个护家清", "has_data": True},
    {"cid": 6, "name": "美妆", "has_data": False},
    {"cid": 7, "name": "服饰内衣", "has_data": False},
    {"cid": 8, "name": "智能家居", "has_data": False},
    {"cid": 9, "name": "生鲜", "has_data": False},
    {"cid": 10, "name": "母婴宠物", "has_data": False},
    {"cid": 11, "name": "鲜花园艺", "has_data": False},
    {"cid": 12, "name": "食品饮料", "has_data": False},
    {"cid": 13, "name": "3C数码家电", "has_data": False},
    {"cid": 14, "name": "图书教育", "has_data": False},
    {"cid": 15, "name": "鞋靴箱包", "has_data": False},
    {"cid": 16, "name": "运动户外", "has_data": False},
    {"cid": 17, "name": "钟表配饰", "has_data": False},
    {"cid": 18, "name": "珠宝文玩", "has_data": False},
    {"cid": 19, "name": "医疗健康", "has_data": False},
    {"cid": 20, "name": "酒类", "has_data": False},
    {"cid": 21, "name": "滋补保健", "has_data": False},
    {"cid": 22, "name": "原料包装", "has_data": False},
    {"cid": 23, "name": "玩具乐器", "has_data": False},
]

# 个护家清 → 个人护理(二级) → 三级 → 四级（真实 cid，实测）
# 本轮只跑通 面部洗护 + 眼部护理（has_data=True）
CATEGORY_TREE = {
    "cid": 5, "name": "个护家清", "children": [
        {"cid": 1000003462, "name": "个人护理", "children": [
            {"cid": 1000003463, "name": "面部洗护", "has_data": True, "children": [
                {"cid": 1000003476, "name": "化妆水/爽肤水"},
                {"cid": 1000003477, "name": "乳液"},
                {"cid": 1000003478, "name": "面霜"},
                {"cid": 1000003479, "name": "面部精华"},
                {"cid": 1000003480, "name": "面部磨砂/去角质"},
                {"cid": 1000003481, "name": "洁面"},
                {"cid": 1000003482, "name": "面膜"},
                {"cid": 1000003483, "name": "面部护理套装"},
                {"cid": 1000003484, "name": "护肤体验装/便携装"},
                {"cid": 1000003485, "name": "防晒霜"},
                {"cid": 1000003486, "name": "防晒喷雾"},
                {"cid": 1000003487, "name": "T区护理"},
                {"cid": 1000003488, "name": "卸妆"},
                {"cid": 1000003489, "name": "面部精油"},
                {"cid": 1000003490, "name": "剃须啫喱/剃须膏/剃须泡"},
                {"cid": 1000003491, "name": "须后水"},
            ]},
            {"cid": 1000003464, "name": "手部洗护", "has_data": False},
            {"cid": 1000003465, "name": "身体清洁", "has_data": False},
            {"cid": 1000003466, "name": "身体护理", "has_data": False},
            {"cid": 1000003467, "name": "唇部护理", "has_data": False},
            {"cid": 1000003468, "name": "私处洗护", "has_data": False},
            {"cid": 1000003469, "name": "眼部护理", "has_data": True, "children": [
                {"cid": 1000003550, "name": "眼霜"},
                {"cid": 1000003551, "name": "眼膜"},
                {"cid": 1000003552, "name": "眼胶/啫喱"},
                {"cid": 1000003553, "name": "眼部精华"},
                {"cid": 1000003554, "name": "眼部护理套装"},
            ]},
            {"cid": 1000003470, "name": "洗护美用具", "has_data": False},
            {"cid": 1000003471, "name": "洗发护发", "has_data": False},
            {"cid": 1000003472, "name": "染发烫发", "has_data": False},
            {"cid": 1000003473, "name": "假发", "has_data": False},
            {"cid": 1000003474, "name": "口腔护理", "has_data": False},
            {"cid": 1000003475, "name": "成人护理", "has_data": False},
        ]},
        {"cid": 1000004647, "name": "家清纸品", "has_data": False},
    ],
}

# 本轮采集目标（三级类目）
TARGET_CATEGORIES = [
    {"name": "面部洗护", "level3": 1000003463, "category_id": "1000003462,1000003463",
     "path": "个护家清/个人护理/面部洗护"},
    {"name": "眼部护理", "level3": 1000003469, "category_id": "1000003462,1000003469",
     "path": "个护家清/个人护理/眼部护理"},
]

# ---------- 蝉妈妈 ----------
CHANMAMA = {
    "base": "https://www.chanmama.com",
    "ingredient_page": "/industryTrends/productConsumptionTrend",  # 美妆属性分析
}

# ---------- 口径常量 ----------
# 成分热度分初始权重（Q2 用户确认：先跑通后调整）
HEAT_WEIGHT = {"product_cnt": 0.4, "volume": 0.35, "on_rank_freq": 0.25}

# 策略台决策阈值（Q3 已对标飞瓜基准）
STRATEGY_THRESHOLD = {
    "cr4_hard": 0.60,     # CR4>60% 难进入
    "cr4_easy": 0.40,     # CR4<40% 有机会
    "rival_cnt_easy": 10,   # 目标价格带竞品数<10
    "month_sale_easy": 1000,  # 月销量>1000万（万元口径待核）
    "margin_easy": 0.50,    # 利润空间>50%
}

# ---------- 存储路径 ----------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_RAW = os.path.join(BASE_DIR, "data", "raw")
DATA_COMPUTED = os.path.join(BASE_DIR, "data", "computed")
WEB_DATA = os.path.join(BASE_DIR, "web", "data")
SNAPSHOT_KEEP_DAYS = 90  # 快照滚动窗口

# ---------- LLM（策略台综合研判，key 从 .env 读，不硬编码）----------
LLM = {
    "provider": "kimi",
    "base_url": "https://api.moonshot.cn/v1",
    "model": "kimi-k2",
    "env_key": "KIMI_API_KEY",
}
