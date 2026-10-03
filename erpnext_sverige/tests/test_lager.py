"""ERPNext:s standardlager Stores heter Lager (inte Butiker) och befintliga lager döps om."""

import frappe
from frappe.tests import IntegrationTestCase

from erpnext_sverige.patches import lager_i_stallet_for_butiker
from erpnext_sverige.tests.utils import COMPANY, COMPANY_ABBR, ensure_test_company


class TestLager(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()

	def tearDown(self):
		frappe.db.rollback()
		frappe.local.lang = "en"

	def test_oversattning(self):
		# ERPNext letar upp standardlagret med det översatta namnet (_("Stores"))
		frappe.local.lang = "sv"
		self.assertEqual(frappe._("Stores"), "Lager")

	def lager(self, namn):
		if not frappe.db.exists("Warehouse", f"{namn} - {COMPANY_ABBR}"):
			frappe.get_doc(
				{"doctype": "Warehouse", "warehouse_name": namn, "company": COMPANY, "is_group": 0}
			).insert()
		return f"{namn} - {COMPANY_ABBR}"

	def test_patchen_dope_om_butiker(self):
		butiker = self.lager("Butiker")
		frappe.db.set_single_value("Stock Settings", "default_warehouse", butiker)
		lager_i_stallet_for_butiker.execute()
		ny = f"Lager - {COMPANY_ABBR}"
		self.assertFalse(frappe.db.exists("Warehouse", butiker))
		self.assertEqual(frappe.db.get_value("Warehouse", ny, "warehouse_name"), "Lager")
		self.assertEqual(frappe.db.get_single_value("Stock Settings", "default_warehouse"), ny)

	def test_patchen_hoppar_over_om_lager_finns(self):
		butiker, lager = self.lager("Butiker"), self.lager("Lager")
		lager_i_stallet_for_butiker.execute()
		self.assertTrue(frappe.db.exists("Warehouse", butiker))
		self.assertTrue(frappe.db.exists("Warehouse", lager))
