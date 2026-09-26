# B1 探测报告 · 飞瓜商品详情页（产品调研模块）

- 生成时间：2026-09-26 00:20:17
- 飞瓜登录态：**normal**
- 样本：效妆、白云山

## 结论速览

| 问题 | 结论 |
|---|---|
| 详情页 URL 是否必须带 ts/sign | **Overview 不需要**（不带/错签都能渲染全部基础字段）；**深层 tab（带货视频等）必须带该 gid 自己的 ts/sign** —— 不带/错签时点击后接口根本不发，total 取不到 |
| 带货视频 tab 怎么点 | 三种方式**都偶发失效**（同一方法不同轮次结果不同）。**唯一稳定的是「完整 PointerEvent 序列」（M2）**；合成 `el.click()`（M1）和 CDP 真实鼠标（M3）都出现过点了没反应 |
| 抖音原视频链接从哪来 | **不要扒 DOM**（本轮 2 个样本 1 成 1 败）。列表接口 `POST /api/v3/goods/aweme/loadAwemeAnalysis` 返回 `BaseAwemeDto.AwemeShareUrl`，翻页/改排序/改 pageSize 全部可用，10/10 带链接 |
| 列表行为什么经常不渲染 | 行是懒渲染的，且是否渲染与接口无关。**接口早在点击后 0.35s 就把 24KB JSON 返给前端了** —— 别等 DOM，直接从接口取数 |

## T1 深层 tab 与 ts/sign

| URL 形态 | Overview 渲染 | 带货视频 tab 切过去 | 列表接口被调用 | 接口 total |
|---|---|---|---|---|
| 效妆 A_正确sign | ✅ (831字) | ✅ | ✅ | 2446 |
| 效妆 B_无sign | ✅ (331字) | ❌ | ❌ | None |
| 效妆 C_错sign | ✅ (325字) | ❌ | ❌ | None |
| 白云山 A_正确sign | ✅ (857字) | ✅ | ✅ | 1808 |
| 白云山 B_无sign | ✅ (344字) | ❌ | ❌ | None |
| 白云山 C_错sign | ✅ (338字) | ❌ | ❌ | None |

## T2 点击方式

| 样本 | 方式 | 返回 | 成功切到 tab | 用时 |
|---|---|---|---|---|
| 效妆 | M1_合成click | `ok` | ✅ | 3.1s |
| 效妆 | M2_完整指针序列 | `ok:带货视频:372,327` | ✅ | 3.1s |
| 效妆 | M3_CDP真实鼠标 | `ok:372,327` | ✅ | 3.1s |
| 白云山 | M1_合成click | `ok` | ✅ | 3.2s |
| 白云山 | M2_完整指针序列 | `ok:带货视频:372,327` | ✅ | 3.1s |
| 白云山 | M3_CDP真实鼠标 | `ok:372,327` | ❌ | 31.4s |

## T3 抖音原视频链接

### 效妆

- 3.1 DOM 路线：列表行渲染 ✅，页面内抖音链接 5 条 → **不可靠**（本轮另一路已出现行不渲染，抓不到链接）
- 3.2 接口路线：total=2401，一页取到 10 条，其中带 `shareUrl` 10 条；pageSize=30 取到 30 条 → **可用**

```json
{
 "awemeId": "7685312786976623915",
 "shareUrl": "https://www.douyin.com/share/video/7685312786976623915/?mid=7685312794775653161",
 "desc": "眼睛保养好，40不显老！眼周松垮有泪沟鱼尾纹的姐姐们！一定要试试这个#效妆#效妆抗皱小金瓶眼油#效妆眼部精华油",
 "duration": "1分23秒",
 "gmv": "5w-10w",
 "volume": "1000-2500",
 "blogger": "Mia✨",
 "displayId": "81079288528",
 "fans": "2.3w",
 "douyinHome": "https://www.douyin.com/user/MS4wLjABAAAA4aKfGoeXpw2X37re2a4LcuSwTtFEGy4z60kJAOgBTJj43Xe6GLMW3m6P19AtyNgY"
}
```
### 白云山

- 3.1 DOM 路线：列表行渲染 ❌，页面内抖音链接 0 条 → **不可靠**（本轮另一路已出现行不渲染，抓不到链接）
- 3.2 接口路线：total=1803，一页取到 10 条，其中带 `shareUrl` 10 条；pageSize=30 取到 30 条 → **可用**

```json
{
 "awemeId": "7673170067340659978",
 "shareUrl": "https://www.douyin.com/share/video/7673170067340659978/?mid=7673170064648833828",
 "desc": "（买一发二）拒绝虚假宣传！眼油选的好，眼周没烦恼！试试#白云山眼部精华，以油养眼！改善眼周！#国货#眼部护理#抗皱",
 "duration": "38秒",
 "gmv": "5w-10w",
 "volume": "1000-2500",
 "blogger": "白云山雅丽格护肤专卖店",
 "displayId": "68683131360",
 "fans": "262.9w",
 "douyinHome": "https://www.douyin.com/user/MS4wLjABAAAAEf5nEtsVXYW1VYnjpCqNtKNb92lUTitBPvOG19A1RreE5X9h90L3iYLAuzMdS63N"
}
```

## 落地配方（写进 01b / 02a 采集脚本）

```text
1) 打开 https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=<GID>&tab=overview&ts=..&sign=..  （newTab）
2) 等 Overview 出现「上架时间」/「近30天销量」（约 5~10s）
3) 注入 pcommon.install_hook()，再用 pcommon.click_tab_full('带货视频') 切 tab（触发接口）
4) 直接 pcommon.aweme_list(gid, page=N, size=30, sort_field='AwemeSaleGmvStr', order=1) 拿 JSON
   —— 不依赖 DOM 是否渲染出列表行
```

## 关键接口清单（均为 POST，同源 fetch 自动带 cookie）

| 接口 | 作用 | 关键字段 |
|---|---|---|
| `/api/v3/goods/aweme/loadAwemeAnalysisOverview` | 该商品视频概览 | AwemeCountStr / BloggerCountStr / AwemeSaleGmvStr / AwemeSaleCountStr |
| `/api/v3/goods/aweme/loadAwemeAnalysis` | **带货视频列表**（可分页排序） | Items[].BaseAwemeDto / BaseBloggerDto |
| `/api/v3/goods/aweme/GetAwemeMarketingKeyWordList` | 视频内容词云 | WordKeyword / AwemeCount / AwemeCountRatio |
| `/api/v3/goods/aweme/GetAwemeMarketingWordType` | 词云分类字典 | WordType / AwemeCount |
| `/api/v3/goods/aweme/search/items` + `/tags` | 筛选条件字典 / 视频标签 | FansCounts / BloggerType / AwemesDuration |
| `/api/v1/goods/CheckTabUseLevel?tabName=AwemeAnalysis` | 会员权限位 | CurtMemberLevel / MinMemberLevel / State |

请求体模板（`loadAwemeAnalysis`）：

```json
{
 "gid": "<GID>",
 "sortField": "AwemeSaleGmvStr",
 "order": 1,
 "keyword": "",
 "fromDateCode": "<YYYYMMDD 起>",
 "toDateCode": "<YYYYMMDD 止>",
 "PeriodType": 10000,
 "page": 1,
 "pageSize": 30,
 "IsReturnCount": 1
}
```

> `order`：1=降序，0=升序；`pageSize` 实测 30 可用；`PeriodType=10000` 对应页面上的「近30天」。
