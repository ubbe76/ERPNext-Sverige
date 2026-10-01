from datetime import date, datetime

import frappe
from frappe.tests import IntegrationTestCase

from erpnext_sverige.frakt import fraktpris, parter
from erpnext_sverige.tests.frakt_utils import aktivera_frakt, make_kund_med_adress


class TestFraktpris(IntegrationTestCase):
	def setUp(self):
		self.inst = aktivera_frakt()

	def test_kundpris_med_paslag_avrundas_till_hela_kronor(self):
		self.assertEqual(fraktpris.kundpris(127), 160)  # 127 * 1,10 + 20 = 159,7

	def test_registrera_produkter_skapar_fraktprodukt_en_gang(self):
		priser = [
			{"transportorskod": "ups_se", "transportor": "_Test UPS", "produkt": "Standard", "pris": 200.0},
			{"transportorskod": "dhl_se", "transportor": "_Test DHL", "produkt": "Paket", "pris": 100.0},
		]
		resultat = fraktpris.registrera_produkter(priser)
		self.assertEqual([p["fraktprodukt"] for p in resultat], ["_Test DHL – Paket", "_Test UPS – Standard"])
		self.assertEqual(resultat[0]["kundpris"], 130)
		fraktpris.registrera_produkter(priser)
		self.assertEqual(frappe.db.count("Fraktprodukt", {"transportor": "_Test UPS"}), 1)

	def test_part_fran_adress_och_kontakt(self):
		kund = make_kund_med_adress()
		adress = frappe.db.get_value("Address", {"address_title": f"{kund} leverans"})
		kontakt = frappe.db.get_value("Contact", {"first_name": f"{kund} kontakt"})
		p = parter.part("Kund AB", adress, kontakt, privatperson=False)
		self.assertEqual(
			{k: p[k] for k in ("namn", "adressrad_1", "postnummer", "ort", "landskod", "telefon", "epost")},
			{
				"namn": "Kund AB",
				"adressrad_1": "Testgatan 1",
				"postnummer": "41107",
				"ort": "Göteborg",
				"landskod": "SE",
				"telefon": "0701234567",
				"epost": "test@example.com",
			},
		)

	def test_nasta_arbetsdag_hoppar_over_helg(self):
		self.assertEqual(parter.nasta_arbetsdag(date(2026, 10, 2)), date(2026, 10, 5))  # fredag → måndag
		self.assertEqual(parter.nasta_arbetsdag(date(2026, 10, 5)), date(2026, 10, 6))

	def test_upphamtningstid(self):
		self.assertEqual(parter.upphamtningstid("2026-10-05", "09:30:00"), datetime(2026, 10, 5, 9, 30))
