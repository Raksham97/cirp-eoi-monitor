import unittest
from app.classifier import classify


class ClassifierTests(unittest.TestCase):
    def test_toll_road_precedence(self):
        c = classify('JRA Infrastructure Limited', 'construction of bridges, roads and public utility projects')
        self.assertEqual(c.industry, 'Roads / Toll Roads')
        self.assertGreaterEqual(c.confidence, 0.9)

    def test_plain_address_road_does_not_force_toll_road(self):
        c = classify('A.P.J. LABORATORIES LIMITED', 'land at Village Ambwala, Nwada Road, Paonta Sahib')
        self.assertEqual(c.industry, 'Pharma / Healthcare')

    def test_hospitality(self):
        self.assertEqual(classify('Majestic Hotels Limited').industry, 'Hotel / Hospitality')

    def test_new_obvious_sectors(self):
        self.assertEqual(classify('Saarthi Pedagogy Private Limited').industry, 'Education')
        self.assertEqual(classify('Truweight Wellness Private Limited').industry, 'Pharma / Healthcare')
        self.assertEqual(classify('Alvi Tech Services Pvt Ltd').industry, 'IT / Technology')
        self.assertEqual(classify('Shree Shiddhanath Cotex Private Limited').industry, 'Textiles')
        self.assertEqual(classify('Margdarshak Financial Services Limited').industry, 'Financial Services')
        self.assertEqual(classify('Comet Granito Private Limited').industry, 'Cement / Building Materials')
        self.assertEqual(classify('Bhubaneshwari Seafood Private Limited').industry, 'Agriculture / Food')
        self.assertEqual(classify('Log 9 Materials Scientific Private Limited', 'battery production capacity').industry, 'Power / Energy')

    def test_unclear_is_review(self):
        c = classify('ABC Ventures Private Limited')
        self.assertEqual(c.industry, 'Other / Unclear')
        self.assertLess(c.confidence, 0.8)


if __name__ == '__main__':
    unittest.main()
