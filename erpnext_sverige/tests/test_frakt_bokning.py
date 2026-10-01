from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from erpnext_sverige.frakt import FraktFel, bokning
from erpnext_sverige.tests.frakt_utils import (
	aktivera_frakt,
	make_eur_pall,
	make_foljesedel,
	make_frakt_item,
	make_kund_med_adress,
)

SENDIFY = "erpnext_sverige.frakt.sendify"


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
		frappe.db.set_value("Customer", self.kund, "forvald_fraktprodukt", None)

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


PRISER = [
	{
		"token": "T-DHL",
		"transportorskod": "dhl",
		"transportor": "_Test DHL",
		"produkt": "Pall",
		"pris": 900.0,
		"valuta": "SEK",
		"dagar_min": 2,
		"dagar_max": 3,
		"upphamtning": {},
		"leverans": {},
		"giltig_till": "2099-01-01T00:00:00Z",
	},
	{
		"token": "T-DSV",
		"transportorskod": "dsv",
		"transportor": "_Test DSV",
		"produkt": "Pall",
		"pris": 800.0,
		"valuta": "SEK",
		"dagar_min": 1,
		"dagar_max": 2,
		"upphamtning": {},
		"leverans": {},
		"giltig_till": "2099-01-01T00:00:00Z",
	},
]


def _fraktprodukt(transportor):
	frappe.get_doc({"doctype": "Fraktprodukt", "transportor": transportor, "produkt": "Pall"}).insert(
		ignore_if_duplicate=True
	)


class TestPriser(FraktTestCase):
	def _priser(self):
		return patch(
			f"{SENDIFY}.hamta_priser", return_value=([dict(p) for p in PRISER], ["UPS: Name too long"])
		)

	def test_hamta_priser_skapar_sandning_och_sorterar(self):
		doc, _dn = self.shipment()
		with patch(f"{SENDIFY}.skapa_sandning", return_value="S1") as skapa, self._priser():
			svar = bokning.hamta_priser(doc.name)
		self.assertEqual(skapa.call_args.args[0]["referens_id"], doc.name)
		self.assertEqual(frappe.db.get_value("Shipment", doc.name, "sendify_id"), "S1")
		self.assertEqual([p["token"] for p in svar["priser"]], ["T-DSV", "T-DHL"])
		self.assertEqual(svar["priser"][0]["kundpris"], 900)  # 800 * 1,1 + 20
		self.assertEqual(svar["varningar"], ["UPS: Name too long"])

	def test_andra_prisforfragan_uppdaterar_sandningen(self):
		doc, _dn = self.shipment()
		frappe.db.set_value("Shipment", doc.name, "sendify_id", "S1")
		with (
			patch(f"{SENDIFY}.skapa_sandning") as skapa,
			patch(f"{SENDIFY}.uppdatera_sandning") as uppdatera,
			patch(f"{SENDIFY}.hamta_priser", return_value=([dict(p) for p in PRISER], [])),
		):
			bokning.hamta_priser(doc.name)
		skapa.assert_not_called()
		self.assertEqual(uppdatera.call_args.args[0], "S1")

	def test_forvald_produkt_markeras(self):
		doc, _dn = self.shipment()
		_fraktprodukt("_Test DHL")
		frappe.db.set_value("Shipment", doc.name, "fraktprodukt", "_Test DHL – Pall")
		with (
			patch(f"{SENDIFY}.skapa_sandning", return_value="S1"),
			patch(f"{SENDIFY}.hamta_priser", return_value=([dict(p) for p in PRISER], [])),
		):
			svar = bokning.hamta_priser(doc.name)
		self.assertEqual([p["forvald"] for p in svar["priser"]], [False, True])

	def test_hamta_priser_visar_sendifys_faltfel(self):
		doc, _dn = self.shipment()
		fel = FraktFel(
			"Sendify kunde inte behandla sändningen", falt_fel=["Mottagare: e-post: The field is required."]
		)
		with patch(f"{SENDIFY}.skapa_sandning", side_effect=fel):
			with self.assertRaises(frappe.ValidationError) as undantag:
				bokning.hamta_priser(doc.name)
		self.assertIn("Mottagare: e-post", str(undantag.exception))

	def test_spara_val(self):
		doc, _dn = self.shipment()
		_fraktprodukt("_Test DSV")
		bokning.spara_val(doc.name, "_Test DSV – Pall", 800, "SEK")
		doc.reload()
		self.assertEqual(
			(doc.fraktprodukt, doc.fraktpris, doc.kundpris, doc.docstatus), ("_Test DSV – Pall", 800, 900, 0)
		)
		self.assertTrue(doc.pris_hamtat)
