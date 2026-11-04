#!/usr/bin/env python3
"""Free official-source collection. Classification is a hint, never legal verification."""
import argparse
import hashlib
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from urllib.request import Request, urlopen

SOURCES = [
    ('fsc', '金管會新聞稿', 'https://www.fsc.gov.tw/RSS/Messages?serno=201202290009&language=chinese', 'rss'),
    ('fsc-law', '金管會法令函釋', 'https://www.fsc.gov.tw/RSS/Newlaw?serno=201202290008&language=chinese', 'rss'),
    ('moenv', '環境部新聞發布', 'https://www.moenv.gov.tw/press/press-releases/2626.html', 'html'),
]
KEYWORDS = re.compile(r'ESG|GHG|MRV|IFRS\s*S[12]|永續|溫室氣體|碳費|碳權|碳盤查|減碳|淨零|氣候|排放|查驗|碳封存', re.I)
HOSTS = {'www.fsc.gov.tw', 'www.moenv.gov.tw', 'enews.moenv.gov.tw'}

def official(url):
    p = urlparse(url)
    return p.scheme == 'https' and p.hostname in HOSTS and not p.username and not p.password and p.port in (None, 443)

def canonical(url):
    p = urlparse(html.unescape(url.strip()))
    q = [(k,v) for k,v in parse_qsl(p.query) if not k.lower().startswith('utm_') and k != 'toolsflag']
    return urlunparse((p.scheme, p.netloc, p.path, '', urlencode(sorted(q)), ''))

class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.hidden = max(0, self.hidden-1)
    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)

def plain(value):
    p = Text(); p.feed(value)
    return ' '.join(' '.join(p.parts).split())

def parse_date(value):
    try: return parsedate_to_datetime(value).astimezone(timezone(timedelta(hours=8))).date()
    except (ValueError, TypeError):
        m = re.search(r'(\d{3,4})[-/年](\d{1,2})[-/月](\d{1,2})', value)
        if not m: raise ValueError('missing publication date')
        y,mn,d = map(int,m.groups())
        return date(y+1911 if y<1911 else y,mn,d)

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]; self.current=None
    def handle_starttag(self, tag, attrs):
        if tag=='a': self.current=[dict(attrs).get('href',''), []]
    def handle_data(self, data):
        if self.current: self.current[1].append(data)
    def handle_endtag(self, tag):
        if tag=='a' and self.current:
            self.links.append((self.current[0], ' '.join(self.current[1]))); self.current=None

def parse_source(raw, kind):
    if kind=='rss':
        root=ET.fromstring(raw)
        entries=root.findall('.//item')
        if not entries: raise ValueError('feed has no items; possible schema change')
        return [(e.findtext('title',''),e.findtext('link',''),e.findtext('pubDate',''),e.findtext('description','')) for e in entries]
    p=Links(); p.feed(raw.decode('utf-8-sig'))
    entries=[(re.sub(r'\s*\d{3,4}-\d{2}-\d{2}\s*$', '', t),u,t,'') for u,t in p.links if 'enews.moenv.gov.tw' in u and re.search(r'\d{3,4}-\d{2}-\d{2}',t)]
    if not entries: raise ValueError('no dated official links; blocked or schema changed')
    return entries

def fetch(url):
    if not official(url): raise ValueError('source outside allowlist')
    for attempt in range(3):
        try:
            with urlopen(Request(url,headers={'User-Agent':'TaiwanESGWatch/1.0 (official public information)'}),timeout=30) as r:
                if not official(r.url): raise ValueError('redirect outside allowlist')
                raw=r.read(8_000_001)
                if len(raw)>8_000_000: raise ValueError('response too large')
                return raw
        except Exception:
            if attempt==2: raise
            time.sleep(attempt+1)

def collect(end, fixtures=None):
    start=end-timedelta(days=6); items={}; coverage=[]
    for key,label,url,kind in SOURCES:
        info={'id':key,'name':label,'url':url,'status':'failed'}
        try:
            raw=(Path(fixtures)/(key+'.'+('xml' if kind=='rss' else 'html'))).read_bytes() if fixtures else fetch(url)
            entries=parse_source(raw,kind); rejected=0
            for title,link,published,summary in entries:
                try:
                    day=parse_date(published); link=canonical(link)
                    if not official(link): raise ValueError('nonofficial link')
                except (ValueError, TypeError): rejected+=1; continue
                title=plain(title); summary=plain(summary)
                if not start<=day<=end or not KEYWORDS.search(title+' '+summary): continue
                ident=hashlib.sha256(link.encode()).hexdigest()[:20]
                items[ident]={'id':ident,'title':title,'announcement_date':day.isoformat(),
                    'status':'unverified','status_hint':'草案／研議線索' if re.search('草案|預告|研議',title) else '待人工確認',
                    'source_title':label,'source_url':link,'summary':summary[:600] or title,
                    'importance':'依 ESG／GHG／MRV 關鍵字自動篩選；不代表重大政策判定。',
                    'taiwan_impact':'適用對象、義務及政策狀態請參閱原文並人工確認。',
                    'effective_date':None,'reviewed':False}
            info.update(status='ok',entries=len(entries),rejected=rejected,sha256=hashlib.sha256(raw).hexdigest())
        except Exception as exc: info['error']=f'{type(exc).__name__}: {exc}'
        coverage.append(info)
    return {'week_ending':end.isoformat(),'mode':'automated','items':sorted(items.values(),key=lambda x:(x['announcement_date'],x['id']),reverse=True),'coverage':coverage,
        'learning_note':'GHG 為溫室氣體；MRV 為監測、報告與查證。自動篩選不等於政策查證。'}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--week-ending'); p.add_argument('--output',default='data/weekly_updates.json'); p.add_argument('--fixtures')
    a=p.parse_args(); end=date.fromisoformat(a.week_ending) if a.week_ending else datetime.now(timezone(timedelta(hours=8))).date()
    data=collect(end,a.fixtures)
    target=Path(a.output); target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'items':len(data['items']),'coverage':data['coverage']},ensure_ascii=False))
    if not any(s['status']=='ok' for s in data['coverage']): raise SystemExit('All sources failed; publication stopped')

if __name__=='__main__': main()
