import frappe
from frappe.tests import IntegrationTestCase

from erpnext_sverige.tests.frakt_utils import make_eur_pall, make_frakt_item


class TestArtikelvalidering(IntegrationTestCase):
	def test_pallplatser_fyller_flakmeter(self):
		item = make_frakt_item(
			"_Test Frakt Maskin",
			fraktsatt="Egna mått",
			frakt_pallplatser=2,
			frakt_kollityp="Pall",
			frakt_langd_cm=240,
			frakt_bredd_cm=80,
			frakt_hojd_cm=150,
			weight_per_unit=400,
		)
		self.assertAlmostEqual(frappe.db.get_value("Item", item, "frakt_flakmeter"), 0.8)

	def test_forpackning_kraver_antal_per_forpackning(self):
		self.assertRaises(
			frappe.ValidationError,
			make_frakt_item,
			"_Test Frakt Utan Antal",
			fraktsatt="Förpackning",
			forpackningstyp=make_eur_pall(),
			antal_per_forpackning=0,
		)
