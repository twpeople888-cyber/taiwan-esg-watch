#!/usr/bin/env python3
"""Generate a source-backed ESG weekly report and archives from reviewed JSON data.
This program does not perform autonomous policy research or legal verification.
"""
import argparse
import html
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

STATUS = {
    'effective': ('已正式實施', '#147d5b'),
    'announced': ('已公布尚未生效', '#9c6200'),
    'draft': ('研議中／草案', '#7752a2'),
}
CSS = '''
:root{color-scheme:light;--ink:#163c33;--green:#147b60;--bg:#f3f7f5}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#24352e;font:16px/1.75 system-ui,"Microsoft JhengHei",sans-serif}
header{background:linear-gradient(110deg,#10483a,#168267);color:#fff;padding:40px max(20px,calc((100vw - 1080px)/2))}
header h1{margin:0;font-size:clamp(26px,4vw,38px)}a{color:#116b54}header a{color:#e4fff4}
main{max-width:1080px;margin:auto;padding:28px 18px 60px}article,.panel{background:#fff;border:1px solid #dce9e3;border-radius:14px;padding:22px;margin:16px 0;box-shadow:0 3px 12px #082b1908}
h2{color:var(--ink)}article h3{margin:.4em 0}small,.muted{color:#5d7168}.pill{font-size:13px;border-radius:30px;padding:4px 10px;display:inline-block;background:#edf4ef}
.meta{display:flex;gap:12px;flex-wrap:wrap;color:#65736d;font-size:14px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:15px}
footer{max-width:1080px;margin:0 auto 30px;padding:0 18px;color:#67796e}li{margin:.45em 0}
'''
def h(value): return html.escape(str(value), quote=True)
def page(title, body):
    return f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{h(title)}</title><style>{CSS}</style></head><body><header><h1>🌱 臺灣 ESG 永續政策觀測站</h1><p>ESG · GHG · MRV｜政策儀表板＋學習資料庫</p><a href="../index.html">回網站首頁</a>　<a href="index.html">歷史週報</a></header><main>{body}</main><footer>資訊整理與學習用途；政策適用性以主管機關正式公告為準。發布前須人工查證資料來源。</footer></body></html>'

def verify(data, beginning, ending):
    if not isinstance(data, dict) or not isinstance(data.get('items'), list):
        raise ValueError('資料必須包含 items 陣列。')
    out=[]
    for n, item in enumerate(data['items'], 1):
        for key in ('title','announcement_date','status','source_title','source_url','summary','importance','taiwan_impact'):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f'第 {n} 項缺少文字欄位：{key}')
        if item['status'] not in STATUS:
            raise ValueError(f'第 {n} 項 status 必須是 effective / announced / draft')
        announcement = date.fromisoformat(item['announcement_date'])
        if not beginning <= announcement <= ending:
            raise ValueError(f'第 {n} 項公告日期 {announcement} 不在本週 {beginning} 至 {ending}；不要將舊聞包裝成新訊。')
        if item.get('effective_date'):
            date.fromisoformat(item['effective_date'])
        if item.get('effective_date') and item['status']=='draft':
            raise ValueError(f'第 {n} 項為草案卻設定了生效日期；請重新確認。')
        url = urlparse(item['source_url'])
        if url.scheme != 'https' or not url.netloc or url.username or url.password:
            raise ValueError(f'第 {n} 項需使用有效的 HTTPS 官方原始來源網址。')
        # Source authority is reviewed by a human, not inferred from URL alone.
        out.append(item)
    return out

def render_item(item):
    status, color = STATUS[item['status']]
    effective = h(item.get('effective_date') or '未公告／不適用')
    concepts = item.get('concepts', '')
    extra = f'<p><strong>入門觀念：</strong>{h(concepts)}</p>' if concepts else ''
    return f'''<article><span class="pill" style="color:{color};border:1px solid {color}">{h(status)}</span>
      <h3>{h(item['title'])}</h3><div class="meta"><span>公告：{h(item['announcement_date'])}</span><span>生效：{effective}</span></div>
      <p><strong>本週變化：</strong>{h(item['summary'])}</p><p><strong>為何重要：</strong>{h(item['importance'])}</p>
      {extra}<p><strong>臺灣實務影響：</strong>{h(item['taiwan_impact'])}</p>
      <p><strong>原始來源：</strong><a href="{h(item['source_url'])}" target="_blank" rel="noopener noreferrer">{h(item['source_title'])}</a></p></article>'''

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument('--input',default='data/weekly_updates.json')
    cli.add_argument('--site-dir',default='.')
    cli.add_argument('--week-ending',help='YYYY-MM-DD, inclusive; default: today Asia/Taipei')
    args=cli.parse_args()
    end=date.fromisoformat(args.week_ending) if args.week_ending else datetime.now(ZoneInfo('Asia/Taipei')).date()
    start=end-timedelta(days=6)
    data=json.loads(Path(args.input).read_text(encoding='utf-8-sig'))
    items=verify(data,start,end)
    site=Path(args.site_dir).resolve()
    reports=site/'reports'
    reports.mkdir(parents=True,exist_ok=True)
    name=f'{end.isoformat()}.html'
    cards=''.join(render_item(i) for i in items)
    if not cards:
        cards='<section class="panel"><h2>本週無重大更新</h2><p>在本期資料審核範圍內，未收錄符合條件的重大政策更新。這不等於宣稱所有官方機關均無公告。</p></section>'
    intro=f'<h2>每週政策週報｜{start.isoformat()} 至 {end.isoformat()}</h2><p class="muted">收錄 {len(items)} 項經人工確認的政策動態。以公告日期歸入本週，並分列生效日期。</p>'
    intro += '<div class="panel"><strong>重要提醒：</strong>本頁由人工審閱的 JSON 產生；程式不會自行核實政策狀態或來源真偽。</div>'
    if data.get('learning_note'):
        note=data['learning_note']
        intro+=f'<section class="panel"><h2>本期基礎學習</h2><p>{h(note)}</p></section>'
    if data.get('question'):
        cards+=f'<section class="panel"><h2>思考題</h2><p>{h(data["question"])}</p></section>'
    report=reports/name
    report.write_text(page('ESG 週報 '+end.isoformat(),intro+cards),encoding='utf-8')
    dates=[]
    for file in reports.glob('????-??-??.html'):
        try: dates.append(date.fromisoformat(file.stem))
        except ValueError: continue
    dates.sort(reverse=True)
    links=''.join(f'<li><a href="{d.isoformat()}.html">{d.isoformat()} ESG／GHG／MRV 週報</a></li>' for d in dates)
    reports.joinpath('index.html').write_text(page('ESG 歷史週報',f'<h2>歷史週報</h2><div class="panel"><ul>{links}</ul></div>'),encoding='utf-8')
    print(f'OK: {report} | total {len(items)} | history {len(dates)}')
    print('注意：不會覆寫網站首頁 index.html；需另行加入 reports/index.html 連結。')

if __name__=='__main__':main()
