import frappe
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

from erpnext_sverige.frakt import bokning
from erpnext_sverige.tests.test_frakt_bokning import FraktTestCase, mockad_sendify


class TestFraktPaFaktura(FraktTestCase):
	def bokad_foljesedel(self):
		doc, dn = self.shipment()
		with mockad_sendify():
			bokning.hamta_priser(doc.name)
			bokning.boka(doc.name, "T-DSV", "_Test DSV – Pall", 800)
		return doc.name, dn

	def fraktrader(self, faktura):
		konto = frappe.db.get_single_value("Fraktinstallningar", "fraktkonto")
		return [t for t in faktura.taxes if t.account_head == konto]

	def test_faktura_far_fraktrad_med_kundpris(self):
		shipment, dn = self.bokad_foljesedel()
		faktura = make_sales_invoice(dn.name)
		faktura.insert()
		rader = self.fraktrader(faktura)
		self.assertEqual(len(rader), 1)
		self.assertEqual((rader[0].charge_type, rader[0].tax_amount), ("Actual", 900))
		self.assertIn(f"({shipment})", rader[0].description)

	def test_andrat_kundpris_anvands(self):
		shipment, dn = self.bokad_foljesedel()
		frappe.db.set_value("Shipment", shipment, "kundpris", 750)
		faktura = make_sales_invoice(dn.name)
		faktura.insert()
		self.assertEqual(self.fraktrader(faktura)[0].tax_amount, 750)

	def test_frakt_laggs_bara_pa_forsta_fakturan(self):
		_shipment, dn = self.bokad_foljesedel()
		forsta = make_sales_invoice(dn.name)
		forsta.items[0].qty = 50
		forsta.insert()
		andra = make_sales_invoice(dn.name)
		andra.insert()
		self.assertEqual(len(self.fraktrader(forsta)), 1)
		self.assertEqual(len(self.fraktrader(andra)), 0)

	def test_ingen_dubbel_frakt_om_fakturan_redan_har_fraktrad(self):
		_shipment, dn = self.bokad_foljesedel()
		faktura = make_sales_invoice(dn.name)
		konto = frappe.db.get_single_value("Fraktinstallningar", "fraktkonto")
		faktura.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": konto,
				"description": "Frakt",
				"tax_amount": 100,
				"cost_center": frappe.db.get_value("Company", faktura.company, "cost_center"),
			},
		)
		faktura.insert()
		self.assertEqual([t.tax_amount for t in self.fraktrader(faktura)], [100])

	def test_obokad_shipment_ger_ingen_frakt(self):
		_doc, dn = self.shipment()
		faktura = make_sales_invoice(dn.name)
		faktura.insert()
		self.assertEqual(self.fraktrader(faktura), [])
