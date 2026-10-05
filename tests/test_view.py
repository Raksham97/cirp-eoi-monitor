import unittest
from datetime import date, timedelta
from types import SimpleNamespace

from app.view import in_working_window, status_for, working_sort_key


class ViewWindowTests(unittest.TestCase):
    def n(self, days):
        return SimpleNamespace(eoi_deadline=date.today() + timedelta(days=days))

    def test_window(self):
        self.assertTrue(in_working_window(self.n(0)))
        self.assertTrue(in_working_window(self.n(30)))
        self.assertTrue(in_working_window(self.n(-10)))
        self.assertFalse(in_working_window(self.n(31)))
        self.assertFalse(in_working_window(self.n(-11)))

    def test_open_before_recently_closed(self):
        items = [self.n(-1), self.n(5), self.n(1), self.n(-2)]
        ordered = sorted(items, key=working_sort_key)
        self.assertEqual([(x.eoi_deadline - date.today()).days for x in ordered], [1, 5, -1, -2])
        self.assertEqual(status_for(self.n(0)), 'Open')
        self.assertEqual(status_for(self.n(-1)), 'Closed recently')


if __name__ == '__main__':
    unittest.main()
