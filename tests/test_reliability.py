import unittest
from app.sources.ibbi import SourceSchemaError, parse_resolution_page

GOOD = '''
<html><body><table>
<tr><th>Name of Corporate Debtor</th><th>Name of Resolution Professional</th><th>Last date for receipt of expression of interest</th><th>Date of issue of prospective resolution applicants</th><th>Last date for submission of objections to provisional lists</th><th>Form G</th><th>Remarks</th></tr>
<tr><td>ABC PRIVATE LIMITED</td><td>RP</td><td>12th October, 2026</td><td>20th October, 2026</td><td>25th October, 2026</td><td><a href="/x.pdf">PDF</a></td><td></td></tr>
</table><div>Total Records :3754</div></body></html>
'''

class ReliabilityTests(unittest.TestCase):
    def test_expected_schema_parses(self):
        rows,total=parse_resolution_page(GOOD,'https://ibbi.gov.in/resolution-plans',0)
        self.assertEqual(total,3754)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0].eoi_deadline.isoformat(),'2026-10-12')

    def test_schema_break_fails_loudly(self):
        with self.assertRaises(SourceSchemaError):
            parse_resolution_page('<html><table><tr><td>oops</td></tr></table></html>','x',0)

if __name__=='__main__':
    unittest.main()
