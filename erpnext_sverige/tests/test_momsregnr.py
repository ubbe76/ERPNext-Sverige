"""Momsregistreringsnummer på bolaget: fylls i från organisationsnumret, kan tömmas och styr utskrifterna."""

import frappe
from frappe.tests import IntegrationTestCase

from erpnext_sverige.patches import fyll_momsregnr
from erpnext_sverige.sweden_compliance.print_context import get_print_context
from erpnext_sverige.tests.utils import COMPANY, ensure_test_company


class TestMomsregnr(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()

	def setUp(self):
		frappe.db.savepoint("momsregnr_test")
		frappe.db.set_value("Company", COMPANY, {"tax_id": "5560000000", "se_momsregnr": None})

	def tearDown(self):
		frappe.db.rollback(save_point="momsregnr_test")
		frappe.clear_document_cache("Company", COMPANY)

	def spara(self, **falt):
		doc = frappe.get_doc("Company", COMPANY)
		doc.update(falt)
		doc.save()
		return doc

	def test_fylls_i_nar_org_nr_anges(self):
		self.assertEqual(self.spara(tax_id="556000-0000").se_momsregnr, "SE556000000001")

	def test_tomt_falt_forblir_tomt(self):
		# Bolaget är inte momsregistrerat: fältet fylls inte i igen så länge organisationsnumret är oförändrat
		self.assertIsNone(self.spara(se_f_skatt=1).se_momsregnr)

	def test_normaliseras(self):
		self.assertEqual(self.spara(se_momsregnr="se 5560000000 01").se_momsregnr, "SE556000000001")

	def test_fel_format_stoppas(self):
		self.assertRaisesRegex(frappe.ValidationError, "SE följt av", self.spara, se_momsregnr="SE5560000000")

	def test_annat_org_nr_stoppas(self):
		self.assertRaisesRegex(
			frappe.ValidationError, "stämmer inte", self.spara, se_momsregnr="SE559999999901"
		)

	def test_foljer_med_nar_org_nr_andras(self):
		self.spara(tax_id="556000-0000")
		self.assertEqual(self.spara(tax_id="5569999999").se_momsregnr, "SE556999999901")

	def test_utskriften_anvander_faltet(self):
		so = frappe._dict(doctype="Purchase Order", company=COMPANY, items=[], taxes=[])
		self.assertIsNone(get_print_context(so)["vat_no"])
		frappe.db.set_value("Company", COMPANY, "se_momsregnr", "SE556000000001")
		frappe.clear_document_cache("Company", COMPANY)
		self.assertEqual(get_print_context(so)["vat_no"], "SE556000000001")

	def test_patchen_fyller_i_befintliga_bolag(self):
		fyll_momsregnr.execute()
		self.assertEqual(frappe.db.get_value("Company", COMPANY, "se_momsregnr"), "SE556000000001")
