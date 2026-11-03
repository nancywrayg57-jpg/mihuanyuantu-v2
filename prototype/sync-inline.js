const fs = require('fs');
const path = require('path');
const root = path.join(__dirname, '..');
const jsPath = path.join(__dirname, 'prototype.js');
const htmlPath = path.join(__dirname, 'index.html');
const js = fs.readFileSync(jsPath, 'utf8');
const html = fs.readFileSync(htmlPath, 'utf8');
const pattern = /(<script>\r?\n)([\s\S]*?)(\r?\n\s*<\/script>\s*<\/body>)/;
if (!pattern.test(html)) {
  console.error('inline script block not found');
  process.exit(1);
}
const trimmed = js.replace(/\s+$/, '');
const newHtml = html.replace(pattern, (_, open, _body, close) => open + trimmed + close);
fs.writeFileSync(htmlPath, newHtml, 'utf8');
const html2 = fs.readFileSync(htmlPath, 'utf8');
const m = html2.match(pattern);
console.log('synced');
console.log('html===js', !!(m && m[2] === trimmed));
console.log('bytes', Buffer.byteLength(js, 'utf8'), Buffer.byteLength(html2, 'utf8'));
