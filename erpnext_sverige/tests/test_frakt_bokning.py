import frappe
from frappe.tests import IntegrationTestCase

from erpnext_sverige.frakt import bokning
from erpnext_sverige.tests.frakt_utils import (
	aktivera_frakt,
	make_eur_pall,
	make_foljesedel,
	make_frakt_item,
	make_kund_med_adress,
)


class FraktTestCase(IntegrationTestCase):
	def setUp(self):
		aktivera_frakt()
		self.kund = make_kund_med_adress()
		self.pall = make_eur_pall()
		self.artikel = make_frakt_item(
			"_Test Frakt Pallvara",
			fraktsatt="Förpackning",
			forpackningstyp=self.pall,
			antal_per_forpackning=40,
			weight_per_unit=2,
			uoms=[("Box", 10)],
		)

	def shipment(self, rader=None, **dn_falt):
		dn = make_foljesedel(self.kund, rader or [(self.artikel, 100)], **dn_falt)
		return frappe.get_doc("Shipment", bokning.skapa_shipment(dn.name)), dn


class TestSkapaShipment(FraktTestCase):
	def test_shipment_far_kollin_referenser_och_avsandare(self):
		doc, dn = self.shipment(po_no="KUND-PO-7")
		self.assertEqual(doc.docstatus, 0)
		self.assertEqual([r.delivery_note for r in doc.shipment_delivery_note], [dn.name])
		self.assertEqual((doc.avsandarens_referens, doc.mottagarens_referens), (dn.name, "KUND-PO-7"))
		self.assertEqual(
			doc.pickup_address_name, frappe.db.get_single_value("Fraktinstallningar", "avsandaradress")
		)
		self.assertEqual(len(doc.shipment_parcel), 1)
		p = doc.shipment_parcel[0]
		self.assertEqual((p.kollityp, p.count, p.length, p.width, p.height), ("Pall", 3, 120, 80, 150))
		self.assertGreater(doc.value_of_goods, 0)

	def test_kollin_raknas_pa_lagerantal(self):
		doc, _dn = self.shipment(rader=[(self.artikel, 8, "Box")])  # 80 st = 2 pallar
		self.assertEqual(doc.shipment_parcel[0].count, 2)

	def test_kundens_forval_forvaljs(self):
		namn = "_Test DSV – Pall"
		if frappe.db.exists("Fraktprodukt", namn):
			produkt = frappe.get_doc("Fraktprodukt", namn)
		else:
			produkt = frappe.get_doc(
				{"doctype": "Fraktprodukt", "transportor": "_Test DSV", "produkt": "Pall"}
			).insert()
		frappe.db.set_value("Customer", self.kund, "forvald_fraktprodukt", produkt.name)
		doc, _dn = self.shipment()
		self.assertEqual(doc.fraktprodukt, produkt.name)

	def test_sandning_fran_shipment(self):
		doc, dn = self.shipment()
		s = bokning.sandning_fran_shipment(doc)
		self.assertEqual(s["referens_id"], doc.name)
		self.assertEqual(s["avsandarens_referens"], dn.name)
		self.assertEqual(s["mottagare"]["namn"], self.kund)
		self.assertEqual(s["mottagare"]["landskod"], "SE")
		self.assertEqual(s["kollin"][0]["kollityp"], "Pall")
		self.assertEqual(s["kollin"][0]["antal"], 3)

	def test_foresla_kollin_igen_ersatter_tabellen(self):
		doc, _dn = self.shipment()
		doc.shipment_parcel[0].count = 9
		doc.save()
		bokning.foresla_kollin_igen(doc.name)
		doc.reload()
		self.assertEqual(doc.shipment_parcel[0].count, 3)
