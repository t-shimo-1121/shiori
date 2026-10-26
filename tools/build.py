"""全部を作る：trips/*/trip.yaml ＋ data/*.yaml → dist/（GitHub Pages にそのまま置く形）
  dist/index.html            本棚
  dist/<id>/index.html       しおり（yaml から作る。raw: true の冊は trips/<id>/index.html をそのまま）
  dist/sw.js・manifest・icon 本棚と全冊をオフラインで開けるようにする
python3 tools/build.py            … 全部
python3 tools/build.py 251122okutama … その冊と本棚だけ（確認用）"""
import base64, hashlib, io, json, os, re, shutil, subprocess, sys
from datetime import date
import yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shiori

ROOT = shiori.ROOT
DIST = os.path.join(ROOT, 'dist')
T = os.path.join(ROOT, 'templates')

def load(p):
    return yaml.safe_load(open(p, encoding='utf-8'))
def iso(v): return v.isoformat() if isinstance(v, date) else str(v)

def git_hist(tid):
    """そのしおりのフォルダの commit 数と最終日（移行前の版数は history に入っている）"""
    try:
        out = subprocess.run(['git', 'log', '--format=%cs', '--', 'trips/' + tid], cwd=ROOT, capture_output=True, text=True).stdout.split()
    except Exception:
        out = []
    return out

def trips():
    out = []
    for tid in sorted(os.listdir(os.path.join(ROOT, 'trips'))):
        p = os.path.join(ROOT, 'trips', tid, 'trip.yaml')
        if not os.path.exists(p): continue
        C = load(p); C['id'] = tid
        for k in ('start', 'end'): C[k] = iso(C[k])
        for d in C.get('days', []): d['date'] = iso(d['date'])
        out.append(C)
    return out

def shelf_cover(tdir):
    p = shiori.cover_path(tdir)
    if not p: return ''
    from PIL import Image
    img = Image.open(p).convert('RGB')
    w = 520; img = img.resize((w, round(img.height * w / img.width)), Image.LANCZOS)
    b = io.BytesIO(); img.save(b, 'WEBP', quality=72)
    return 'data:image/webp;base64,' + base64.b64encode(b.getvalue()).decode()

def tabs_of(C):
    if C.get('tabs'): return C['tabs']
    return ['準備 費用'] + ['%s %s' % (d.get('tab_label') or shiori.md_label(shiori.D(d['date'])), d['tab']) for d in C['days']]

def hues_of(C):
    h = dict(C['hues'])
    for i, d in enumerate(C.get('days', [])): h['d%d' % (i + 1)] = d['hue']
    return h

def build_trip(C):
    tdir = os.path.join(ROOT, 'trips', C['id'])
    os.makedirs(os.path.join(DIST, C['id']), exist_ok=True)
    out = os.path.join(DIST, C['id'], 'index.html')
    if C.get('raw'):
        shutil.copy(os.path.join(tdir, 'index.html'), out)
    else:
        open(out, 'w', encoding='utf-8').write(shiori.render(C, tdir))

def ledger(all_trips):
    """本棚の表（宿泊・山・施設・旅先）を各しおりと data/ から集める。形は本棚のページが読む形"""
    L = {'STAYS': [], 'STAY_SHORT': {}, 'PEAKS': [], 'SPOTS': []}
    rec = load(os.path.join(ROOT, 'data', 'records.yaml')) or {}
    def peak(p, t):
        x = {'d': iso(p['date']), 'nm': p['name'], 'e': p['elev']}
        if t: x['t'] = t
        if p.get('subs'): x['sub'] = '・'.join(p['subs'])
        for a, b in (('ct', 'coursetime'), ('k', 'const'), ('lv', 'level'), ('n', 'hyaku')):
            if p.get(b) is not None: x[a] = p[b]
        return x
    def spot(s, t, past):
        x = {'c': s['cat'], 'nm': s['name'], 'at': s['at'], 'd': s.get('facts', [])}
        if s.get('visited'): x['v'] = str(s['visited'])
        if t: x['tr' if (s.get('visited') or past) else 't'] = t
        return x
    for C in all_trips:
        t = C['id']; past = C['end'] < date.today().isoformat()
        for s in C.get('stays', []):
            x = {'d': iso(s['date']), 't': t, 'nm': s['name'], 'a': s.get('area', ''), 'n': s['nights'], 'kind': s.get('kind', '')}
            if s.get('price') is not None: x['p'] = s['price']
            if s.get('approx'): x['approx'] = True
            if s.get('note'): x['nt'] = s['note']
            L['STAYS'].append(x)
            if s.get('short') or s.get('group'): L['STAY_SHORT'][s['name']] = [s.get('short'), s.get('group')]
        L['PEAKS'] += [peak(p, t) for p in C.get('peaks', [])]
        L['SPOTS'] += [spot(s, t, past) for s in C.get('spots', [])]
    L['PEAKS'] += [peak(p, None) for p in rec.get('peaks', [])]
    L['SPOTS'] += [spot(s, None, True) for s in rec.get('spots', [])]
    L['STAYS'].sort(key=lambda x: x['d']); L['PEAKS'].sort(key=lambda x: x['d'])
    P = load(os.path.join(ROOT, 'data', 'places.yaml'))
    def vis(x, o):
        if x.get('visited') is not None: o['v'] = x['visited'] if x['visited'] in (1, '地元') else str(x['visited'])
        if x.get('trip'): o['t'] = x['trip']
        return o
    L['PREFS'] = [vis(p, {'no': p['no'], 'nm': p['name'], 'cap': p['capital'], 'pop': p['pop'], 'area': p['area'], 'ft': p['note']}) for p in P['prefs']]
    L['CITIES'] = [vis(c, {'p': c['pref'], 'nm': c['name'], 'pop': c['pop'], 'area': c['area'], 'r': c['did'], 'ft': c['note']}) for c in P['cities']]
    L['YOMI'] = {c['name']: c['yomi'] for c in P['cities'] if c.get('yomi')}
    L['ABROAD'] = [vis(a, {'nm': a['name'], 'sub': a.get('sub', ''), 'ft': a['note']}) for a in P['abroad']]
    # 旅先ランキング：市区町村ごとの観光・宿泊スポットの数（「・」で分けて数え、同じ名前は1つ）
    KEEP = ['ユニバーサル・スタジオ・ジャパン', 'レゴランド・ディスカバリー・センター大阪', '大阪・関西万博', 'レゴランド・ジャパン・ホテル',
            'レゴランド・シーライフ名古屋', 'リニア・鉄道館', 'BOSS E・ZO FUKUOKA', 'スーパーホテル沖縄・名護', 'ザ・グローバルウエスト']
    def items(v):
        for i, k in enumerate(KEEP): v = v.replace(k, '\x00%d\x00' % i)
        return [re.sub(r'\x00(\d+)\x00', lambda m: KEEP[int(m.group(1))], x).strip() for x in v.split('・') if x.strip()]
    L['CITY_SPOTS'] = {}
    for c in P['cities']:
        seen = {}
        for k, v in c['did']:
            if k in ('観光', '宿泊'):
                for x in items(v): seen.setdefault(x, k)
        L['CITY_SPOTS'][c['name']] = [list(seen.values()).count('観光'), list(seen.values()).count('宿泊')]
    L['GUIDE'] = load(os.path.join(ROOT, 'data', 'guide.yaml'))
    Dz = load(os.path.join(ROOT, 'data', 'design.yaml'))
    L['SPOT_CATS'] = [[c['id'], c['name']] for c in Dz['cats']]
    L['DESIGN'] = [[g['name'], g['items']] for g in Dz['design']]
    # 参照先のしおりがあるか確かめる
    ids = {C['id'] for C in all_trips}
    for k in ('STAYS', 'PEAKS', 'SPOTS', 'PREFS', 'CITIES', 'ABROAD'):
        for x in L[k]:
            for f in ('t', 'tr'):
                assert x.get(f) is None or x[f] in ids, ('しおりが見つからない', k, x.get('nm'), x[f])
    return L

def build_shelf(all_trips):
    shown = [C for C in all_trips if C.get('shelf', True)]
    data = []
    for C in shown:
        h = C.get('history', {'versions': 0, 'first': None, 'last': None})
        g = git_hist(C['id'])
        versions = (h.get('versions') or 0) + max(0, len(g) - 1) if h.get('versions') else max(1, len(g))
        last = g[0] if len(g) > 1 else (iso(h['last']) if h.get('last') else (g[0] if g else date.today().isoformat()))
        cov = shelf_cover(os.path.join(ROOT, 'trips', C['id']))
        data.append({'id': C['id'], 'repo': C['id'], 'title': C['title'], 'start': C['start'], 'end': C['end'],
                     'hues': hues_of(C), 'tabs': tabs_of(C), 'versions': versions, 'last': last, 'cover': cov, 'ph': not cov})
    js = lambda o: json.dumps(o, ensure_ascii=False).replace('</', '<\\/')
    t = open(os.path.join(T, 'shelf.html'), encoding='utf-8').read()
    t = t.replace('__DATA__', js(data)).replace('__LEDGER__', js(ledger(all_trips)))
    head = ('<!DOCTYPE html>\n<html lang="ja">\n<head>\n<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">\n'
            '<meta name="mobile-web-app-capable" content="yes">\n<meta name="apple-mobile-web-app-capable" content="yes">\n'
            '<meta name="apple-mobile-web-app-status-bar-style" content="default">\n<meta name="apple-mobile-web-app-title" content="しおり集">\n'
            '<meta name="theme-color" media="(prefers-color-scheme: light)" content="#F3F5F8">\n'
            '<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#161B22">\n'
            '<link rel="manifest" href="manifest.webmanifest">\n<link rel="apple-touch-icon" href="icon-180.png">\n<link rel="icon" href="icon-192.png">\n'
            '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n')
    i = t.find('<div class="wrap">')
    sw = '<script>if("serviceWorker" in navigator)window.addEventListener("load",function(){navigator.serviceWorker.register("sw.js").catch(function(){});});</script>\n'
    page = head + t[:i] + sw + '</head>\n<body>\n' + t[i:] + '\n</body>\n</html>\n'
    open(os.path.join(DIST, 'index.html'), 'w', encoding='utf-8').write(page)
    for f in ('icon-180.png', 'icon-192.png', 'icon-512.png'):
        shutil.copy(os.path.join(T, f), DIST)
    json.dump({"name": "旅行のしおり集", "short_name": "しおり集", "lang": "ja", "start_url": "./", "scope": "./", "display": "standalone",
               "background_color": "#F3F5F8", "theme_color": "#F3F5F8",
               "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
                         {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}]},
              open(os.path.join(DIST, 'manifest.webmanifest'), 'w'), ensure_ascii=False, indent=1)
    # サービスワーカー：本棚と全冊をまとめて保存（版は中身のハッシュ）
    pages = ['./'] + ['./%s/' % C['id'] for C in all_trips]
    hsh = hashlib.md5()
    for root, _, files in sorted(os.walk(DIST)):
        for f in sorted(files):
            if f != 'sw.js': hsh.update(open(os.path.join(root, f), 'rb').read())
    sw = open(os.path.join(T, 'sw.js'), encoding='utf-8').read().replace('__VER__', hsh.hexdigest()[:8]).replace('__PAGES__', json.dumps(pages))
    open(os.path.join(DIST, 'sw.js'), 'w', encoding='utf-8').write(sw)
    return len(shown)

def main(only=None):
    all_trips = trips()
    if os.path.exists(DIST) and not only: shutil.rmtree(DIST)
    os.makedirs(DIST, exist_ok=True)
    for C in all_trips:
        if not only or C['id'] in only: build_trip(C)
    n = build_shelf(all_trips)
    open(os.path.join(DIST, '.nojekyll'), 'w').close()
    print('ok: しおり %d 冊（本棚 %d 冊）→ dist/' % (len(all_trips) if not only else len(only), n))

if __name__ == '__main__':
    main(sys.argv[1:] or None)
