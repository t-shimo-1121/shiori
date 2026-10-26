"""trip.yaml → しおり1冊（単一HTML）

行の書き方（days[].rows の1行）：
  "開始 | アイコン | 概要 | 詳細 | @フラグ"   … 詳細・フラグは省略可
  "6:26 | 日の出"  /  "16:33 | 日の入"       … 日の出入りの区切り行
フラグ：@hike（登山中）@stay（宿で）@dur=1:30（所要を手で指定）@in / @out（日の出入りを登山中に含める／含めない）
文中の記法：[白丸ダム] [表示名](検索語) … Googleマップのリンク
            **要予約** … 日の色のハイライト   !!要注意!! … 朱色
"""
import base64, html, json, os, re, urllib.parse
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, 'templates', 'shiori.html')
WD = '月火水木金土日'

# ── 文中の記法 ──
def inline(s):
    if s is None:
        return ''
    s = str(s)
    def mp(m):
        label, q = m.group(1), m.group(2) or m.group(1)
        return '<a class="map" href="https://www.google.com/maps/search/?api=1&query=%s" target="_blank" rel="noopener">%s</a>' % (
            urllib.parse.quote(q, safe=''), label)
    s = re.sub(r'\[([^\[\]]+)\](?:\(([^()]+)\))?', mp, s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<span class="hl">\1</span>', s)
    s = re.sub(r'!!(.+?)!!', r'<span class="warn">\1</span>', s)
    return s

def mins(t):
    h, m = str(t).split(':'); return int(h) * 60 + int(m)
def fmt(d): return '%d:%02d' % (d // 60, d % 60)
def yen(n): return '—' if n is None else '{:,}円'.format(n)
def D(s): return s if isinstance(s, date) else date.fromisoformat(str(s))

def parse_row(r):
    parts = [p.strip() for p in str(r).split(' | ')]
    flags = {}
    while parts and parts[-1].startswith('@'):
        for f in parts.pop().split():
            k, _, v = f[1:].partition('=')
            flags[k] = v or True
    if len(parts) == 2 and parts[1] in ('日の出', '日の入'):
        return dict(sun=True, t=parts[0], kind='rise' if parts[1] == '日の出' else 'set', flags=flags)
    t, ico, s = parts[:3]
    det = parts[3] if len(parts) > 3 else ''
    return dict(sun=False, t=t, ico=ico, s=s, det=det, flags=flags)

def day_rows(day, next_wake):
    rows = [parse_row(r) for r in day['rows']]
    tl = [r for r in rows if not r['sun']]
    out = []
    for k, r in enumerate(rows):
        if r['sun']:
            prev = next((x for x in reversed(rows[:k]) if not x['sun']), None)
            nxt = next((x for x in rows[k + 1:] if not x['sun']), None)
            inh = bool(prev and nxt and prev['flags'].get('hike') and nxt['flags'].get('hike'))
            if r['flags'].get('in'): inh = True
            if r['flags'].get('out'): inh = False
            cls = (' set' if r['kind'] == 'set' else '') + (' in-hike' if inh else '')
            out.append('        <div class="sun%s" data-t="%s"><div class="s-t">%s</div><div class="s-d"></div><div>%s</div></div>'
                       % (cls, r['t'], r['t'], '日の出' if r['kind'] == 'rise' else '日の入'))
            continue
        i = tl.index(r)
        if 'dur' in r['flags']:
            dur = r['flags']['dur'] if r['flags']['dur'] is not True else ''
            if dur == '-': dur = ''
        else:
            if i + 1 < len(tl): d = mins(tl[i + 1]['t']) - mins(r['t'])
            elif next_wake: d = mins(next_wake) + 1440 - mins(r['t'])
            else: d = None
            dur = '—' if d is None else ('' if d < 5 else fmt(d))
        cls = ' '.join(c for c in ('hike', 'stay') if r['flags'].get(c))
        hh, mm = r['t'].split(':')
        out.append('        <div class="tl%s" data-t="%02d:%s"><div class="t-start">%s</div><div class="t-dur">%s</div><div class="t-ico"><svg class="ic"><use href="#i-%s"/></svg></div><div class="t-sum">%s</div>%s</div>'
                   % (' ' + cls if cls else '', int(hh), mm, r['t'], dur, r['ico'], inline(r['s']),
                      ('<div class="t-det">%s</div>' % inline(r['det'])) if r['det'] else ''))
    return '\n'.join(out)

def md_label(d): return '%d/%d %s' % (d.month, d.day, WD[d.weekday()])
def aria_default(d): return '%d/%d（%s）' % (d.month, d.day, WD[d.weekday()])
def range_label(a, b):
    s = '%d.%d.%d(%s)' % (a.year, a.month, a.day, WD[a.weekday()])
    if a == b: return s
    e = ('%d.%d.%d(%s)' % (b.year, b.month, b.day, WD[b.weekday()])) if a.year != b.year else '%d.%d(%s)' % (b.month, b.day, WD[b.weekday()])
    return s + ' — ' + e

def doc_default(place, a, b):
    if a == b: e = ''
    elif a.year != b.year: e = '-%d.%d.%d' % (b.year, b.month, b.day)
    elif a.month != b.month: e = '-%d.%d' % (b.month, b.day)
    else: e = '-%d' % b.day
    return '%s旅行 %d.%d.%d%s' % (place, a.year, a.month, a.day, e)

def card(n, day, next_wake):
    d = D(day['date'])
    stats = ''
    if day.get('stats'):
        stats = '      <div class="mt">\n        <div class="stats stats-%d">%s</div>\n      </div>\n' % (len(day['stats']), ''.join(
            '<div class="s"><div class="n">%s</div><div class="l">%s</div></div>' % (inline(a), inline(b)) for a, b in day['stats']))
    return '''  <!-- ══════════ Day%d ══════════ -->
  <div class="tab-panel" id="day%d">
    <div class="card day%d" data-date="%s">
      <div class="card-head">
        <span class="tag only" aria-label="%s"><svg class="ic"><use href="#i-%s"/></svg></span>
        <div class="card-title">%s</div>
      </div>
%s      <div class="trail">
%s
      </div>
    </div>
  </div><!-- /day%d -->
''' % (n, n, n, d.isoformat(), day.get('aria') or aria_default(d), day['icon'], inline(day['title']), stats,
       day_rows(day, next_wake), n)

def ftable(g):
    head = g['name']
    sub = ('日程', '宿泊先') if head == '宿泊費' else ('日付', '項目')
    rows = [(str(a), b, c) for a, b, c in g['rows']]
    body = '\n'.join('            <tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (a, inline(b), yen(c)) for a, b, c in rows)
    vals = [c for _, _, c in rows if c]
    return '''      <div class="mt">
        <div class="mt-h">%s</div>
        <table class="ftable">
          <thead><tr><th>%s</th><th>%s</th><th>金額</th></tr></thead>
          <tbody>
%s
          </tbody>
%s        </table>
      </div>
''' % (head, sub[0], sub[1], body, '' if g.get('subtotal') is False else '          <tfoot><tr><td colspan="2">小計</td><td>%s</td></tr></tfoot>\n' % yen(sum(vals) if vals else None))

SHORT = {'交通費': '交通', '宿泊費': '宿泊', '食事ほか': '食事'}
def excl_line(x):
    """補足を短く：「AとBは含まない。」→「含まない：AとB」"""
    x = str(x).strip()
    m = re.match(r'^(.*?)は含まない。?$', x)
    if m and '。' not in m.group(1): return '含まない：' + m.group(1)
    return x
def packing(C):
    """持ち物：packing＝[{group, items:[…]}]。項目は「品物｜補足」で下に小さく補足"""
    P = C.get('packing')
    if not P: return ''
    body = ''
    for g in P:
        body += '      <div class="cat">%s</div>\n' % inline(g['group'])
        for it in g['items']:
            t, _, sub = str(it).partition('｜')
            body += '      <div class="item"><span class="box"></span><span class="txt">%s%s</span></div>\n' % (inline(t), ('<small>%s</small>' % inline(sub)) if sub else '')
    return '''    <div class="card pack">
      <div class="card-head">
        <span class="tag only" aria-hidden="true"><svg class="ic"><use href="#i-bag"/></svg></span>
        <div class="card-title">持ち物</div>
        <button class="fold" type="button" aria-pressed="false">済みを隠す</button>
        <span class="counter"></span>
      </div>
%s      <div class="all-done">全部そろいました</div>
    </div>

''' % body

def pack(C):
    costs = C['costs']
    parts, tot, expl = [], 0, []
    for g in costs['groups']:
        parts.append(ftable(g))
        s = sum(c for _, _, c in g['rows'] if c); tot += s
        if s: expl.append((g.get('short') or SHORT.get(g['name'], re.sub(r'(費|料)$', '', g['name'])), s))
    total = """      <div class="mt total">
        <div class="tot-row"><span class="tot-l">総額</span><span class="tot-v">%s</span></div>
        <div class="tot-sub">%s</div>
%s      </div>
""" % (yen(tot), ''.join('<span>%s<b>%s</b></span>' % (k, '{:,}円'.format(v)) for k, v in expl),
       ('        <div class="tot-ex">%s</div>\n' % inline(excl_line(costs['excl']))) if costs.get('excl') else '')
    return """  <!-- ══════════ 準備タブ ══════════ -->
  <div class="tab-panel is-active" id="pack">

%s    <div class="card pack">
      <div class="card-head">
        <span class="tag only" aria-hidden="true"><svg class="ic"><use href="#i-coin"/></svg></span>
        <div class="card-title">費用</div>
      </div>

%s
%s    </div>

  </div><!-- /pack -->

""" % (packing(C), total, '\n'.join(parts)), tot

def cover_html(C, tdir):
    p = cover_path(tdir)
    if not p:
        return '      <div class="cover-ph">表紙イラスト（後で差し替え）</div>'
    ext = os.path.splitext(p)[1][1:].replace('jpg', 'jpeg')
    return '      <img src="data:image/%s;base64,%s" alt="%s の表紙">' % (ext, base64.b64encode(open(p, 'rb').read()).decode(), html.escape(C['title']))

def cover_path(tdir):
    for ext in ('webp', 'jpg', 'jpeg', 'png'):
        p = os.path.join(tdir, 'cover.' + ext)
        if os.path.exists(p): return p
    return None

def tab_cols(k):
    """タブ k 枚を等幅で並べる列数。4枚までは1行、5〜8枚は2行、9枚以上は1行5枚"""
    if k <= 4: return k
    if k <= 8: return -(-k // 2)
    return 5

def render(C, tdir):
    days = C['days']
    dates = [D(d['date']) for d in days]
    n = len(days)
    start, end = D(C['start']), D(C['end'])
    hues = C['hues']
    hue_vars = '  --h-base: %3d;    /* 紙・文字・罫線のベース色相 */\n  --h-brand:%3d;    /* 表紙まわり・見出しのアクセント */\n  --h-pack: %3d;    /* 準備タブ */\n' % (
        hues['base'], hues['brand'], hues['pack'])
    hue_vars += ''.join('  --h-d%d:%5d;     /* %s */\n' % (i + 1, d['hue'], d.get('hue_note', '')) for i, d in enumerate(days))
    rng = range(1, n + 1)
    tab_rules = ''.join('.tab-btn.active.t%d{background:hsl(var(--h-d%d),46%%,36%%);}\n' % (i, i) for i in rng)
    day_rules = ''.join('.day%d{--c:hsl(var(--h-d%d),46%%,36%%);--c-bg:hsl(var(--h-d%d),45%%,94%%);--c-tint:hsl(var(--h-d%d),45%%,97%%);}\n' % (i, i, i, i) for i in rng)
    day_dark = ''.join('  .day%d{--c:hsl(var(--h-d%d),50%%,64%%);--c-bg:hsl(var(--h-d%d),26%%,18%%);--c-tint:hsl(var(--h-d%d),26%%,16%%);}\n' % (i, i, i, i) for i in rng)
    tabs = '\n'.join('    <button class="tab-btn t%d" data-tab="day%d" role="tab"%s>%s<small>%s</small></button>'
                     % (i + 1, i + 1, (' aria-label="%s"' % d['tab_aria']) if d.get('tab_aria') else '',
                        d.get('tab_label') or md_label(dates[i]), d['tab'])
                     for i, d in enumerate(days))
    packhtml, tot = pack(C)
    if 'excel_total' in C['costs']:
        assert tot == C['costs']['excel_total'], ('費用の合計が Excel と合わない', tot, C['costs']['excel_total'])
    cards = ''.join(card(i + 1, d, (days[i + 1]['rows'] and next(parse_row(r)['t'] for r in days[i + 1]['rows'] if not parse_row(r)['sun'])) if i + 1 < n else None)
                    for i, d in enumerate(days))
    body = '''<div class="wrap">

  <!-- ══════════ 表紙 ══════════ -->
  <div class="cover">
    <div class="cover-frame">
%s
    </div>
    <div class="cover-cap">
      <h1>%s</h1>
      <div class="date">%s</div>
      <div class="count" id="countdown"></div>
    </div>
  </div>

  <!-- ══════════ タブ ══════════ -->
  <div class="tabs" role="tablist" style="--cols:%d">
    <button class="tab-btn t0 active" data-tab="pack" role="tab">準備<small>%s</small></button>
%s
  </div>


''' % (cover_html(C, tdir), html.escape(C['title']), C.get('daterange') or range_label(start, end), tab_cols(n + 1),
       '持ち物・費用' if C.get('packing') else '費用', tabs) + packhtml + cards + '\n\n</div>\n\n\n'
    t = open(TEMPLATE).read()
    rep = {
        'apptitle': C.get('apptitle') or (C['place'] + 'しおり'),
        'doctitle': C.get('doctitle') or doc_default(C['place'], start, end),
        'days_json': json.dumps([d.isoformat() for d in dates]),
        'hue_vars': hue_vars, 'tab_rules': tab_rules, 'day_rules': day_rules, 'day_rules_dark': day_dark,
        'ns': C.get('ns') or (C['id'] + '_'), 'start': dates[0].isoformat(), 'body': body,
    }
    for k, v in rep.items():
        t = t.replace('{{%s}}' % k, v)
    assert '{{' not in t
    for bad in ['⇄', '⇔']:
        assert bad not in t, bad
    return t
