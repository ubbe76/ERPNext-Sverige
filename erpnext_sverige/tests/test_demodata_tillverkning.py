"""Testdatan för tillverkning: stycklistor med material och arbete, parter och ingående lager."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from erpnext_sverige.scripts import demodata_tillverkning as demo
from erpnext_sverige.tests.utils import COMPANY, ensure_test_company


class TestDemodataTillverkning(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		cls.skapat = demo.skapa(COMPANY)

	def test_stycklistor_med_material_och_arbete(self):
		for kod in demo.STYCKLISTOR:
			bom = frappe.get_doc(
				"BOM", frappe.db.get_value("BOM", {"item": kod, "docstatus": 1, "is_default": 1})
			)
			self.assertTrue(bom.operations, kod)
			self.assertGreater(bom.raw_material_cost, 0, kod)
			self.assertGreater(bom.operating_cost, 0, kod)

	def test_produktens_kostnad_inkluderar_halvfabrikat(self):
		bom = frappe.get_doc("BOM", frappe.db.get_value("BOM", {"item": "LH-900", "docstatus": 1}))
		gavel = next(r for r in bom.items if r.item_code == "HF-GAVEL-1800")
		self.assertGreater(gavel.rate, 0)

	def test_ingaende_lager(self):
		lager = demo._lager(COMPANY)["ravaror"]
		self.assertEqual(
			frappe.db.get_value("Bin", {"item_code": "RM-PLAT-15", "warehouse": lager}, "actual_qty"), 1500
		)

	def test_parter_med_momskategori(self):
		self.assertEqual(frappe.db.get_value("Customer", "Værkstedsudstyr Jensen ApS", "tax_category"), "EU")
		self.assertEqual(
			frappe.db.get_value("Supplier", "Pulverfärg Norden AB", "tax_category"), "Svensk moms"
		)

	def test_kan_koras_igen(self):
		self.assertEqual(set(demo.skapa(COMPANY).values()), {0})

	def test_bara_pa_testsajter(self):
		with patch.dict(frappe.local.conf, {"allow_tests": 0}):
			self.assertRaisesRegex(frappe.ValidationError, "allow_tests", demo.skapa, COMPANY)
