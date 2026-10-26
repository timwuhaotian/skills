---
name: ziwei-doushu
description: >-
  Use when 用户想排紫微斗数命盘、看盘解盘、生成紫微命理报告 HTML（"排盘"、"帮我看看我的盘"、
  "紫微斗数"、"命盘"、"十二宫"、"看盘解读"、"算命"（紫微类）、"zi wei"、"purple star astrology"）。
  输入公历生日+出生时间+性别(+可选出生地真太阳时校正)，脚本确定性排盘（iztro 引擎，
  倪海厦《天纪》体系口径），按内置知识库撰写七维解读，产出单文件 HTML 报告。
  不适用于八字四柱、西方星座、塔罗占卜类请求。
user-invocable: true
argument-hint: "[姓名] [公历生日YYYY-MM-DD] [出生时间HH:MM] [性别男/女] [出生城市(可选)]"
---

# 紫微斗数排盘与命理报告

用户给出公历生日等信息 → `scripts/paipan.mjs` 确定性排盘出 chart.json → 你按
`reference/` 知识库撰写解读 interpretation.json → `scripts/build-report.mjs` 生成单文件
HTML 报告并打开。排盘交给脚本（数字零手算），解读由你写，页面由模板渲染。

## Step 0 · 收集信息

| 字段 | 必填 | 说明 |
|---|---|---|
| 姓名/称呼 | ✅ | 报告抬头，可用昵称 |
| 公历生日 | ✅ | YYYY-MM-DD（农历生日请先让用户换算成公历，或用万年历确认） |
| 出生时间 | ✅ | HH:MM（24 小时制）。紫微必须有时辰：不知道精确到分也没关系，先确认落在哪个时辰 |
| 性别 | ✅ | 男/女——决定大限顺逆行，不可省 |
| 出生地 | 可选 | 城市名（真太阳时校正）；也可直接给东经度数 |

- **时辰完全未知**：如实告知紫微斗数必须有时辰才能排盘，引导用户用生活场景回忆
  （天亮前/早饭后/午饭前后/傍晚天黑前后等），先缩小范围再确认；实在无法确认则停止，不要猜。
- **1986–1991 年出生**：脚本会检测中国夏令时并提示——需向用户确认所填是否夏令时钟表
  读数；若是，把时间减 1 小时后重跑排盘。
- 脚本对**时辰边界 ±15 分钟**会自动警告，此时务必与用户核对出生时间精度。

## Step 1 · 排盘

```bash
node <skill目录>/scripts/paipan.mjs --name 张三 --date 1992-06-15 --time 14:30 \
  --gender 女 --city 上海 --out /tmp/ziwei-chart.json
```

- 首次运行自动 `npm install iztro`（需网络；之后离线可用）。Node ≥ 18。
- `--city` 未收录的城市换 `--longitude 106.6`（东经度数）；无出生地加 `--no-solar`。
- 口径已内置：晚子时（23:00–23:59）按次日排盘、正月初一换年、真太阳时=钟表时+经度修正+均时差。

**读完输出再往下走**：
- `notes[]` 非空（时辰边界/夏令时/未做校正）→ 先向用户核实，必要时调整输入重跑。
- `chart.mingGong.empty: true` → 命宫空宫，`borrowedStars` 已给出所借对宫主星，解读按借星论并说明。

## Step 2 · 核对

- 12 宫地支齐全（寅丑子亥在底行）、命宫主星/五行局/四化与 `chart` 字段一致；**一切以 JSON 为准，不手工推算星曜**。
- 改动过排盘脚本后必跑回归：`node scripts/test.mjs`（13 项，含 11 组名人金标准盘）。

## Step 3 · 撰写解读

先通读 `reference/interpretation-guide.md`（总纲），再按需查 `reference/` 其他文件，写
interpretation.json（结构照抄 `examples/demo-interpretation.json`）：

```json
{
  "name": "张三",
  "intro": "一句话总评(30字内)",
  "highlights": ["天同庙守命", "…"],
  "sections": [
    {"id": "personality", "title": "性格特质", "icon": "◈", "summary": "导语", "body": ["段落", "…"]}
  ],
  "advice": ["扬长…", "避短…", "方向…"],
  "summary": "一句话总结"
}
```

- 七个维度顺序与 id：`personality` 性格特质 → `career` 事业方向 → `wealth` 财运特点 →
  `love` 感情婚姻 → `health` 健康提醒 → `family` 六亲关系 → `decadal` 大限走向；每维 200–400 字。
- 解读顺序：命宫主星+亮度 → 三方四正（命财官迁）→ 身宫 → 生年四化落宫 → 辅煞 → 大限（见 guide 第三节）。
- 大限起限岁数按五行局：水二局 2 岁、木三局 3 岁、金四局 4 岁、土五局 5 岁、火六局 6 岁；当前大限取用户今年虚岁所在区间。

## Step 4 · 生成并打开报告

```bash
node <skill目录>/scripts/build-report.mjs /tmp/ziwei-chart.json /tmp/ziwei-interpretation.json \
  -o 紫微命盘报告-张三.html
open 紫微命盘报告-张三.html
```

免责声明由脚本**逐字内置**追加，无需也不会被漏掉。

## Step 5 · 交付

口头给用户摘要：命宫主星组合+亮度、五行局、身宫、1–2 个亮点、当前大限主题；告知报告文件路径；
如 `notes` 有校正说明（真太阳时/夏令时/时辰边界）需一并转述。

## Hard rules

- 语气用倾向性表述（"倾向于/容易/建议留意"），**严禁**"注定/必然/一定会/克/大凶/短寿"（禁用词表见 guide 第五节）。
- 健康只说哪个系统"需留意"，不诊断、不提病名；财务不预测数字、不荐标的；感情不断言离婚出轨。
- 六亲维度段尾固定注明"六亲缘分论述属传统命理范畴，仅供参考"。
- 不逐字引用倪海厦《天纪》原话（其语录为 CC BY-NC-SA 非商用授权），概述思路即可。
- 星曜、亮度、四化、宫位一律以脚本 JSON 输出为准。
- 用户只要快速看盘不要 HTML 时，可只执行 Step 0–2 后口头解读，跳过 Step 4。

## Files

| path | what |
|---|---|
| `scripts/paipan.mjs` | 排盘：公历+时间+性别(+城市经度) → chart.json（iztro，含真太阳时/夏令时/晚子时口径） |
| `scripts/build-report.mjs` | chart.json + interpretation.json → 单文件 HTML 报告（暗色星穹金线风、12 宫盘、大限表，免责声明内置） |
| `scripts/test.mjs` | 回归：11 组名人金标准盘 + 空宫借星 + 晚子时等价性，共 13 项 |
| `examples/demo-interpretation.json` | interpretation.json 完整示例（林小满盘） |
| `reference/interpretation-guide.md` | 解读总纲：七步顺序、七维度写法、禁用词表、免责声明原文 |
| `reference/stars-14.md` | 十四主星：五行/特质/优劣/庙陷 |
| `reference/palaces-12.md` | 十二宫含义与看盘要点、三方四正速查 |
| `reference/si-hua.md` | 四化禄权科忌、十天干四化表、落宫思路 |
| `reference/brightness.md` | 亮度七档 + 辅星杂曜速查（吉凶属性/象征） |
| `reference/patterns.md` | 20 个常见格局：判定条件+含义 |

## Requires

- Node ≥ 18（本机为 v24）；首次运行联网装 iztro（MIT），之后纯离线。
- 排盘引擎 iztro、口径与真太阳时/夏令时算法对齐 [Renhuai123/ziwei-doushu](https://github.com/Renhuai123/ziwei-doushu)（MIT，倪海厦《天纪》体系），报告页脚已带署名。
