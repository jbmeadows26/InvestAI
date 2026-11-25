import unittest
from datetime import date,timedelta
from engine import parse,validate,forecast
XML=b'<root xmlns:m="urn:m" xmlns:d="urn:d"><m:properties><d:NEW_DATE>2026-11-24T00:00:00</d:NEW_DATE><d:BC_10YEAR>4.91</d:BC_10YEAR><d:BC_2YEAR>4.63</d:BC_2YEAR></m:properties></root>'
class Test(unittest.TestCase):
 def test_parse(self): self.assertEqual(parse(XML)[0]['y10'],4.91)
 def test_empty(self):
  with self.assertRaises(ValueError): parse(b'<root/>')
 def test_duplicate(self):
  with self.assertRaises(ValueError): validate(parse(XML)*2,date(2026,11,25))
 def test_stale(self):
  with self.assertRaises(ValueError): validate(parse(XML),date(2026,12,4))
 def test_future(self):
  with self.assertRaises(ValueError): validate(parse(XML),date(2026,11,23))
 def test_nonfinite(self):
  r=parse(XML);r[0]['y10']=float('nan')
  with self.assertRaises(ValueError): validate(r,date(2026,11,25))
 def test_small(self): self.assertEqual(forecast(parse(XML))['status'],'withheld')
 def test_no_skill(self):
  r=[{'date':str(date(2024,1,1)+timedelta(days=i)),'y10':4.,'y2':3.} for i in range(600)]
  self.assertEqual(forecast(r)['status'],'withheld')
if __name__=='__main__': unittest.main()
