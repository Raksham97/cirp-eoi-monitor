import unittest
from pathlib import Path
from app.sources.ibbi import parse_resolution_page

class ParserTests(unittest.TestCase):
    def test_parse(self):
        html=Path('tests/fixtures/ibbi_page.html').read_text()
        rows,total=parse_resolution_page(html,'https://ibbi.gov.in/resolution-plans?page=1',1)
        self.assertEqual(total,3756)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0].debtor_name,'JRA INFRASTRUCTURE LIMITED')
        self.assertEqual(rows[0].eoi_deadline.isoformat(),'2026-03-04')
        self.assertTrue(rows[0].form_g_url.endswith('/uploads/resolution_plan/jra.pdf'))

if __name__=='__main__': unittest.main()
