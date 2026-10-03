import frappe
from frappe.tests import IntegrationTestCase

from erpnext_sverige.patches import (
	brevhuvud_bara_logga,
	brevhuvud_html_kalla,
	brevhuvud_loggstorlek,
	brevhuvud_relativ_logga,
)
from erpnext_sverige.setup.company import (
	ERPNEXT_LETTER_HEADS,
	LETTER_HEAD,
	TAX_CATEGORY_SE,
	create_letter_head,
)
from erpnext_sverige.setup.custom_fields import GOODS
from erpnext_sverige.tests.utils import COMPANY, ensure_test_company, make_invoice, make_item, make_party


def default_letter_head():
	return frappe.db.get_value("Letter Head", {"is_default": 1})


def make_letter_head(name, is_default=0):
	if not frappe.db.exists("Letter Head", name):
		frappe.get_doc(
			{
				"doctype": "Letter Head",
				"letter_head_name": name,
				"source": "HTML",
				"content": f"<p>{name}</p>",
			}
		).insert()
	if is_default:
		frappe.db.set_value("Letter Head", {"name": ["!=", name]}, "is_default", 0)
		frappe.db.set_value("Letter Head", name, "is_default", 1)


class TestLetterHead(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()

	def tearDown(self):
		frappe.db.rollback()
		frappe.local.lang = "en"

	def test_replaces_erpnext_default(self):
		make_letter_head(ERPNEXT_LETTER_HEADS[-1], is_default=1)
		create_letter_head()
		self.assertEqual(default_letter_head(), LETTER_HEAD)

	def test_keeps_own_default(self):
		make_letter_head("Eget brevhuvud", is_default=1)
		create_letter_head()
		self.assertEqual(default_letter_head(), "Eget brevhuvud")
		self.assertTrue(frappe.db.exists("Letter Head", LETTER_HEAD))

	def test_keeps_edited_content(self):
		create_letter_head()
		frappe.db.set_value("Letter Head", LETTER_HEAD, "content", "<p>Ändrat</p>")
		create_letter_head()
		self.assertEqual(frappe.db.get_value("Letter Head", LETTER_HEAD, "content"), "<p>Ändrat</p>")

	def test_skapas_med_html_som_kalla(self):
		# Frappes before_insert sätter källan till Bild utanför migrering; då döljs Header HTML i formuläret
		if frappe.db.exists("Letter Head", LETTER_HEAD):
			frappe.delete_doc("Letter Head", LETTER_HEAD, force=True)
		create_letter_head()
		kalla, innehall = frappe.db.get_value("Letter Head", LETTER_HEAD, ["source", "content"])
		self.assertEqual(kalla, "HTML")
		self.assertIn("company_logo", innehall)

	def test_patchen_ratter_kallan(self):
		create_letter_head()
		frappe.db.set_value("Letter Head", LETTER_HEAD, {"source": "Image", "image": None})
		brevhuvud_html_kalla.execute()
		self.assertEqual(frappe.db.get_value("Letter Head", LETTER_HEAD, "source"), "HTML")

	def test_patchen_later_uppladdad_bild_vara(self):
		create_letter_head()
		frappe.db.set_value(
			"Letter Head", LETTER_HEAD, {"source": "Image", "image": "/files/logo.png", "content": "<img>"}
		)
		brevhuvud_html_kalla.execute()
		self.assertEqual(frappe.db.get_value("Letter Head", LETTER_HEAD, "source"), "Image")

	def test_logga_med_relativ_adress(self):
		# Relativ adress: webbläsaren hämtar bilden från samma värd, och get_pdf gör adressen absolut
		frappe.db.set_value("Company", COMPANY, "company_logo", "/files/logga.png")
		if frappe.db.exists("Letter Head", LETTER_HEAD):
			frappe.delete_doc("Letter Head", LETTER_HEAD, force=True)
		create_letter_head()
		mall = frappe.db.get_value("Letter Head", LETTER_HEAD, "content")
		html = frappe.render_template(mall, {"doc": frappe._dict(company=COMPANY)})
		self.assertIn('src="/files/logga.png"', html)
		self.assertIn("max-height: 30px; max-width: 120px", html)
		# Logotypen innehåller oftast namnet; namnet skrivs bara ut utan logotyp
		self.assertNotIn(f">{COMPANY}<", html)
		frappe.db.set_value("Company", COMPANY, "company_logo", None)
		html = frappe.render_template(mall, {"doc": frappe._dict(company=COMPANY)})
		self.assertIn(f">{COMPANY}<", html)
		self.assertNotIn("<img", html)

	def test_patchen_byter_forra_mallen_men_inte_egen(self):
		create_letter_head()
		frappe.db.set_value("Letter Head", LETTER_HEAD, "content", brevhuvud_bara_logga.FORRA_MALLEN)
		brevhuvud_bara_logga.execute()
		self.assertNotIn("display: flex", frappe.db.get_value("Letter Head", LETTER_HEAD, "content"))
		# Variant utan kommentarsraden: skapad från första mallen och rättad av brevhuvud_relativ_logga
		utan_kommentar = "\n".join(
			rad for rad in brevhuvud_bara_logga.FORRA_MALLEN.split("\n") if "Relativ adress" not in rad
		)
		frappe.db.set_value("Letter Head", LETTER_HEAD, "content", utan_kommentar)
		brevhuvud_bara_logga.execute()
		self.assertNotIn("display: flex", frappe.db.get_value("Letter Head", LETTER_HEAD, "content"))
		frappe.db.set_value("Letter Head", LETTER_HEAD, "content", "<p>Eget</p>")
		brevhuvud_bara_logga.execute()
		self.assertEqual(frappe.db.get_value("Letter Head", LETTER_HEAD, "content"), "<p>Eget</p>")

	def test_patchen_byter_till_relativ_adress(self):
		create_letter_head()
		frappe.db.set_value(
			"Letter Head", LETTER_HEAD, "content", '<p>Eget</p><img src="{{ frappe.utils.get_url(logo) }}">'
		)
		brevhuvud_relativ_logga.execute()
		self.assertEqual(
			frappe.db.get_value("Letter Head", LETTER_HEAD, "content"), '<p>Eget</p><img src="{{ logo }}">'
		)

	def test_patchen_minskar_loggan(self):
		create_letter_head()
		frappe.db.set_value(
			"Letter Head",
			LETTER_HEAD,
			"content",
			'<p>Eget</p><img style="max-height: 60px; max-width: 240px">',
		)
		brevhuvud_loggstorlek.execute()
		self.assertEqual(
			frappe.db.get_value("Letter Head", LETTER_HEAD, "content"),
			'<p>Eget</p><img style="max-height: 30px; max-width: 120px">',
		)

	def test_invoice_header_is_swedish(self):
		make_letter_head(ERPNEXT_LETTER_HEADS[-1], is_default=1)
		create_letter_head()
		item = make_item("TEST-SE-BREVHUVUD", kind=GOODS)
		customer = make_party("Customer", "Test SE Kund AB", TAX_CATEGORY_SE)
		# Nya dokument får standardvärdet "letter_head". Det läses ur den delade Redis-cachen, som andra
		# processer (t.ex. en worker efter migrate) kan fylla med det committade värdet medan testets
		# transaktion pågår. Kontrollera därför standardvärdet i databasen och sätt brevhuvudet explicit.
		self.assertEqual(
			frappe.db.get_value("DefaultValue", {"parent": "__default", "defkey": "letter_head"}, "defvalue"),
			LETTER_HEAD,
		)
		si = make_invoice("Sales Invoice", customer, [(item, 100)], submit=False)
		si.letter_head = LETTER_HEAD
		frappe.local.lang = "sv"
		html = frappe.get_print("Sales Invoice", si.name, print_format="Faktura Sverige", doc=si)
		header = html.split('class="letter-head"', 1)[1].split("</div>\n", 1)[0]
		self.assertIn(COMPANY, header)
		self.assertNotIn("Sales Invoice", header)
		self.assertNotIn(si.name, header)
