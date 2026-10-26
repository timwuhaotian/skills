#!/usr/bin/env node
/**
 * 紫微命盘 HTML 报告生成器（ziwei-doushu skill）
 * chart.json (paipan.mjs 输出) + interpretation.json (LLM 按解读规范撰写) → 单文件 HTML
 *
 * interpretation.json 契约:
 * {
 *   "name": "张三",
 *   "intro": "一句话总评(30字内)",
 *   "highlights": ["贪狼庙守命", "杀破狼三合"],           // 可选, 头部亮点标签
 *   "sections": [
 *     {"id":"personality","title":"性格特质","icon":"◈","summary":"一句导语","body":["段落1","段落2"]}
 *   ],
 *   "advice": ["扬长…","避短…","近十年方向…"],            // 可选, 综合建议 3 条
 *   "summary": "一句话总结"                                // 可选, 收束引言
 * }
 * 免责声明由本脚本内置逐字追加, 不依赖 LLM 是否写入。
 *
 * 用法: node scripts/build-report.mjs chart.json interpretation.json [-o 报告.html]
 */
import fs from 'node:fs';

const args = process.argv.slice(2);
const outIdx = args.indexOf('-o');
const outPath = outIdx > -1 ? args[outIdx + 1] : null;
const files = args.filter((_, i) => i !== outIdx && i !== outIdx + 1);
if (files.length < 2) { console.error('用法: node scripts/build-report.mjs chart.json interpretation.json [-o 报告.html]'); process.exit(2); }

const chart = JSON.parse(fs.readFileSync(files[0], 'utf8'));
const interp = JSON.parse(fs.readFileSync(files[1], 'utf8'));

/* ---------- 工具 ---------- */
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
const name = interp.name || chart.input.name;
const c = chart.chart;
const tc = chart.timeCheck;

/* 命盘 4x4 布局: 地支 -> (行,列) */
const POS = { 巳: [1, 1], 午: [1, 2], 未: [1, 3], 申: [1, 4], 辰: [2, 1], 酉: [2, 4], 卯: [3, 1], 戌: [3, 4], 寅: [4, 1], 丑: [4, 2], 子: [4, 3], 亥: [4, 4] };

const MUTAGEN_CLS = { 禄: 'lu', 权: 'quan', 科: 'ke', 忌: 'ji' };
const brightCls = (b) => ({ 庙: 'bm', 旺: 'bw', 得: 'bd', 利: 'bl', 平: 'bp', 不: 'bn', 陷: 'bx' }[b] || '');

const starHtml = (s, big) => {
  const m = s.mutagen ? `<i class="mh ${MUTAGEN_CLS[s.mutagen]}">${s.mutagen}</i>` : '';
  const b = s.brightness ? `<sup class="${brightCls(s.brightness)}">${s.brightness}</sup>` : '';
  return big
    ? `<div class="star"><span class="sname">${esc(s.name)}</span>${b}${m}</div>`
    : `<span class="star sm"><span class="sname">${esc(s.name)}</span>${s.brightness ? `<sup class="${brightCls(s.brightness)}">${s.brightness}</sup>` : ''}${m}</span>`;
};

/* 命宫对宫(空宫借星用) */
const mingIdx = c.palaces.findIndex((p) => p.name === '命宫');
const opposite = c.palaces[(mingIdx + 6) % 12];

const cellHtml = (p) => {
  const [r, col] = POS[p.branch];
  const isMing = p.name === '命宫';
  let stars;
  if (p.majorStars.length) stars = p.majorStars.map((s) => starHtml(s, true)).join('');
  else stars = `<div class="star empty">空宫<span class="borrow">（借${esc(opposite.name)}：${opposite.majorStars.map((s) => esc(s.name)).join('、') || '亦空'}）</span></div>`;
  const minor = [...p.minorStars, ...p.adjectiveStars.map((n) => ({ name: n }))].map((s) => starHtml(s, false)).join('');
  return `
  <div class="cell${isMing ? ' ming' : ''}" style="grid-row:${r};grid-column:${col}">
    <div class="p-head"><span class="p-name">${esc(p.name)}</span>${p.isBodyPalace ? '<span class="tag body">身宫</span>' : ''}<span class="p-limit">${p.decadal.range[0]}–${p.decadal.range[1]}</span></div>
    <div class="p-stars">${stars}${minor ? `<div class="minor">${minor}</div>` : ''}</div>
    <div class="p-foot"><span class="p-branch">${esc(p.stem)}${esc(p.branch)}</span><span class="p-cs">${esc(p.changsheng12)}</span></div>
  </div>`;
};

const chips = [];
const chip = (k, v) => `<div class="chip"><span class="k">${k}</span><span class="v">${v}</span></div>`;
chips.push(chip('公历', esc(chart.input.solarDate)));
chips.push(chip('农历', esc(c.lunarDate)));
chips.push(chip('四柱', esc(c.chineseDate.join(' '))));
chips.push(chip('生肖 / 星座', `${esc(c.zodiac)} · ${esc(c.sign)}`));
chips.push(chip('时辰', `${esc(c.time)}${tc.applied ? `（真太阳时 ${esc(tc.trueSolarTime)}）` : ''}`));
chips.push(chip('五行局', `<b class="gold">${esc(c.wuXingJu)}</b>`));
chips.push(chip('命主 / 身主', `${esc(c.soulStar)} · ${esc(c.bodyStar)}`));
chips.push(chip('阴阳', esc(c.yinYang)));
if (tc.applied && tc.city) chips.push(chip('出生地', `${esc(tc.city)}（东经 ${tc.longitude}°）`));

const siHuaHtml = ['禄', '权', '科', '忌'].map((k) => {
  const v = c.siHua[k];
  return `<span class="sh ${MUTAGEN_CLS[k]}"><b>${k}</b>${v ? `${esc(v.star)} @ ${esc(v.palace)}(${esc(v.branch)})` : '—'}</span>`;
}).join('');

const sectionsHtml = (interp.sections || []).map((s) => `
  <section class="card sec">
    <h2><span class="icon">${s.icon ? esc(s.icon) : '✦'}</span>${esc(s.title)}</h2>
    ${s.summary ? `<p class="lead">${fmt(s.summary)}</p>` : ''}
    ${(s.body || []).map((p) => `<p>${fmt(p)}</p>`).join('')}
  </section>`).join('');

const dachengRows = [...c.palaces].sort((a, b) => a.decadal.range[0] - b.decadal.range[0]).map((p) => `
  <tr${p.name === '命宫' ? ' class="ming-row"' : ''}><td>${p.decadal.range[0]}–${p.decadal.range[1]}</td><td>${esc(p.stem)}${esc(p.branch)}</td><td>${esc(p.name)}${p.isBodyPalace ? '（身）' : ''}</td><td>${p.majorStars.map((s) => esc(s.name)).join('、') || '空宫'}</td></tr>`).join('');

const notesHtml = (chart.notes || []).length ? `
  <div class="card notice"><h2><span class="icon">⚠</span>排盘口径说明</h2><ul>${(chart.notes || []).map((n) => `<li>${esc(n)}</li>`).join('')}</ul></div>` : '';

const highlightsHtml = (interp.highlights || []).length ? `<div class="hl">${(interp.highlights || []).map((h) => `<span>${esc(h)}</span>`).join('')}</div>` : '';

const DISCLAIMER = '免责声明：本报告基于传统紫微斗数文化进行解读，仅供文化参考与自我认识之用，不构成任何医疗、心理咨询、投资、婚姻或人生重大决策的依据。命理描述反映的是传统文化中的倾向性归纳，人的命运由自身选择与努力塑造。如有健康问题请咨询执业医师，涉及重大决策请寻求专业人士帮助。';

const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>紫微命盘报告 · ${esc(name)}</title>
<style>
  :root{
    --bg0:#070b1e; --bg1:#141034; --card:rgba(255,255,255,.045); --line:rgba(230,196,115,.22);
    --gold:#e6c473; --gold-dim:#b39758; --text:#e9e7f2; --dim:#a49fc0; --faint:#7d7899;
    --lu:#7fd6a4; --quan:#ff9d80; --ke:#8ab8ff; --ji:#b9b3d6;
  }
  *{margin:0;padding:0;box-sizing:border-box}
  body{background:radial-gradient(1200px 800px at 70% -10%, #241a4d 0%, transparent 55%),
       radial-gradient(1000px 700px at -10% 110%, #1b1440 0%, transparent 50%),
       linear-gradient(160deg, var(--bg0), var(--bg1));
       color:var(--text); font:15px/1.85 -apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
       min-height:100vh; padding:40px 18px 60px; position:relative; overflow-x:hidden}
  body::before{content:""; position:fixed; inset:0; pointer-events:none; opacity:.75;
    background-image:
      radial-gradient(1.6px 1.6px at 12% 22%, #fff 60%, transparent 61%), radial-gradient(1.2px 1.2px at 30% 70%, #ffe9b0 60%, transparent 61%),
      radial-gradient(1.8px 1.8px at 48% 12%, #fff 60%, transparent 61%), radial-gradient(1.1px 1.1px at 62% 45%, #cfd6ff 60%, transparent 61%),
      radial-gradient(1.5px 1.5px at 78% 18%, #fff 60%, transparent 61%), radial-gradient(1.2px 1.2px at 88% 62%, #ffe9b0 60%, transparent 61%),
      radial-gradient(1.4px 1.4px at 20% 88%, #fff 60%, transparent 61%), radial-gradient(1.1px 1.1px at 70% 86%, #cfd6ff 60%, transparent 61%),
      radial-gradient(1.3px 1.3px at 40% 40%, #fff 60%, transparent 61%), radial-gradient(1px 1px at 55% 60%, #fff 60%, transparent 61%);
    animation:tw 5.5s ease-in-out infinite alternate}
  @keyframes tw{from{opacity:.4}to{opacity:.95}}
  .wrap{max-width:980px;margin:0 auto;position:relative}
  .serif{font-family:"Songti SC","Noto Serif SC","STSong",serif}
  header{text-align:center;margin-bottom:26px;animation:fade .8s ease both}
  .eyebrow{letter-spacing:.55em;text-indent:.55em;color:var(--gold-dim);font-size:12px;margin-bottom:10px}
  h1.name{font-size:clamp(34px,6vw,52px);color:var(--gold);letter-spacing:.12em;font-weight:600}
  .intro{color:var(--dim);margin-top:8px;font-size:15px}
  .hl{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:14px}
  .hl span{border:1px solid var(--line);border-radius:999px;padding:3px 14px;font-size:13px;color:var(--gold);background:rgba(230,196,115,.07)}
  .card{background:var(--card);border:1px solid rgba(255,255,255,.09);border-radius:16px;padding:22px 26px;margin-bottom:18px;
    backdrop-filter:blur(6px);animation:fade .8s ease both}
  @keyframes fade{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
  .chips{display:flex;flex-wrap:wrap;gap:10px;justify-content:center}
  .chip{border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:6px 14px;font-size:13px;background:rgba(255,255,255,.03)}
  .chip .k{color:var(--faint);margin-right:8px;font-size:12px}
  .gold{color:var(--gold)}
  h2{font-size:19px;color:var(--gold);margin-bottom:12px;font-weight:600;letter-spacing:.06em}
  h2 .icon{margin-right:10px;opacity:.9}
  /* 命盘 */
  .board-scroll{overflow-x:auto;margin-bottom:6px}
  .board{display:grid;grid-template-columns:repeat(4,1fr);grid-template-rows:repeat(4,1fr);gap:8px;min-width:700px;min-height:700px}
  .cell{border:1px solid rgba(255,255,255,.12);border-radius:10px;padding:8px 10px;display:flex;flex-direction:column;
    background:linear-gradient(180deg,rgba(255,255,255,.05),rgba(255,255,255,.02));min-height:0}
  .cell.ming{border:1.5px solid var(--gold);box-shadow:0 0 22px rgba(230,196,115,.28) inset,0 0 14px rgba(230,196,115,.18)}
  .p-head{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--dim);border-bottom:1px dashed rgba(255,255,255,.14);padding-bottom:4px;margin-bottom:6px}
  .p-name{color:var(--gold);font-weight:600;font-size:13px}
  .tag.body{background:rgba(180,140,255,.18);color:#cbb2ff;border-radius:4px;padding:0 5px;font-size:11px}
  .p-limit{margin-left:auto;color:var(--faint);font-size:11px}
  .p-stars{flex:1;overflow:hidden}
  .star{font-size:16px;line-height:1.7}
  .star .sname{color:#fff}
  .star.sm{font-size:12.5px;margin-right:2px;color:var(--dim)}
  .star.sm .sname{color:#c9c4e4}
  .star.empty{font-size:14px;color:var(--dim)}
  .borrow{font-size:11px;color:var(--faint);display:block;line-height:1.5}
  sup{font-size:10px;margin-left:2px}
  .bm,.bw{color:#ffd97a}.bd,.bl{color:#e6c473}.bp{color:#cbbfe0}.bn,.bx{color:#ff9a9a}
  .minor{margin-top:4px;line-height:1.8}
  .mh{font-style:normal;font-size:10.5px;border-radius:4px;padding:0 4px;margin-left:4px;vertical-align:2px}
  .mh.lu{color:var(--lu);border:1px solid}.mh.quan{color:var(--quan);border:1px solid}
  .mh.ke{color:var(--ke);border:1px solid}.mh.ji{color:var(--ji);border:1px solid}
  .p-foot{display:flex;justify-content:space-between;font-size:11px;color:var(--faint);border-top:1px dashed rgba(255,255,255,.14);padding-top:4px;margin-top:6px}
  .p-branch{color:var(--dim)}
  .center{grid-row:2/4;grid-column:2/4;border:1px solid var(--line);border-radius:12px;padding:18px;text-align:center;
    background:radial-gradient(400px 260px at 50% 30%, rgba(230,196,115,.1), transparent 70%), var(--card);
    display:flex;flex-direction:column;justify-content:center;gap:8px}
  .center .cname{font-size:26px;color:var(--gold)}
  .center .csub{color:var(--dim);font-size:13px}
  .center .sh-row{display:flex;flex-wrap:wrap;gap:6px;justify-content:center;margin-top:6px}
  .sh{font-size:12px;border-radius:6px;padding:2px 8px;border:1px solid rgba(255,255,255,.14);color:var(--dim)}
  .sh b{margin-right:5px}
  .sh.lu b{color:var(--lu)}.sh.quan b{color:var(--quan)}.sh.ke b{color:var(--ke)}.sh.ji b{color:var(--ji)}
  .legend{text-align:center;color:var(--faint);font-size:12px;margin:10px 0 18px}
  /* 表格与文本 */
  table{width:100%;border-collapse:collapse;font-size:13.5px}
  th{color:var(--gold-dim);font-weight:500;text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);font-size:12.5px;letter-spacing:.08em}
  td{padding:7px 10px;border-bottom:1px solid rgba(255,255,255,.07);color:var(--text)}
  tr.ming-row td{color:var(--gold)}
  .sec p{margin-bottom:10px;text-align:justify}
  .sec p:last-child{margin-bottom:0}
  .lead{color:var(--gold) !important;font-weight:500}
  .advice{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
  .advice div{border:1px solid var(--line);border-radius:12px;padding:14px 16px;font-size:14px;background:rgba(230,196,115,.05)}
  .advice b{color:var(--gold);display:block;margin-bottom:4px;font-size:12.5px;letter-spacing:.15em}
  .sum{border-left:3px solid var(--gold);padding:14px 20px;font-size:15.5px;background:rgba(230,196,115,.06);border-radius:0 12px 12px 0}
  .notice{border-color:rgba(255,180,120,.3)}
  .notice h2{color:#ffb570}
  .notice li{color:var(--dim);font-size:13.5px;margin-left:18px;margin-bottom:4px}
  footer{margin-top:34px;text-align:center;color:var(--faint);font-size:12px;line-height:2}
  footer .disc{max-width:760px;margin:10px auto 0;color:var(--faint);border-top:1px solid rgba(255,255,255,.08);padding-top:14px}
  @media (max-width:760px){.card{padding:18px 16px}}
  @media print{
    body{background:#fff;color:#222;padding:10px}body::before{display:none}
    .card,.cell,.center{background:#fff;border-color:#ccc;box-shadow:none;backdrop-filter:none}
    h1.name,h2,.p-name,.gold{color:#8a6d1f}.star .sname{color:#111}.chip,.hl span{background:#f7f4ec;border-color:#d8cdb0;color:#555}
    .intro,.p-head,.p-foot,.minor,.center .csub,.star.sm .sname,.star.empty,.td,td,th{color:#444}
    sup{color:#7a6320}.mh{border-color:#999}footer .disc{color:#777}
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="eyebrow serif">紫微斗数 · 命盘报告</div>
    <h1 class="name serif">${esc(name)}</h1>
    ${interp.intro ? `<p class="intro">${fmt(interp.intro)}</p>` : ''}
    ${highlightsHtml}
  </header>

  <div class="card"><div class="chips">${chips.join('')}</div></div>

  <section class="card">
    <h2><span class="icon">✦</span>命盘十二宫</h2>
    <div class="board-scroll"><div class="board">
      ${c.palaces.map(cellHtml).join('')}
      <div class="center">
        <div class="cname serif">${esc(name)}</div>
        <div class="csub">${esc(c.wuXingJu)} · 命主${esc(c.soulStar)} · 身主${esc(c.bodyStar)}</div>
        <div class="csub">${esc(c.lunarDate)} · ${esc(c.chineseDate.join(' '))}</div>
        <div class="sh-row">${siHuaHtml}</div>
        <div class="csub" style="font-size:11px">生年四化：禄财于源 · 权势于力 · 科名于助 · 忌执于修</div>
      </div>
    </div></div>
    <div class="legend">金框为命宫 ·「身宫」为后天发力点 · 角标为星曜亮度（庙旺得利平不陷）· 禄/权/科/忌为生年四化 · 右上角为该宫大限虚岁</div>
  </section>

  ${notesHtml}

  <section class="card">
    <h2><span class="icon">☰</span>大限十年运程</h2>
    <table><thead><tr><th>虚岁</th><th>大限宫</th><th>宫名</th><th>主星</th></tr></thead><tbody>${dachengRows}</tbody></table>
  </section>

  ${sectionsHtml}

  ${(interp.advice || []).length ? `<section class="card"><h2><span class="icon">❖</span>综合建议</h2><div class="advice">${(interp.advice || []).map((a, i) => `<div><b>建议 ${['一', '二', '三', '四', '五'][i] || i + 1}</b>${fmt(a)}</div>`).join('')}</div></section>` : ''}

  ${interp.summary ? `<section class="card"><div class="sum">${fmt(interp.summary)}</div></section>` : ''}

  <footer>
    排盘引擎 <a style="color:var(--gold-dim)" href="https://github.com/SylarLong/iztro">iztro</a>（MIT）· 口径对齐
    <a style="color:var(--gold-dim)" href="https://github.com/Renhuai123/ziwei-doushu">Renhuai123/ziwei-doushu</a>（倪海厦《天纪》体系，MIT）· 解读文字由 AI 生成
    <br>生成时间 ${new Date().toLocaleString('zh-CN')}
    <div class="disc">${esc(DISCLAIMER)}</div>
  </footer>
</div>
</body>
</html>`;

const target = outPath || `紫微命盘报告-${name}.html`;
fs.writeFileSync(target, html);
console.log(`[ziwei] 报告已生成: ${target}`);
