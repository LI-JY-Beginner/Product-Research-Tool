# data 分支 · 美妆数据看板采集数据

本分支专门存放工作台采集到的**真实数据**，与 main 分支的代码分离。

## 目录结构

```
data/
  raw/
    <日期>/                          # 每日快照
      compass_product_rank.json      # 罗盘商品榜（TOP200/类目，含图与链接）
      compass_category_overview.json # 罗盘类目概览（类目级环比 out_period_ratio）
      compass_category_mining.json   # 罗盘类目挖掘（成交增速 + 需求供给比）
      chanmama_product_rank.json     # 蝉妈妈商品库
      chanmama_ingredient.json       # 蝉妈妈美妆属性分析（成分榜 × 3 窗口）
    dayboards/<日期>/<cate_key>.json # 罗盘单日榜（动能增速的数据底座）
web/data/
  view.json                          # 前端视图模型（build_view.py 组装产物）
  ingredients_by_cate.json           # 成分 × 类目索引
  products_by_cate.json              # 商品 × 类目索引
```

## 数据口径

- **罗盘**：官方区间值（GMV 主口径）；动能增速 = 名次口径（榜位分 201−名次，双窗口 7 天）
- **蝉妈妈**：预估口径（成分/带货结构/画像），GMV 不主用
- 口径细节见 main 分支 `需求挖掘/罗盘后台数据字段手册.md` 与 `蝉妈妈后台数据字段手册.md`

## 更新方式

在主仓工作区跑完采集后，把 `data/` 与 `web/data/` 同步到本分支提交。
