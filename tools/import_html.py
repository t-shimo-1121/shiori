"""移行用：奥多摩型のしおり HTML → trips/<id>/trip.yaml（＋cover）
python3 tools/import_html.py <元のindex.html> <id>
作り直した HTML の本文が元と一致しなければ止まる（その冊は raw として預かる）"""
import base64, html as H, os, re, sys, urllib.parse
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shiori
import yaml

def unline(s):
    """HTML → 文中の記法"""
    s = s.strip()
    def mp(m):
        q = urllib.parse.unquote(H.unescape(m.group(1)))
        lab = m.group(2)
        return '[%s]' % lab if q == lab else '[%s](%s)' % (lab, q)
    s = re.sub(r'<a class="map" href="https://www\.google\.com/maps/search/\?api=1&(?:amp;)?query=([^"]*)" target="_blank" rel="noopener">(.*?)</a>', mp, s)
    s = re.sub(r'<span class="hl">(.*?)</span>', r'**\1**', s)
    s = re.sub(r'<span class="warn">(.*?)</span>', r'!!\1!!', s)
    return s

def norm(s):
    s = re.sub(r'data:image/[a-z]+;base64,[A-Za-z0-9+/=]+', 'IMG', s)
    s = re.sub(r'href="https://www\.google\.com/maps/search/\?api=1&(?:amp;)?query=([^"]*)"',
               lambda m: 'href="MAP:%s"' % urllib.parse.unquote(H.unescape(m.group(1))), s)
    s = re.sub(r'<!--.*?-->', '', s, flags=re.S)
    s = re.sub(r'>\s+<', '><', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def body_of(s):
    i = s.index('<div class="wrap">'); j = s.index('<script>', i)
    return s[i:j]

def parse(src, tid):
    C = {'id': tid}
    s = src
    C['title'] = H.unescape(re.search(r'<div class="cover-cap">\s*<h1>(.*?)</h1>', s, re.S).group(1))
    C['daterange_src'] = re.search(r'<div class="cover-cap">.*?<div class="date">(.*?)</div>', s, re.S).group(1)
    C['apptitle'] = re.search(r'apple-mobile-web-app-title" content="([^"]*)"', s).group(1)
    C['doctitle'] = re.search(r'<title>(.*?)</title>', s).group(1)
    C['ns'] = re.search(r"var NS = '([^']*)';", s).group(1)
    hv = dict(re.findall(r'--h-(base|brand|pack):\s*(\d+)', s))
    C['hues'] = {k: int(hv[k]) for k in ('base', 'brand', 'pack')}
    dh = {int(n): (int(v), c.strip()) for n, v, c in re.findall(r'--h-d(\d+):\s*(\d+);\s*/\*\s*(.*?)\s*\*/', s)}
    # 表紙
    m = re.search(r'<div class="cover-frame">\s*<img src="data:image/(jpeg|png|webp);base64,([A-Za-z0-9+/=]+)"', s)
    C['_cover'] = (m.group(1), base64.b64decode(m.group(2))) if m else None
    # タブ
    tabs = re.findall(r'<button class="tab-btn t(\d+)[^"]*" data-tab="day\d+" role="tab"(?: aria-label="([^"]*)")?>(.*?)<small>(.*?)</small></button>', s)
    pk = re.search(r'<button class="tab-btn t0 active" data-tab="pack" role="tab">準備<small>費用</small></button>', s)
    assert pk, 'pack tab'
    # 費用
    pack = re.search(r'<div class="tab-panel is-active" id="pack">(.*?)</div><!-- /pack -->', s, re.S).group(1)
    assert pack.count('class="card ') == 1, 'pack has extra cards'
    groups = []
    for head, tb, tf in re.findall(r'<div class="mt-h">(.*?)</div>\s*<table class="ftable">.*?<tbody>(.*?)</tbody>(\s*<tfoot>)?', pack, re.S):
        rows = []
        for a, b, c in re.findall(r'<tr><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td></tr>', tb):
            rows.append([a, unline(b), None if c == '—' else int(c.replace(',', '').replace('円', ''))])
        groups.append({'name': head, 'rows': rows})
        if not tf: groups[-1]['subtotal'] = False
    lis = [x.strip() for x in re.findall(r'<li>(.*?)</li>', re.search(r'<div class="note-h">総額</div>\s*<ul>(.*?)</ul>', pack, re.S).group(1), re.S)]
    costs = {'groups': groups}
    C['costs'] = costs
    # 1行目（合計）と2行目（含まないもの）は自動。それ以外は notes
    tmp = dict(costs, total=True)
    auto = re.findall(r'<li>(.*?)</li>', shiori.pack(dict(costs=tmp))[0])
    if lis and lis[0] == auto[0]:
        lis = lis[1:]
    else:
        costs['total'] = False
    if lis and lis[0].startswith('金額の分かっている分だけの合計。'):
        costs['excl'] = lis[0][len('金額の分かっている分だけの合計。'):]
        lis = lis[1:]
    if lis: costs['notes'] = [unline(x) for x in lis]
    # 日ごと
    days = []
    panels = re.findall(r'<div class="tab-panel" id="day(\d+)">(.*?)</div><!-- /day\d+ -->', s, re.S)
    assert len(panels) == len(tabs), ('tabs vs panels', len(panels), len(tabs))
    for (n, p), (tn, taria, tlab, tsmall) in zip(panels, tabs):
        n = int(n)
        d = {}
        d['date'] = re.search(r'data-date="([\d-]+)"', p).group(1)
        dt = date.fromisoformat(d['date'])
        if tlab.strip() != shiori.md_label(dt): d['tab_label'] = tlab.strip()
        d['tab'] = tsmall
        if taria: d['tab_aria'] = taria
        d['hue'], note = dh[n]
        if note: d['hue_note'] = note
        m = re.search(r'<span class="tag only" aria-label="([^"]*)"><svg class="ic"><use href="#i-([\w-]+)"/></svg></span>\s*<div class="card-title">(.*?)</div>', p, re.S)
        if m.group(1) != shiori.aria_default(dt): d['aria'] = m.group(1)
        d['icon'] = m.group(2); d['title'] = unline(m.group(3))
        st = re.search(r'<div class="stats stats-\d+">(.*?)</div>\s*</div>\s*<div class="trail">', p, re.S)
        if st:
            d['stats'] = [[unline(a), unline(b)] for a, b in re.findall(r'<div class="s"><div class="n">(.*?)</div><div class="l">(.*?)</div></div>', st.group(1))]
        tr = re.search(r'<div class="trail">(.*?)\n      </div>\s*<div class="note">', p, re.S).group(1)
        rows = []
        for line in [x.strip() for x in tr.strip().split('\n') if x.strip()]:
            m = re.match(r'<div class="sun( set)?( in-hike)?" data-t="([^"]*)"><div class="s-t">([^<]*)</div><div class="s-d"></div><div>(日の出|日の入)</div></div>$', line)
            if m:
                rows.append({'sun': True, 't': m.group(4), 'kind': m.group(5), 'inh': bool(m.group(2))}); continue
            m = re.match(r'<div class="tl( [\w ]+)?" data-t="[^"]*"><div class="t-start">([^<]*)</div><div class="t-dur">([^<]*)</div><div class="t-ico"><svg class="ic"><use href="#i-([\w-]+)"/></svg></div><div class="t-sum">(.*?)</div>(?:<div class="t-det">(.*?)</div>)?</div>$', line)
            assert m, ('row', line[:120])
            cls = (m.group(1) or '').split()
            for c in cls: assert c in ('hike', 'stay'), ('class', c)
            rows.append({'sun': False, 't': m.group(2), 'dur': m.group(3), 'ico': m.group(4), 's': unline(m.group(5)),
                         'det': unline(m.group(6) or ''), 'cls': cls})
        d['_rows'] = rows
        nt = re.search(r'<div class="note-h">この日のポイント</div>\s*<ul>(.*?)</ul>', p, re.S)
        d['notes'] = [unline(x) for x in re.findall(r'<li>(.*?)</li>', nt.group(1), re.S)] if nt else []
        days.append(d)
    # 行を文字列へ（所要・登山中の判定が自動と違う所だけフラグ）
    for d in days: d['_raw'] = d.pop('_rows')
    for i, d in enumerate(days):
        rows = d.pop('_raw')
        nw = next((r['t'] for r in days[i + 1]['_raw'] if not r['sun']), None) if i + 1 < len(days) else None
        tl = [r for r in rows if not r['sun']]
        out = []
        for k, r in enumerate(rows):
            if r['sun']:
                prev = next((x for x in reversed(rows[:k]) if not x['sun']), None)
                nx = next((x for x in rows[k + 1:] if not x['sun']), None)
                auto = bool(prev and nx and 'hike' in prev['cls'] and 'hike' in nx['cls'])
                f = '' if auto == r['inh'] else (' | @in' if r['inh'] else ' | @out')
                out.append('%s | %s%s' % (r['t'], r['kind'], f)); continue
            j = tl.index(r)
            if j + 1 < len(tl): dd = shiori.mins(tl[j + 1]['t']) - shiori.mins(r['t'])
            elif nw: dd = shiori.mins(nw) + 1440 - shiori.mins(r['t'])
            else: dd = None
            auto = '—' if dd is None else ('' if dd < 5 else shiori.fmt(dd))
            flags = ['@' + c for c in r['cls']]
            if r['dur'] != auto: flags.append('@dur=' + (r['dur'] or '-'))
            parts = [r['t'], r['ico'], r['s']]
            if r['det']: parts.append(r['det'])
            line = ' | '.join(parts)
            if flags: line += ' | ' + ' '.join(flags)
            out.append(line)
        d['rows'] = out
        notes = d.pop('notes'); d['notes'] = notes   # 行のあとに「この日のポイント」
    C['days'] = days
    C['start'] = days[0]['date']; C['end'] = days[-1]['date']
    return C

class Lit(str): pass
def dump(C):
    order = ['title', 'place', 'start', 'end', 'shelf', 'hues', 'apptitle', 'doctitle', 'ns', 'daterange', 'costs', 'days', 'stays', 'peaks', 'spots']
    out = {k: C[k] for k in order if k in C}
    def rep_str(d, v):
        return d.represent_scalar('tag:yaml.org,2002:str', v, style='"' if (':' in v or v.startswith(('[', '*', '!', '@', '&', '-', '?', '{', '#', '|', '>', '%', '`', "'", '"')) or v in ('', 'null', 'true', 'false', 'yes', 'no') or re.match(r'^[\d.]+$', v)) else None)
    class Dm(yaml.SafeDumper): pass
    Dm.add_representer(str, rep_str)
    def flow_list(d, v):
        if all(not isinstance(x, (dict, list)) for x in v) and len(v) <= 3 and any(isinstance(x, int) or x is None for x in v):
            return d.represent_sequence('tag:yaml.org,2002:seq', v, flow_style=True)
        if len(v) == 2 and all(isinstance(x, str) for x in v) and sum(len(x) for x in v) < 40:
            return d.represent_sequence('tag:yaml.org,2002:seq', v, flow_style=True)
        return d.represent_sequence('tag:yaml.org,2002:seq', v, flow_style=False)
    Dm.add_representer(list, flow_list)
    def date_rep(d, v): return d.represent_scalar('tag:yaml.org,2002:timestamp', v.isoformat())
    return yaml.dump(out, Dumper=Dm, allow_unicode=True, sort_keys=False, width=1000, default_flow_style=False)

def main(src_path, tid, outdir):
    src = open(src_path).read()
    C = parse(src, tid)
    tdir = os.path.join(outdir, tid); os.makedirs(tdir, exist_ok=True)
    cov = C.pop('_cover')
    if cov:
        open(os.path.join(tdir, 'cover.' + ('jpg' if cov[0] == 'jpeg' else cov[0])), 'wb').write(cov[1])
    # place（地名）＝タイトルの「N泊N日」「旅行」を除いた部分
    C['place'] = re.sub(r'旅行$', '', re.sub(r'^(\d+泊\d+日|日帰り)', '', C['title'])) or C['title']
    dr = C.pop('daterange_src')
    if dr != shiori.range_label(date.fromisoformat(C['start']), date.fromisoformat(C['end'])): C['daterange'] = dr
    if C['apptitle'] == C['place'] + 'しおり': del C['apptitle']
    if C['ns'] == tid + '_': del C['ns']
    if C['doctitle'] == shiori.doc_default(C['place'], date.fromisoformat(C['start']), date.fromisoformat(C['end'])): del C['doctitle']
    y = dump(C)
    C2 = yaml.safe_load(y); C2['id'] = tid
    out = shiori.render(C2, tdir)
    a, b = norm(body_of(src)), norm(body_of(out))
    if a != b:
        k = next(i for i in range(min(len(a), len(b))) if a[i] != b[i])
        raise SystemExit('MISMATCH %s\n  src: %s\n  out: %s' % (tid, a[max(0, k - 80):k + 120], b[max(0, k - 80):k + 120]))
    open(os.path.join(tdir, 'trip.yaml'), 'w').write(y)
    print('ok', tid, len(y))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else os.path.join(shiori.ROOT, 'trips'))
