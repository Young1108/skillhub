#!/usr/bin/env node
// 渲染 SPA 页面并抽取纯文本。零依赖，Node >= 22（内置 WebSocket）。
// 用法: node grab_text.mjs <url> <out.txt> [port] [maxRounds]
// 前提: Chrome 已按 grab_spa_text.sh 的方式带 --remote-debugging-port 启动。

const url = process.argv[2];
const outfile = process.argv[3];
const PORT = process.argv[4] || '9333';
const MAX_ROUNDS = parseInt(process.argv[5] || '25', 10);
const CDP_HTTP = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function pageTarget() {
  const list = await (await fetch(`${CDP_HTTP}/json/list`)).json();
  const pages = list.filter(t => t.type === 'page');
  return pages.find(p => /^https?:/.test(p.url)) || pages[0];
}

class CDP {
  constructor(ws) { this.ws = ws; this.id = 0; this.pending = new Map(); }
  static async connect(u) {
    const ws = new WebSocket(u);
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('ws error')); });
    const c = new CDP(ws);
    ws.onmessage = ev => {
      const m = JSON.parse(ev.data);
      if (m.id && c.pending.has(m.id)) {
        const { res, rej } = c.pending.get(m.id);
        c.pending.delete(m.id);
        m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result);
      }
    };
    return c;
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((res, rej) => {
      this.pending.set(id, { res, rej });
      this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => { if (this.pending.has(id)) { this.pending.delete(id); rej(new Error('timeout ' + method)); } }, 60000);
    });
  }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.text || 'eval error');
    return r.result.value;
  }
}

const t = await pageTarget();
if (!t) { console.error('no page target on port', PORT); process.exit(1); }
const cdp = await CDP.connect(t.webSocketDebuggerUrl);
await cdp.send('Page.enable');
await cdp.send('Runtime.enable');
await cdp.send('Page.navigate', { url });
await sleep(6000);

// 轮询 innerText 直到长度稳定。SPA 常见：先空壳 -> 突然渲染 -> 懒加载追加。
let last = '';
let stable = 0;
for (let i = 0; i < MAX_ROUNDS; i++) {
  const txt = await cdp.eval('document.body ? document.body.innerText : ""').catch(() => '');
  const st = await cdp.eval('JSON.stringify({href: location.href, title: document.title, len: document.body ? document.body.innerText.length : 0})').catch(() => '{}');
  console.log(`round ${i} ${st}`);
  if (txt === last && txt.length > 200) {
    if (++stable >= 3) break;
  } else {
    stable = 0;
  }
  last = txt;
  await cdp.eval('window.scrollBy(0, window.innerHeight*1.5); true').catch(() => {});
  await sleep(2000);
}

await cdp.eval('window.scrollTo(0,0); true').catch(() => {});
await sleep(800);
const final = await cdp.eval('document.body ? document.body.innerText : ""').catch(() => '');

const fs = await import('node:fs');
fs.writeFileSync(outfile, final, 'utf8');
console.log('SAVED', outfile, final.length);

// 空白/登录墙判定，交给调用方决定是否重试
if (final.length < 200) {
  console.error('WARN: 抽取文本过短，可能是登录墙或渲染失败');
  process.exit(3);
}
process.exit(0);
