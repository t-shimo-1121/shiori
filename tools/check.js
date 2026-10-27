const { chromium } = require('playwright');
/* しおりの検査：390px・明暗で各タブを開き、2行に折り返した行・はみ出しを列挙する
   node tools/check.js 251122kumotori [251122kumotori ...]   （引数なしなら yaml から作る全冊）
   スクショは check/<id>_<明暗>_<タブ>.png に保存（git には入れない） */
const fs = require('fs'), path = require('path');
const ROOT = path.resolve(__dirname, '..');
let ids = process.argv.slice(2);
if (!ids.length) ids = fs.readdirSync(path.join(ROOT, 'trips')).filter(d => !fs.existsSync(path.join(ROOT, 'trips', d, 'index.html')));
const shots = process.env.SHOTS !== '0';
(async () => {
  const b = await chromium.launch();
  let bad_total = 0;
  fs.mkdirSync(path.join(ROOT, 'check'), { recursive: true });
  for (const id of ids) {
  for (const scheme of ['light','dark']) {
    const p = await b.newPage({ viewport:{width:390,height:844}, deviceScaleFactor:2, colorScheme:scheme });
    await p.route(/fonts\.(googleapis|gstatic)/, r=>r.abort());
    await p.goto('file://'+require('path').resolve(__dirname,'..','dist',id,'index.html'));
    for (const tab of await p.evaluate(()=>[...document.querySelectorAll('.tab-btn')].map(b=>b.dataset.tab))) {
      await p.click(`.tab-btn[data-tab="${tab}"]`); await p.waitForTimeout(350);
      const bad = await p.evaluate((tab)=>{
        const out=[]; const panel=document.getElementById(tab);
        panel.querySelectorAll('.t-sum,.t-det,.card-title,.ftable td,.ftable td small,.note li,.stats .n').forEach(e=>{
          const lh=parseFloat(getComputedStyle(e).lineHeight)||0;
          if (e.matches('.t-sum,.t-det,.ftable td small') && e.getBoundingClientRect().height>lh*1.5) out.push('WRAP '+e.textContent);
          if (e.scrollWidth>e.clientWidth+1) out.push('OVER '+e.textContent);
        });
        if (document.documentElement.scrollWidth>390) out.push('PAGE WIDTH '+document.documentElement.scrollWidth);
        return out;
      }, tab);
      if (bad.length) { bad_total += bad.length; console.log(id, scheme, tab, bad); }
      if (shots) await p.screenshot({path: path.join(ROOT, 'check', `${id}_${scheme}_${tab}.png`), fullPage:true});
    }
    await p.close();
  }
  }
  await b.close();
  console.log(bad_total ? `要確認 ${bad_total} か所` : `OK（${ids.length} 冊）`);
  process.exit(bad_total ? 1 : 0);
})();
