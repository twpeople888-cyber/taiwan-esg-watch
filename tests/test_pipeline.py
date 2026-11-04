import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import collect_esg as c
import build_esg as b

RSS=b'''<rss><channel><item><title>ESG draft</title><link>https://www.fsc.gov.tw/news?id=1</link><pubDate>Fri, 30 Oct 2026 00:00:00 GMT</pubDate><description>&lt;script&gt;bad&lt;/script&gt;GHG</description></item><item><title>ESG old</title><link>https://www.fsc.gov.tw/old</link><pubDate>Fri, 01 Jan 2021 00:00:00 GMT</pubDate></item></channel></rss>'''

class Pipeline(unittest.TestCase):
    def data(self):
        with patch.object(c,'fetch',side_effect=[RSS,RSS,ValueError('blocked')]):
            return c.collect(date(2026,10,30))
    def test_partial_failure_dates_dedup(self):
        d=self.data(); self.assertEqual(len(d['items']),1)
        self.assertEqual(d['coverage'][2]['status'],'failed')
        self.assertNotIn('bad',d['items'][0]['summary'])
        self.assertEqual(d['items'][0]['status'],'unverified')
    def test_all_failed(self):
        with patch.object(c,'fetch',side_effect=ValueError('offline')):
            d=c.collect(date(2026,10,30))
        self.assertTrue(all(s['status']=='failed' for s in d['coverage']))
    def test_authority_and_dates(self):
        self.assertFalse(c.official('https://www.fsc.gov.tw.evil.com/x'))
        self.assertFalse(c.official('http://www.fsc.gov.tw/x'))
        self.assertEqual(c.parse_date('115-10-30'),date(2026,10,30))
        d=self.data(); item=d['items'][0]
        for changes in ({'announcement_date':'2026-11-01'}, {'status':'effective'}, {'source_url':'https://evil.com'}):
            bad=copy.deepcopy(d); bad['items'][0].update(changes)
            with self.assertRaises(ValueError): b.verify(bad,date(2026,10,24),date(2026,10,30))
        item.update(status='effective',reviewed=True,effective_date='2026-11-01')
        with self.assertRaises(ValueError): b.verify(d,date(2026,10,24),date(2026,10,30))
    def test_html_parser(self):
        rows=c.parse_source('<a href="https://enews.moenv.gov.tw/a">碳費 115-10-30</a>'.encode(),'html')
        self.assertEqual(len(rows),1)
        with self.assertRaises(ValueError): c.parse_source(b'Just a moment','html')
    def test_supplement_window_and_dedup(self):
        with tempfile.TemporaryDirectory() as t:
            source=Path(t)/'manual.json'
            item=dict(self.data()['items'][0],title='Supplement')
            source.write_text(json.dumps({'collection_method':'Official web supplement','items':[item,dict(item,announcement_date='2020-01-01')]}),encoding='utf-8')
            merged=c.merge_manual(self.data(),source)
            self.assertEqual(len(merged['items']),1)
            self.assertEqual(merged['items'][0]['title'],'Supplement')
            self.assertFalse(merged['items'][0]['reviewed'])
            self.assertEqual(merged['coverage'][2]['status'],'failed')
            item['source_url']='https://evil.com'
            source.write_text(json.dumps({'collection_method':'test','items':[item]}),encoding='utf-8')
            with self.assertRaises(ValueError): c.merge_manual(self.data(),source)
    def test_refresh_dashboard_and_revision(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t); (p/'index.html').write_text('green header<!-- ESG-DASHBOARD:START --><!-- ESG-DASHBOARD:END -->learning footer')
            source=p/'input.json'; data=self.data()
            source.write_text(json.dumps(data),encoding='utf-8')
            cmd=[sys.executable,str(ROOT/'scripts/build_esg.py'),'--input',str(source),'--site-dir',t,'--week-ending','2026-10-30']
            subprocess.run(cmd,check=True,capture_output=True)
            before=(p/'reports/2026-10-30.html').read_bytes()
            data['items'][0]['title']='New supplement'
            source.write_text(json.dumps(data),encoding='utf-8')
            subprocess.run(cmd+['--replace-existing'],check=True,capture_output=True)
            self.assertIn('New supplement',(p/'index.html').read_text(encoding='utf-8'))
            self.assertTrue((p/'index.html').read_text(encoding='utf-8').startswith('green header'))
            backups=list((p/'reports/revisions/2026-10-30').glob('*.html'))
            self.assertEqual(len(backups),1)
            self.assertEqual(backups[0].read_bytes(),before)
            self.assertEqual((p/'reports/latest.html').read_bytes(),(p/'reports/2026-10-30.html').read_bytes())
    def test_end_to_end_local_and_rerun(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t); (p/'index.html').write_text('original green homepage')
            source=p/'input.json'; source.write_text(json.dumps(self.data()),encoding='utf-8')
            cmd=[sys.executable,str(ROOT/'scripts/build_esg.py'),'--input',str(source),'--site-dir',t,'--week-ending','2026-10-30']
            subprocess.run(cmd,check=True,capture_output=True)
            report=p/'reports/2026-10-30.html'; before=report.read_bytes()
            self.assertIn('待確認',before.decode()); self.assertIn('blocked',before.decode())
            self.assertIn('2026-10-30.html',(p/'reports/index.html').read_text(encoding='utf-8'))
            subprocess.run(cmd,check=True,capture_output=True)
            self.assertEqual(before,report.read_bytes())
            self.assertEqual((p/'index.html').read_text(),'original green homepage')
            self.assertTrue((p/'reports/2026-10-30.json').exists())

if __name__=='__main__': unittest.main()
