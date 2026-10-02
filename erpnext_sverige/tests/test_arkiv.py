import os
import tempfile

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate, today

from erpnext_sverige.arkiv import skriv_sie_filer
from erpnext_sverige.tests.utils import COMPANY, ensure_test_company


class TestArkiv(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()

	def test_writes_sie_file_per_company(self):
		year = getdate(today()).year
		with tempfile.TemporaryDirectory() as katalog:
			paths = skriv_sie_filer(katalog, year)
			ours = [p for p in paths if os.path.basename(p).startswith(frappe.scrub(COMPANY))]
			self.assertEqual(len(ours), 1, paths)
			with open(ours[0], "rb") as f:
				content = f.read()
			self.assertTrue(content.startswith(b"#FLAGGA 0"), content[:40])
			self.assertIn(b"#SIETYP 4", content)

	def test_no_fiscal_year_gives_no_files(self):
		with tempfile.TemporaryDirectory() as katalog:
			self.assertEqual(skriv_sie_filer(katalog, 1990), [])
