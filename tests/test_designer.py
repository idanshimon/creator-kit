import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
from creator_tools import designer
class DesignerTests(unittest.TestCase):
 def test_no_consent_before_inference(self):
  with patch('creator_tools.models.request_json') as call:
   with self.assertRaises(ValueError): designer.review({},'x','brief',[],'out.json',False)
   call.assert_not_called()
 def test_reject_nonimage(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'bad.png';p.write_text('not image')
   with self.assertRaises(ValueError):designer.image_data(p)
 def test_validate_palette_rejects_code(self):
  bad={'variants':[{'name':'x','light':{'stable':'javascript:evil'},'dark':{'stable':'#123456'}}]*2}
  with self.assertRaises(ValueError):designer.validate_review(bad)
 def test_requires_two_variants(self):
  with self.assertRaises(ValueError):designer.validate_review({'variants':[]})
