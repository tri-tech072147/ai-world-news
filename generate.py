import feedparser
import datetime
import html
import re
import json
import os
import glob

FEEDS = [
    {"key": "TechCrunch",  "label": "TechCrunch AI",  "flag": "🇺🇸", "country": "米国", "color": "#0a8a5c", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"key": "MIT",         "label": "MIT Tech Review", "flag": "🇺🇸", "country": "米国", "color": "#a00c0c", "url": "https://www.technologyreview.com/feed/"},
    {"key": "VentureBeat", "label": "VentureBeat AI",  "flag": "🇺🇸", "country": "米国", "color": "#7b2fd4", "url": "https://venturebeat.com/category/ai/feed/"},
    {"key": "TheVerge",    "label": "The Verge AI",    "flag": "🇺🇸", "country": "米国", "color": "#e5472d", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
]

def strip_tags(text):
    text = re.sub(r'<[^>]+>', '', text or '')
    text = re.sub(r'&[a-z#0-9]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def format_date(entry):
    try:
        t = entry.get("published_parsed") or entry.get("updated_parsed")
        if t:
            dt = datetime.datetime(*t[:6])
            return dt.strftime("%Y年%-m月%-d日")
    except:
        pass
    return ""

def split_at_sentence(text, limit):
    if len(text) <= limit:
        return text, ""
    cut = text.rfind(". ", 0, limit)
    if cut == -1 or cut < limit // 2:
        cut = text.rfind(" ", 0, limit)
    if cut == -1:
        cut = limit
    else:
        cut += 1
    return text[:cut].strip(), text[cut:].strip()

def fetch_articles():
    articles = []
    for feed_info in FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:8]:
                summary_raw = (
                    entry.get("summary") or
                    entry.get("description") or
                    (entry.get("content") or [{}])[0].get("value", "")
                )
                full_text = strip_tags(summary_raw).strip()
                summary, rest = split_at_sentence(full_text, 200)
                if rest:
                    summary += "…"
                body_text, _ = split_at_sentence(rest, 400) if rest else ("", "")
                body = (body_text + ("…" if len(rest) > 400 else "")) if rest else ""
                articles.append({
                    "feedKey":   feed_info["key"],
                    "feedLabel": feed_info["label"],
                    "feedColor": feed_info["color"],
                    "flag":      feed_info["flag"],
                    "country":   feed_info["country"],
                    "title":     strip_tags(entry.get("title", "")),
                    "summary":   summary,
                    "body":      body,
                    "url":       entry.get("link", "#"),
                    "date":      format_date(entry),
                })
        except Exception as e:
            print(f"Error fetching {feed_info['key']}: {e}")
    return articles[:30]

def save_to_archive(articles):
    today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")
    os.makedirs("data", exist_ok=True)
    path = f"data/{today}.json"
    existing = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            existing = json.load(f)
    existing_urls = {a["url"] for a in existing}
    new_articles = [a for a in articles if a["url"] not in existing_urls]
    merged = existing + new_articles
    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(new_articles)} new articles to {path} (total: {len(merged)})")

def load_archive_index():
    files = sorted(glob.glob("data/*.json"), reverse=True)
    return [os.path.basename(f).replace(".json", "") for f in files]

def render_card(a, i, prefix=""):
    delay = min(i * 0.05, 0.4)
    uid = f"{prefix}body_{i}_{abs(hash(a.get('url','')) % 10000)}"
    body_html = ""
    read_more_btn = ""
    if a.get("body"):
        summary_trimmed = a["summary"].rstrip("…").rstrip("…").rstrip()
        full_inline = html.escape(summary_trimmed + " " + a["body"])
        body_html = f'<p class="card-body" id="{uid}" style="display:none">{full_inline}</p>'
        read_more_btn = f'<button class="read-more" onclick="toggleBody(\'{uid}\',this)">続きを読む ▾</button>'
    return f"""
    <article class="news-card" style="animation-delay:{delay}s">
      <div class="card-meta">
        <span class="country-flag">{a['flag']}</span>
        <span class="country-label">{a['country']}</span>
        <span class="feed-label" style="color:{a['feedColor']}">{html.escape(a['feedLabel'])}</span>
        {"<span class='pub-date'>📅 " + html.escape(a['date']) + "</span>" if a['date'] else ""}
      </div>
      <h2 class="card-title">{html.escape(a['title'])}</h2>
      <p class="card-summary" id="s_{uid}">{html.escape(a['summary'])}</p>
      {body_html}
      <div class="card-footer">
        {read_more_btn}
        <a class="source-link" href="{html.escape(a['url'])}" target="_blank" rel="noopener">↗ 原文を読む</a>
      </div>
    </article>"""

def generate_html(articles):
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    updated = now.strftime("%Y/%m/%d %H:%M")
    count = len(articles)
    sources = len(set(a["feedKey"] for a in articles))

    cards_all = "\n".join(render_card(a, i) for i, a in enumerate(articles))
    feed_sections = ""
    for feed in FEEDS:
        filtered = [a for a in articles if a["feedKey"] == feed["key"]]
        cards = "\n".join(render_card(a, i, prefix=feed["key"]) for i, a in enumerate(filtered))
        feed_sections += f'<div class="feed-section" data-feed="{feed["key"]}" style="display:none"><div class="news-grid">{cards}</div></div>\n'

    archive_dates = load_archive_index()
    archive_dates_js = json.dumps(archive_dates)

    all_archive_data = {}
    for date_str in archive_dates:
        path = f"data/{date_str}.json"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                all_archive_data[date_str] = json.load(f)
    archive_data_js = json.dumps(all_archive_data, ensure_ascii=False)

    now_y = now.year
    now_m = now.month
    now_d = now.day
    archive_count = len(archive_dates)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI World News — 世界のAIニュース</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{
    --bg: #ffffff; --bg-secondary: #f7f7f5; --bg-tertiary: #f0eeea;
    --text: #1a1a18; --text-secondary: #5a5a56; --text-tertiary: #9a9a94;
    --border: rgba(0,0,0,0.09); --border-mid: rgba(0,0,0,0.16);
    --accent: #185fa5; --radius-md: 8px; --radius-lg: 14px;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #1c1c1a; --bg-secondary: #252523; --bg-tertiary: #2a2a27;
      --text: #f0eeea; --text-secondary: #a8a8a0; --text-tertiary: #6a6a64;
      --border: rgba(255,255,255,0.08); --border-mid: rgba(255,255,255,0.16);
      --accent: #5ba3e8;
    }}
  }}
  html {{ scroll-behavior: smooth; }}
  body {{
    font-family: -apple-system, 'Hiragino Sans', 'Hiragino Kaku Gothic ProN', 'Noto Sans JP', sans-serif;
    background: var(--bg-tertiary); color: var(--text); font-size: 15px; line-height: 1.6; min-height: 100vh;
  }}
  .page-wrap {{ max-width: 740px; margin: 0 auto; padding: 0 16px 80px; }}
  .header {{ padding: 28px 0 18px; border-bottom: 0.5px solid var(--border-mid); margin-bottom: 20px; }}
  .header-top {{ display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }}
  .site-title {{ font-size: 23px; font-weight: 700; color: var(--text); letter-spacing: -0.8px; }}
  .site-sub {{ font-size: 13px; color: var(--text-tertiary); }}
  .header-meta {{ display: flex; align-items: center; gap: 10px; margin-top: 10px; flex-wrap: wrap; }}
  .badge-live {{ font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 20px; background: #e8f5e9; color: #2e7d32; }}
  .updated {{ font-size: 12px; color: var(--text-tertiary); }}
  .tabs {{ display: flex; gap: 0; margin-bottom: 20px; border-bottom: 1.5px solid var(--border-mid); }}
  .tab-btn {{
    font-size: 13px; font-weight: 600; padding: 10px 20px;
    border: none; background: none; color: var(--text-tertiary);
    cursor: pointer; font-family: inherit;
    border-bottom: 2.5px solid transparent; margin-bottom: -1.5px;
    transition: all 0.15s;
  }}
  .tab-btn.active {{ color: var(--text); border-bottom-color: var(--text); }}
  .tab-btn:hover:not(.active) {{ color: var(--text-secondary); }}
  .tab-panel {{ display: none; }}
  .tab-panel.active {{ display: block; }}
  .controls {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 14px; align-items: center; }}
  .filter-btn {{
    font-size: 12px; padding: 6px 13px; border-radius: 20px;
    border: 0.5px solid var(--border-mid); background: var(--bg);
    color: var(--text-secondary); cursor: pointer; transition: all 0.15s; font-family: inherit;
  }}
  .filter-btn.active {{ background: var(--text); color: var(--bg); border-color: var(--text); }}
  .filter-btn:hover:not(.active) {{ background: var(--bg-secondary); color: var(--text); }}
  .refresh-btn {{
    margin-left: auto; font-size: 12px; padding: 6px 14px; border-radius: 20px;
    border: 0.5px solid var(--border-mid); background: var(--bg);
    color: var(--text-secondary); cursor: pointer; display: flex;
    align-items: center; gap: 6px; font-family: inherit;
  }}
  .refresh-btn:hover {{ color: var(--text); background: var(--bg-secondary); }}
  .date-search {{
    background: var(--bg); border: 0.5px solid var(--border);
    border-radius: var(--radius-lg); padding: 18px; margin-bottom: 16px;
  }}
  .date-search h3 {{ font-size: 13px; font-weight: 600; margin-bottom: 14px; color: var(--text-secondary); }}
  .date-row {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }}
  .date-label {{ font-size: 12px; color: var(--text-secondary); min-width: 24px; }}
  .date-select {{
    font-size: 12px; padding: 5px 8px; border-radius: 8px;
    border: 0.5px solid var(--border-mid); background: var(--bg-secondary);
    color: var(--text); font-family: inherit; cursor: pointer;
  }}
  .date-sep {{ font-size: 12px; color: var(--text-tertiary); }}
  .search-btn {{
    margin-top: 4px; font-size: 12px; padding: 7px 18px; border-radius: 20px;
    background: var(--text); color: var(--bg); border: none;
    cursor: pointer; font-family: inherit; font-weight: 600;
  }}
  .search-btn:hover {{ opacity: 0.85; }}
  .archive-note {{ font-size: 11px; color: var(--text-tertiary); margin-top: 10px; }}
  .stats-bar {{
    display: flex; gap: 18px; margin-bottom: 16px; flex-wrap: wrap;
    padding: 10px 14px; background: var(--bg-secondary);
    border-radius: var(--radius-md); border: 0.5px solid var(--border);
  }}
  .stat {{ font-size: 12px; color: var(--text-secondary); }}
  .stat strong {{ color: var(--text); font-weight: 600; }}
  .news-grid {{ display: flex; flex-direction: column; gap: 10px; }}
  .news-card {{
    background: var(--bg); border: 0.5px solid var(--border);
    border-radius: var(--radius-lg); padding: 18px;
    transition: border-color 0.15s, box-shadow 0.15s;
    animation: fadeUp 0.35s ease both;
  }}
  .news-card:hover {{ border-color: var(--border-mid); box-shadow: 0 2px 14px rgba(0,0,0,0.07); }}
  @keyframes fadeUp {{ from {{ opacity:0; transform:translateY(10px); }} to {{ opacity:1; transform:translateY(0); }} }}
  .card-meta {{ display: flex; align-items: center; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }}
  .country-flag {{ font-size: 15px; }}
  .country-label {{
    font-size: 11px; font-weight: 600; color: var(--text-secondary);
    background: var(--bg-secondary); padding: 2px 8px; border-radius: 10px; border: 0.5px solid var(--border);
  }}
  .feed-label {{ font-size: 11px; font-weight: 700; margin-left: 2px; }}
  .pub-date {{ font-size: 11px; color: var(--text-tertiary); margin-left: auto; white-space: nowrap; }}
  .card-title {{ font-size: 16px; font-weight: 600; color: var(--text); line-height: 1.45; margin-bottom: 10px; }}
  .card-summary {{
    font-size: 13px; color: var(--text-secondary); line-height: 1.65;
    margin-bottom: 12px; border-left: 2px solid var(--border-mid); padding-left: 12px; font-style: italic;
    word-break: break-word; overflow-wrap: break-word;
  }}
  .card-body {{ font-size: 13px; color: var(--text-secondary); line-height: 1.65; margin-top: 8px; margin-bottom: 12px; word-break: break-word; overflow-wrap: break-word; }}
  .card-footer {{ display: flex; align-items: center; margin-top: 8px; gap: 10px; flex-wrap: wrap; }}
  .read-more {{ font-size: 12px; color: var(--text-secondary); background: none; border: none; cursor: pointer; padding: 0; font-family: inherit; text-decoration: underline; text-underline-offset: 2px; }}
  .source-link {{ font-size: 12px; color: var(--accent); text-decoration: none; margin-left: auto; display: flex; align-items: center; gap: 4px; }}
  .source-link:hover {{ text-decoration: underline; }}
  .empty-msg {{ text-align: center; padding: 40px 20px; color: var(--text-tertiary); font-size: 14px; line-height: 1.8; }}
  .footer {{ margin-top: 40px; padding-top: 20px; border-top: 0.5px solid var(--border); text-align: center; font-size: 12px; color: var(--text-tertiary); line-height: 1.8; }}
  @media (max-width: 480px) {{
    .site-title {{ font-size: 19px; }} .card-title {{ font-size: 15px; }}
    .header {{ padding: 18px 0 14px; }} .news-card {{ padding: 14px; }}
    .pub-date {{ margin-left: 0; }} .tab-btn {{ padding: 8px 14px; font-size: 12px; }}
  }}
</style>
</head>
<body>
<div class="page-wrap">
  <header class="header">
    <div class="header-top">
      <span class="site-title">AI World News</span>
      <span class="site-sub">世界のAIニュース — 日本語版</span>
    </div>
    <div class="header-meta">
      <span class="badge-live">● LIVE</span>
      <span class="updated">🕐 {updated} JST 更新</span>
    </div>
  </header>

  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('latest', this)">最新記事</button>
    <button class="tab-btn" onclick="switchTab('archive', this)">期間指定</button>
  </div>

  <div class="tab-panel active" id="tab-latest">
    <div class="controls">
      <button class="filter-btn active" onclick="filterNews('all', this)">すべて</button>
      <button class="filter-btn" onclick="filterNews('TechCrunch', this)">TechCrunch</button>
      <button class="filter-btn" onclick="filterNews('MIT', this)">MIT Tech Review</button>
      <button class="filter-btn" onclick="filterNews('VentureBeat', this)">VentureBeat</button>
      <button class="filter-btn" onclick="filterNews('TheVerge', this)">The Verge</button>
      <button class="refresh-btn" onclick="location.reload()">↻ 更新</button>
    </div>
    <div class="stats-bar">
      <span class="stat">記事数: <strong>{count}</strong></span>
      <span class="stat">ソース: <strong>{sources}</strong></span>
      <span class="stat">次回更新: <strong>約1時間後</strong></span>
    </div>
    <div id="latest-container">
      <div class="feed-section" data-feed="all"><div class="news-grid">{cards_all}</div></div>
      {feed_sections}
    </div>
  </div>

  <div class="tab-panel" id="tab-archive">
    <div class="date-search">
      <h3>📅 期間を指定して記事を検索</h3>
      <div class="date-row">
        <span class="date-label">開始</span>
        <select class="date-select" id="from-y" onchange="updateDays('from')"></select>
        <span class="date-sep">年</span>
        <select class="date-select" id="from-m" onchange="updateDays('from')"></select>
        <span class="date-sep">月</span>
        <select class="date-select" id="from-d"></select>
        <span class="date-sep">日</span>
      </div>
      <div class="date-row">
        <span class="date-label">終了</span>
        <select class="date-select" id="to-y" onchange="updateDays('to')"></select>
        <span class="date-sep">年</span>
        <select class="date-select" id="to-m" onchange="updateDays('to')"></select>
        <span class="date-sep">月</span>
        <select class="date-select" id="to-d"></select>
        <span class="date-sep">日</span>
      </div>
      <button class="search-btn" onclick="searchArchive()">この期間の記事を表示</button>
      <p class="archive-note">蓄積データ: {archive_count}日分</p>
    </div>
    <div id="archive-results"></div>
  </div>

  <footer class="footer">
    <p>AI World News — GitHub Actionsで1時間ごとに自動更新・過去ログ蓄積</p>
    <p>記事の著作権は各メディアに帰属します</p>
  </footer>
</div>

<script>
const ARCHIVE = {archive_data_js};
const ARCHIVE_DATES = {archive_dates_js};
const NOW_Y = {now_y}, NOW_M = {now_m}, NOW_D = {now_d};

function switchTab(name, btn) {{
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
}}

function filterNews(key, btn) {{
  document.querySelectorAll('#tab-latest .filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('#latest-container .feed-section').forEach(s => {{
    s.style.display = s.dataset.feed === key ? 'block' : 'none';
  }});
}}
document.querySelector('[data-feed="all"]').style.display = 'block';

function toggleBody(id, btn) {{
  const body = document.getElementById(id);
  const summary = document.getElementById('s_' + id);
  const expanded = body.style.display === 'none';
  body.style.display = expanded ? 'block' : 'none';
  if (summary) summary.style.display = expanded ? 'none' : 'block';
  btn.textContent = expanded ? '閉じる ▴' : '続きを読む ▾';
}}

function daysInMonth(y, m) {{ return new Date(y, m, 0).getDate(); }}

function buildSelect(el, values, selected) {{
  el.innerHTML = '';
  values.forEach(v => {{
    const opt = document.createElement('option');
    opt.value = v;
    opt.textContent = v;
    if (v == selected) opt.selected = true;
    el.appendChild(opt);
  }});
}}

function updateDays(prefix) {{
  const y = parseInt(document.getElementById(prefix + '-y').value);
  const m = parseInt(document.getElementById(prefix + '-m').value);
  const max = daysInMonth(y, m);
  const cur = parseInt(document.getElementById(prefix + '-d').value) || 1;
  buildSelect(document.getElementById(prefix + '-d'), Array.from({{length: max}}, (_, i) => i + 1), Math.min(cur, max));
}}

function initDatePickers() {{
  const years = [];
  for (let y = 2023; y <= NOW_Y; y++) years.push(y);
  const months = Array.from({{length: 12}}, (_, i) => i + 1);
  buildSelect(document.getElementById('from-y'), years, NOW_Y);
  buildSelect(document.getElementById('from-m'), months, NOW_M);
  updateDays('from');
  document.getElementById('from-d').value = NOW_D;
  buildSelect(document.getElementById('to-y'), years, NOW_Y);
  buildSelect(document.getElementById('to-m'), months, NOW_M);
  updateDays('to');
  document.getElementById('to-d').value = NOW_D;
}}

function searchArchive() {{
  const fy = document.getElementById('from-y').value;
  const fm = String(document.getElementById('from-m').value).padStart(2,'0');
  const fd = String(document.getElementById('from-d').value).padStart(2,'0');
  const ty = document.getElementById('to-y').value;
  const tm = String(document.getElementById('to-m').value).padStart(2,'0');
  const td = String(document.getElementById('to-d').value).padStart(2,'0');
  const fromStr = `${{fy}}-${{fm}}-${{fd}}`;
  const toStr   = `${{ty}}-${{tm}}-${{td}}`;

  if (fromStr > toStr) {{ alert('開始日が終了日より後になっています。'); return; }}

  let results = [];
  const urls = new Set();
  for (const [date, articles] of Object.entries(ARCHIVE)) {{
    if (date >= fromStr && date <= toStr) {{
      articles.forEach(a => {{
        if (!urls.has(a.url)) {{ urls.add(a.url); results.push({{...a, _d: date}}); }}
      }});
    }}
  }}
  results.sort((a, b) => b._d.localeCompare(a._d));

  const container = document.getElementById('archive-results');
  if (results.length === 0) {{
    const oldest = ARCHIVE_DATES.length > 0 ? ARCHIVE_DATES[ARCHIVE_DATES.length - 1] : null;
    container.innerHTML = `<div class="empty-msg">📭 この期間の記事はありません。${{oldest ? '<br>データは ' + oldest + ' から蓄積されています' : ''}}</div>`;
    return;
  }}

  const cards = results.map((a, i) => buildCard(a, i)).join('');
  container.innerHTML = `
    <div class="stats-bar">
      <span class="stat">期間: <strong>${{fromStr}} 〜 ${{toStr}}</strong></span>
      <span class="stat">記事数: <strong>${{results.length}}</strong></span>
    </div>
    <div class="news-grid">${{cards}}</div>`;
}}

function buildCard(a, i) {{
  const delay = Math.min(i * 0.04, 0.4);
  const uid = `arc_${{i}}_${{Math.abs(hc(a.url||'')) % 10000}}`;
  let bodyHtml = '', readMoreBtn = '';
  if (a.body) {{
    const trimmed = a.summary.replace(/…+$/, '').trim();
    const full = esc(trimmed + ' ' + a.body);
    bodyHtml = `<p class="card-body" id="${{uid}}" style="display:none">${{full}}</p>`;
    readMoreBtn = `<button class="read-more" onclick="toggleBody('${{uid}}',this)">続きを読む ▾</button>`;
  }}
  return `<article class="news-card" style="animation-delay:${{delay}}s">
    <div class="card-meta">
      <span class="country-flag">${{a.flag||'🌐'}}</span>
      <span class="country-label">${{esc(a.country||'')}}</span>
      <span class="feed-label" style="color:${{a.feedColor||'#666'}}">${{esc(a.feedLabel||'')}}</span>
      ${{a.date ? `<span class="pub-date">📅 ${{esc(a.date)}}</span>` : ''}}
    </div>
    <h2 class="card-title">${{esc(a.title||'')}}</h2>
    <p class="card-summary" id="s_${{uid}}">${{esc(a.summary||'')}}</p>
    ${{bodyHtml}}
    <div class="card-footer">
      ${{readMoreBtn}}
      <a class="source-link" href="${{esc(a.url||'#')}}" target="_blank" rel="noopener">↗ 原文を読む</a>
    </div>
  </article>`;
}}

function esc(s) {{ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }}
function hc(s) {{ let h=0; for(let i=0;i<s.length;i++) h=Math.imul(31,h)+s.charCodeAt(i)|0; return h; }}

initDatePickers();
</script>
</body>
</html>"""

if __name__ == "__main__":
    print("Fetching RSS feeds...")
    articles = fetch_articles()
    print(f"Fetched {len(articles)} articles")
    save_to_archive(articles)
    html_content = generate_html(articles)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("index.html generated!")
