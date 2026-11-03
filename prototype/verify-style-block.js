const fs = require('fs');
const html = fs.readFileSync('D:/workspace/蜜獾原图v2/prototype/index.html', 'utf8');
const styleMatch = html.match(/<style>([\s\S]*?)<\/style>/);
if (!styleMatch) {
  console.error('no style block');
  process.exit(1);
}
const css = styleMatch[1];
let inStr = null;
for (let i = 0; i < css.length; i++) {
  const ch = css[i];
  if (inStr) {
    if (ch === '\\' && i + 1 < css.length) {
      i++;
      continue;
    }
    if (ch === inStr) inStr = null;
  } else if (ch === '"' || ch === "'") {
    inStr = ch;
  }
}
console.log('unclosed_quotes:', inStr ? 'FAIL ' + inStr : 'OK');
const thumbRule = css.match(/\.resource-table-thumb\s*\{[^}]+\}/);
console.log('resource-table-thumb rule:', thumbRule ? thumbRule[0].slice(0, 120) + '...' : 'MISSING');
console.log('resource-method rules:', (css.match(/\.resource-method/g) || []).length);
console.log('toast::before:', css.match(/\.toast::before\s*\{[^}]+\}/)?.[0] || 'MISSING');
