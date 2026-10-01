import frappe
from frappe.tests import IntegrationTestCase

from erpnext_sverige.frakt import FraktFel, hamta_installningar, visa_fraktfel


class TestFraktDoctypes(IntegrationTestCase):
	def test_fraktprodukt_namnges_efter_transportor_och_produkt(self):
		doc = frappe.get_doc(
			{"doctype": "Fraktprodukt", "transportor": "_Test Frakt AB", "produkt": "Paket Express"}
		).insert()
		self.assertEqual(doc.name, "_Test Frakt AB – Paket Express")

	def test_forpackningstyp_kraver_matt(self):
		doc = frappe.get_doc(
			{
				"doctype": "Forpackningstyp",
				"forpackningstyp_namn": "_Test noll",
				"langd_cm": 0,
				"bredd_cm": 80,
				"hojd_cm": 100,
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_inaktiverade_installningar_ger_fel(self):
		frappe.db.set_single_value("Fraktinstallningar", "aktiverad", 0)
		frappe.clear_document_cache("Fraktinstallningar", "Fraktinstallningar")
		self.assertRaises(frappe.ValidationError, hamta_installningar)

	def test_visa_fraktfel_blir_valideringsfel_med_faltlista(self):
		@visa_fraktfel
		def misslyckas():
			raise FraktFel(
				"Ogiltig sändning", falt_fel=["Kolli 1: vikt: The field is required."], request_id="abc"
			)

		with self.assertRaises(frappe.ValidationError) as fel:
			misslyckas()
		self.assertIn("Kolli 1: vikt", str(fel.exception))
		self.assertIn("abc", str(fel.exception))
