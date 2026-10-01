import frappe
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
from frappe.utils import flt

from erpnext_sverige.frakt import bokning
from erpnext_sverige.setup.company import TAX_CATEGORY_EU
from erpnext_sverige.tests.frakt_utils import make_adress, make_foljesedel, make_kontakt
from erpnext_sverige.tests.test_frakt_bokning import FraktTestCase, mockad_sendify
from erpnext_sverige.tests.utils import account, make_party


class TestFraktPaFaktura(FraktTestCase):
	def bokad_foljesedel(self, kund=None):
		if kund:
			dn = make_foljesedel(kund, [(self.artikel, 100)])
			doc = frappe.get_doc("Shipment", bokning.skapa_shipment(dn.name))
		else:
			doc, dn = self.shipment()
		with mockad_sendify():
			bokning.hamta_priser(doc.name)
			bokning.boka(doc.name, "T-DSV", "_Test DSV – Pall", 800)
		return doc.name, dn

	def fraktrader(self, faktura):
		artikel = frappe.db.get_single_value("Fraktinstallningar", "fraktartikel")
		return [r for r in faktura.items if r.item_code == artikel]

	def test_faktura_far_fraktrad_med_kundpris_pa_3520_och_moms(self):
		shipment, dn = self.bokad_foljesedel()
		faktura = make_sales_invoice(dn.name)
		faktura.insert()
		rader = self.fraktrader(faktura)
		self.assertEqual(len(rader), 1)
		rad = rader[0]
		self.assertEqual((rad.qty, rad.rate, rad.amount), (1, 900, 900))
		self.assertEqual(rad.income_account, account("3520"))
		self.assertEqual(rad.frakt_shipment, shipment)
		self.assertIn("_Test DSV Pall", rad.description)
		varor = sum(r.amount for r in faktura.items if r.item_code != rad.item_code)
		self.assertEqual(flt(faktura.total_taxes_and_charges), flt((varor + 900) * 0.25))
		self.assertEqual(len([t for t in faktura.taxes if t.charge_type == "Actual"]), 0)

	def test_eu_kund_far_3108_och_ingen_moms(self):
		kund = "_Test DE Fraktkund"
		make_party("Customer", kund, TAX_CATEGORY_EU)
		make_adress(f"{kund} leverans", "Customer", kund, land="Germany")
		make_kontakt(f"{kund} kontakt", "Customer", kund)
		_shipment, dn = self.bokad_foljesedel(kund)
		faktura = make_sales_invoice(dn.name)
		faktura.insert()
		rader = self.fraktrader(faktura)
		self.assertEqual(len(rader), 1)
		self.assertEqual(rader[0].income_account, account("3108"))
		self.assertEqual(flt(faktura.total_taxes_and_charges), 0)

	def test_andrat_kundpris_anvands(self):
		shipment, dn = self.bokad_foljesedel()
		frappe.db.set_value("Shipment", shipment, "kundpris", 750)
		faktura = make_sales_invoice(dn.name)
		faktura.insert()
		self.assertEqual(self.fraktrader(faktura)[0].rate, 750)

	def test_frakt_laggs_bara_pa_forsta_fakturan(self):
		_shipment, dn = self.bokad_foljesedel()
		forsta = make_sales_invoice(dn.name)
		forsta.items[0].qty = 50
		forsta.insert()
		andra = make_sales_invoice(dn.name)
		andra.insert()
		self.assertEqual(len(self.fraktrader(forsta)), 1)
		self.assertEqual(len(self.fraktrader(andra)), 0)

	def test_makulerad_faktura_frigor_frakten(self):
		_shipment, dn = self.bokad_foljesedel()
		forsta = make_sales_invoice(dn.name)
		forsta.insert()
		forsta.submit()
		forsta.cancel()
		ny = make_sales_invoice(dn.name)
		ny.insert()
		self.assertEqual(len(self.fraktrader(ny)), 1)

	def test_ingen_dubbel_frakt_om_fakturan_redan_har_fraktartikeln(self):
		_shipment, dn = self.bokad_foljesedel()
		faktura = make_sales_invoice(dn.name)
		artikel = frappe.db.get_single_value("Fraktinstallningar", "fraktartikel")
		faktura.append("items", {"item_code": artikel, "qty": 1, "rate": 100})
		faktura.insert()
		self.assertEqual([r.rate for r in self.fraktrader(faktura)], [100])

	def test_obokad_shipment_ger_ingen_frakt(self):
		_doc, dn = self.shipment()
		faktura = make_sales_invoice(dn.name)
		faktura.insert()
		self.assertEqual(self.fraktrader(faktura), [])
