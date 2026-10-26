#!/usr/bin/env node
/**
 * 紫微斗数排盘脚本（ziwei-doushu skill）
 * 公历生日 + 出生时间 + 性别 (+可选出生地) → 命盘 chart.json
 *
 * 引擎: iztro (https://github.com/SylarLong/iztro, MIT)
 * 口径对齐 Renhuai123/ziwei-doushu (倪海厦《天纪》体系):
 *   - yearDivide: 'normal'（正月初一换年）
 *   - 晚子时(23:00-23:59)按次日排盘, 早子时按当日
 *   - 真太阳时 = 东八区钟表时 + 经度修正 + 均时差（NOAA 式, 移植自 true-solar-time.ts）
 *   - 中国 1986-1991 夏令时: 只提示, 不自动扣减（无法得知用户填的是否夏令时读数）
 *
 * 用法:
 *   node scripts/paipan.mjs --name 张三 --date 1990-06-15 --time 14:30 --gender 男 \
 *                           [--city 重庆 | --longitude 106.6] [--no-solar] [--out chart.json]
 */
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const SKILL_DIR = path.dirname(path.dirname(fileURLToPath(import.meta.url)));

/* ---------- 依赖自举: 缺 iztro 就地安装 ---------- */
function loadIztro() {
  const req = createRequire(import.meta.url);
  try {
    return req('iztro');
  } catch {
    console.error('[ziwei] 首次运行, 正在安装排盘引擎 iztro ...');
    const r = spawnSync('npm', ['install', '--prefix', SKILL_DIR, '--no-audit', '--no-fund'], {
      stdio: 'inherit',
    });
    if (r.status !== 0) throw new Error('iztro 安装失败, 请检查网络后重试, 或手动执行: npm install --prefix ' + SKILL_DIR);
    return req('iztro');
  }
}
const { astro } = loadIztro();

/* ---------- 参数解析 ---------- */
function parseArgs(argv) {
  const a = {};
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === '--no-solar') { a.noSolar = true; continue; }
    const v = argv[i + 1];
    if (k.startsWith('--') && v !== undefined && !v.startsWith('--')) { a[k.slice(2)] = v; i++; }
    else { console.error('未知或缺少取值的参数: ' + k); process.exit(2); }
  }
  return a;
}
const args = parseArgs(process.argv.slice(2));
const die = (msg) => { console.error('[错误] ' + msg); process.exit(1); };

const name = args.name || die('缺少 --name 姓名');
const dateStr = args.date || die('缺少 --date 公历生日 (YYYY-MM-DD)');
const timeStr = args.time || die('缺少 --time 出生时间 (HH:MM, 24 小时制)');
const genderRaw = (args.gender || die('缺少 --gender 性别 (男/女)')).toLowerCase();

/* 校验: 真实公历日期 */
const dm = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(dateStr) || die('--date 格式应为 YYYY-MM-DD, 收到: ' + dateStr);
const [y, mo, d] = [ +dm[1], +dm[2], +dm[3] ];
const utc = new Date(Date.UTC(y, mo - 1, d));
if (utc.getUTCFullYear() !== y || utc.getUTCMonth() !== mo - 1 || utc.getUTCDate() !== d) die('公历日期不存在: ' + dateStr);
/* 校验: 时间 */
const tm = /^(\d{1,2}):(\d{1,2})$/.exec(timeStr) || die('--time 格式应为 HH:MM, 收到: ' + timeStr);
const hh = +tm[1], mi = +tm[2];
if (hh > 23 || mi > 59) die('时间超出范围: ' + timeStr);
/* 校验: 性别 */
const gender = ['男', 'male', 'm', '1'].includes(genderRaw) ? '男'
             : ['女', 'female', 'f', '0'].includes(genderRaw) ? '女'
             : die('--gender 应为 男 或 女');
if (y < 1900 || y > 2100) die('出生年份建议在 1900-2100 之间');

/* ---------- 主要城市经度（子集移植自 Renhuai123/ziwei-doushu cities.ts, MIT） ---------- */
const CITY_LON = {
  北京: 116.4, 天津: 117.2, 上海: 121.5, 重庆: 106.6,
  石家庄: 114.5, 太原: 112.6, 呼和浩特: 111.7, 沈阳: 123.4, 长春: 125.4, 哈尔滨: 126.5,
  南京: 118.8, 杭州: 120.1, 合肥: 117.3, 福州: 119.3, 南昌: 115.9, 济南: 117.0,
  郑州: 113.6, 武汉: 114.3, 长沙: 113.0, 广州: 113.3, 南宁: 108.3, 海口: 110.3,
  成都: 104.1, 贵阳: 106.7, 昆明: 102.7, 拉萨: 91.1, 西安: 108.9, 兰州: 103.8,
  西宁: 101.8, 银川: 106.3, 乌鲁木齐: 87.6,
  深圳: 114.1, 珠海: 113.6, 青岛: 120.4, 大连: 121.6, 厦门: 118.1, 宁波: 121.6, 苏州: 120.6,
  香港: 114.2, 澳门: 113.5, 台北: 121.5, 台中: 120.7, 高雄: 120.3,
};

const notes = [];
let longitude = null;
let cityName = null;
if (!args.noSolar) {
  if (args.longitude) {
    longitude = +args.longitude;
    if (!(60 <= longitude && longitude <= 140)) die('--longitude 应为东经度数 (60-140), 收到: ' + args.longitude);
  } else if (args.city) {
    cityName = args.city.replace(/市$/, '');
    if (CITY_LON[cityName] == null) {
      die('未收录城市「' + args.city + '」。可改用 --longitude 东经度数, 或加 --no-solar 跳过真太阳时校正。已收录: ' + Object.keys(CITY_LON).join('、'));
    }
    longitude = CITY_LON[cityName];
  }
}

/* ---------- 真太阳时（移植自 Renhuai123/ziwei-doushu true-solar-time.ts, MIT） ---------- */
const isLeap = (yy) => yy % 4 === 0 && (yy % 100 !== 0 || yy % 400 === 0);
const dayOfYear = (yy, mm, dd) => Math.floor((Date.UTC(yy, mm - 1, dd) - Date.UTC(yy, 0, 0)) / 86400000);
/** NOAA 均时差, 单位分钟; 正值 = 真太阳时快于平太阳时 */
function eotMinutes(yy, mm, dd, clockHour = 12, clockMinute = 0) {
  const daysInYear = isLeap(yy) ? 366 : 365;
  const fh = clockHour + clockMinute / 60;
  const g = ((2 * Math.PI) / daysInYear) * (dayOfYear(yy, mm, dd) - 1 + (fh - 12) / 24);
  return 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g)
    - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
}
const pad = (n) => String(n).padStart(2, '0');
const SHICHEN = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];

let chartY = y, chartM = mo, chartD = d, timeIndex, lateZi = false;
let timeCheck = { applied: false };

if (longitude != null) {
  const lonCorrMin = (longitude - 120) * 4;
  const eot = eotMinutes(y, mo, d, hh, mi);
  const rawMin = hh * 60 + mi + lonCorrMin + eot;
  const totalSec = Math.round(rawMin * 60);
  const dayOffset = Math.floor(totalSec / 86400);
  const secOfDay = ((totalSec % 86400) + 86400) % 86400;
  const normMin = secOfDay / 60;
  // 换日后的排盘基准日期
  const base = new Date(Date.UTC(y, mo - 1, d) + dayOffset * 86400000);
  // 晚子时(23:00-23:59)按次日排盘、时辰取子
  const addDay = normMin >= 1380 ? 1 : 0;
  const chart = new Date(base.getTime() + addDay * 86400000);
  chartY = chart.getUTCFullYear(); chartM = chart.getUTCMonth() + 1; chartD = chart.getUTCDate();
  lateZi = addDay === 1;
  timeIndex = normMin < 60 ? 0 : Math.floor((normMin - 60) / 120) + 1;

  // 时辰边界提醒(±15 分钟)
  const bounds = [60, 180, 300, 420, 540, 660, 780, 900, 1020, 1140, 1260, 1380];
  for (const b of bounds) {
    if (Math.abs(normMin - b) <= 15) {
      notes.push(`真太阳时 ${pad(Math.floor(normMin / 60))}:${pad(Math.round(normMin % 60))} 距时辰交界仅 ${Math.round(Math.abs(normMin - b))} 分钟，排盘对出生时间精度敏感，建议与用户核对几分钟内的误差。`);
      break;
    }
  }
  timeCheck = {
    applied: true,
    city: cityName || null,
    longitude,
    lonCorrMin: +lonCorrMin.toFixed(2),
    eotMin: +eot.toFixed(2),
    clockTime: `${pad(hh)}:${pad(mi)}`,
    trueSolarTime: `${pad(Math.floor(secOfDay / 3600))}:${pad(Math.floor((secOfDay % 3600) / 60))}`,
    shichen: `${SHICHEN[timeIndex === 0 ? 0 : timeIndex]}时`,
    normalizedDate: `${chartY}-${pad(chartM)}-${pad(chartD)}`,
    lateZiHour: lateZi,
  };
} else {
  // 不做校正: 按东经 120° 钟表时间直接定时辰
  const normMin = hh * 60 + mi;
  const addDay = normMin >= 1380 ? 1 : 0;
  if (addDay) { const c = new Date(Date.UTC(y, mo - 1, d) + 86400000); chartY = c.getUTCFullYear(); chartM = c.getUTCMonth() + 1; chartD = c.getUTCDate(); }
  lateZi = addDay === 1;
  timeIndex = normMin < 60 ? 0 : Math.floor((normMin - 60) / 120) + 1;
  timeCheck = { applied: false, clockTime: `${pad(hh)}:${pad(mi)}`, shichen: `${SHICHEN[timeIndex]}时`, normalizedDate: `${chartY}-${pad(chartM)}-${pad(chartD)}`, lateZiHour: lateZi };
  notes.push('未提供出生地，未做真太阳时校正（按东经 120°）。中国东西部时差最多近 2 小时，可能影响时辰判定。');
}
if (lateZi) notes.push('出生真太阳时在 23:00-24:00（晚子时），已按次日排盘、时辰取子时。');

/* ---------- 中国夏令时 1986-1991（起止均含, 只提示不扣减） ---------- */
const DST_CN = { 1986: ['05-04', '09-14'], 1987: ['04-12', '09-13'], 1988: ['04-10', '09-11'], 1989: ['04-16', '09-17'], 1990: ['04-15', '09-16'], 1991: ['04-14', '09-15'] };
timeCheck.dst = 'none';
const rng = DST_CN[y];
if (rng) {
  const cur = `${pad(mo)}-${pad(d)}`;
  if (rng[0] <= cur && cur <= rng[1]) {
    timeCheck.dst = 'in-dst';
    notes.push(`出生日期 ${dateStr} 处于 ${y} 年中国夏令时期间（${rng[0]} 至 ${rng[1]}）。若用户提供的是夏令时钟表读数，真太阳时需再减 1 小时，可能改变时辰——请向用户确认后，必要时用减 1 小时后的时间重排。`);
  }
}

/* ---------- 排盘 ---------- */
astro.config({ yearDivide: 'normal' }); // 正月初一换年, 主流口径
const a = astro.bySolar(`${chartY}-${chartM}-${chartD}`, timeIndex, gender, true, 'zh-CN');
const plain = JSON.parse(JSON.stringify(a)); // 去掉 class 方法, 只留数据

/* 生年四化: 扫描全部星曜的 mutagen 标记 */
const siHua = {};
for (const p of plain.palaces) {
  for (const s of [...p.majorStars, ...p.minorStars]) {
    if (s.scope === 'origin' && s.mutagen) siHua[s.mutagen] = { star: s.name, palace: p.name, branch: p.earthlyBranch };
  }
}

/* 命宫三方四正 + 空宫借星 */
const mingIdx = plain.palaces.findIndex((p) => p.name === '命宫');
const ming = plain.palaces[mingIdx];
const opposite = plain.palaces[(mingIdx + 6) % 12];
const emptyMing = ming.majorStars.length === 0;

/* 阴阳: 年干奇偶 */
const STEMS = '甲乙丙丁戊己庚辛壬癸';
const yearGan = plain.chineseDate[0][0];
const yinYang = (STEMS.indexOf(yearGan) % 2 === 0 ? '阳' : '阴') + gender;

const out = {
  meta: {
    skill: 'ziwei-doushu',
    generatedAt: new Date().toISOString(),
    engine: `iztro v${loadIztroVersion()}`,
    school: '倪海厦《天纪》体系口径（晚子时按次日、正月初一换年）',
    source: '排盘算法基于 iztro (MIT)，口径对齐 github.com/Renhuai123/ziwei-doushu (MIT)',
  },
  input: { name, gender, solarDate: dateStr, clockTime: `${pad(hh)}:${pad(mi)}`, city: cityName, longitude },
  timeCheck,
  notes,
  chart: {
    lunarDate: plain.lunarDate,
    chineseDate: Array.isArray(plain.chineseDate) ? plain.chineseDate : String(plain.chineseDate).split(/\s+/), // [年干支, 月干支, 日干支, 时干支]
    zodiac: plain.zodiac,
    sign: plain.sign,
    time: plain.time,
    timeRange: plain.timeRange,
    wuXingJu: plain.fiveElementsClass,
    soulStar: plain.soul,   // 命主
    bodyStar: plain.body,   // 身主
    yinYang,
    mingGong: { branch: ming.earthlyBranch, stem: ming.heavenlyStem, index: mingIdx, empty: emptyMing },
    shenGong: { branch: plain.earthlyBranchOfBodyPalace, palaceName: plain.palaces.find((p) => p.isBodyPalace)?.name },
    siHua,
    sanFangSiZheng: {
      ming: ming.name,
      dui: opposite.name,                       // 迁移
      sanHe1: plain.palaces[(mingIdx + 4) % 12].name, // 财帛/官禄
      sanHe2: plain.palaces[(mingIdx + 8) % 12].name,
    },
    borrowedStars: emptyMing ? opposite.majorStars.map((s) => s.name + (s.brightness ? `(${s.brightness})` : '')) : null,
    palaces: plain.palaces.map((p) => ({
      index: p.index,
      name: p.name,
      branch: p.earthlyBranch,
      stem: p.heavenlyStem,
      isBodyPalace: p.isBodyPalace,
      majorStars: p.majorStars.map((s) => ({ name: s.name, brightness: s.brightness, mutagen: s.mutagen })),
      minorStars: p.minorStars.map((s) => ({ name: s.name, brightness: s.brightness, mutagen: s.mutagen })),
      adjectiveStars: p.adjectiveStars.map((s) => s.name),
      changsheng12: p.changsheng12,
      boshi12: p.boshi12,
      decadal: { range: p.decadal.range, branch: p.decadal.earthlyBranch },
      ages: p.ages, // 小限虚岁
    })),
  },
};

function loadIztroVersion() {
  try {
    const pkg = createRequire(import.meta.url)('iztro/package.json');
    return pkg.version;
  } catch { return 'unknown'; }
}

const json = JSON.stringify(out, null, 2);
if (args.out) {
  const fs = await import('node:fs');
  fs.writeFileSync(args.out, json);
  console.error(`[ziwei] 命盘已写入 ${args.out}`);
} else {
  console.log(json);
}
