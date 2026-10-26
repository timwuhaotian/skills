#!/usr/bin/env node
/**
 * 回归测试: 11 组金标准命盘（取自 Renhuai123/ziwei-doushu famous.ts,
 * 期望值经原仓库引擎与 iztro 双重复核一致）。
 * 用法: node scripts/test.mjs
 */
import { createRequire } from 'node:module';
const { astro } = createRequire(import.meta.url)('iztro');
astro.config({ yearDivide: 'normal' });

const CASES = [
  // [人物, 公历, 时辰序号, 性别, 命宫地支, 命宫主星(空为''), 五行局, 命主, 身主, 身宫宫名, 阴阳]
  ['马云', '1964-9-10', 5, '男', '辰', '贪狼', '木三局', '廉贞', '文昌', '夫妻', '阳男'],
  ['李嘉诚', '1928-7-29', 3, '男', '辰', '七杀', '土五局', '廉贞', '文昌', '迁移', '阳男'],
  ['任正非', '1944-10-25', 3, '男', '未', '天梁', '土五局', '武曲', '天梁', '迁移', '阳男'],
  ['张爱玲', '1920-9-30', 1, '女', '申', '贪狼', '水二局', '廉贞', '天梁', '福德', '阳女'], // 1920 庚申年, 阳年
  ['周杰伦', '1979-1-18', 1, '男', '子', '贪狼', '金四局', '贪狼', '火星', '福德', '阳男'],
  ['王菲', '1969-8-8', 4, '女', '卯', '', '火六局', '文曲', '天同', '财帛', '阴女'],
  ['林志玲', '1974-11-29', 5, '女', '午', '太阳', '土五局', '破军', '天梁', '夫妻', '阳女'],
  ['乔布斯', '1955-2-24', 6, '男', '酉', '天同', '水二局', '文曲', '天相', '命宫', '阴男'],
  ['马斯克', '1971-6-28', 4, '男', '寅', '天机太阴', '木三局', '禄存', '天机', '财帛', '阴男'],
  ['姚明', '1980-9-12', 5, '男', '辰', '贪狼', '金四局', '廉贞', '天梁', '夫妻', '阳男'],
  ['李娜', '1982-2-26', 2, '女', '丑', '天机', '木三局', '巨门', '文昌', '官禄', '阳女'],
];

const STEMS = '甲乙丙丁戊己庚辛壬癸';
let fail = 0;
for (const [who, date, ti, g, expBranch, expStars, expJu, expSoul, expBody, expBodyPalace, expYy] of CASES) {
  const a = JSON.parse(JSON.stringify(astro.bySolar(date, ti, g, true, 'zh-CN')));
  const ming = a.palaces.find((p) => p.name === '命宫');
  const stars = ming.majorStars.map((s) => s.name).join('');
  const bodyPalace = a.palaces.find((p) => p.isBodyPalace)?.name;
  const yy = (STEMS.indexOf(a.chineseDate[0][0]) % 2 === 0 ? '阳' : '阴') + g;
  const errs = [];
  if (ming.earthlyBranch !== expBranch) errs.push(`命宫地支 ${ming.earthlyBranch}≠${expBranch}`);
  if (stars !== expStars) errs.push(`命宫主星「${stars || '空宫'}」≠「${expStars || '空宫'}」`);
  if (a.fiveElementsClass !== expJu) errs.push(`五行局 ${a.fiveElementsClass}≠${expJu}`);
  if (a.soul !== expSoul) errs.push(`命主 ${a.soul}≠${expSoul}`);
  if (a.body !== expBody) errs.push(`身主 ${a.body}≠${expBody}`);
  if (bodyPalace !== expBodyPalace) errs.push(`身宫 ${bodyPalace}≠${expBodyPalace}`);
  if (yy !== expYy) errs.push(`阴阳 ${yy}≠${expYy}`);
  // 结构铁律: 12 宫地支全覆盖且唯一
  if (new Set(a.palaces.map((p) => p.earthlyBranch)).size !== 12) errs.push('地支未全覆盖');
  if (errs.length) { fail++; console.error(`✗ ${who}: ${errs.join('; ')}`); }
  else console.log(`✓ ${who} ${date} ${ti}时 ${g} — 命宫${expBranch}「${expStars || '空宫'}」${expJu}`);
}
// 王妃空宫借星: 命宫卯空, 对宫酉应有天机巨门
{
  const a = JSON.parse(JSON.stringify(astro.bySolar('1969-8-8', 4, '女', true, 'zh-CN')));
  const i = a.palaces.findIndex((p) => p.name === '命宫');
  const opp = a.palaces[(i + 6) % 12];
  const ok = a.palaces[i].majorStars.length === 0 && /天机/.test(opp.majorStars.map((s) => s.name).join()) && /巨门/.test(opp.majorStars.map((s) => s.name).join());
  ok ? console.log('✓ 王妃 命宫空宫借对宫天机巨门') : (fail++, console.error('✗ 王妃 借星校验失败'));
}
// 晚子时等价性: bySolar(D,12) ≡ bySolar(D+1,0) —— 只比盘面字段(排盘日不同是应该的)
{
  const pick = (o) => JSON.stringify([o.palaces, o.soul, o.body, o.fiveElementsClass, o.earthlyBranchOfSoulPalace, o.earthlyBranchOfBodyPalace]);
  const s1 = pick(astro.bySolar('2000-1-31', 12, '男', true, 'zh-CN'));
  const s2 = pick(astro.bySolar('2000-2-1', 0, '男', true, 'zh-CN'));
  s1 === s2 ? console.log('✓ 晚子时 bySolar(D,12) ≡ bySolar(D+1,0)') : (fail++, console.error('✗ 晚子时等价性失败'));
}
console.log(fail ? `\n${fail} 项失败` : '\n全部通过 (13 项)');
process.exit(fail ? 1 : 0);
