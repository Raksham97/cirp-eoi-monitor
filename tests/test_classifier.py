import unittest
from app.classifier import classify

class ClassifierTests(unittest.TestCase):
    def test_toll_road_precedence(self):
        c=classify('JRA Infrastructure Limited','construction of bridges, roads and public utility projects')
        self.assertEqual(c.industry,'Roads / Toll Roads')
        self.assertGreaterEqual(c.confidence,0.9)
    def test_hospitality(self):
        self.assertEqual(classify('Majestic Hotels Limited').industry,'Hotel / Hospitality')
    def test_unclear_is_review(self):
        c=classify('ABC Trading Private Limited')
        self.assertEqual(c.industry,'Other / Unclear')
        self.assertLess(c.confidence,0.8)

if __name__=='__main__': unittest.main()
