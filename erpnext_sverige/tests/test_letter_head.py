import frappe
from frappe.tests import IntegrationTestCase

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

	def test_invoice_header_is_swedish(self):
		make_letter_head(ERPNEXT_LETTER_HEADS[-1], is_default=1)
		create_letter_head()
		item = make_item("TEST-SE-BREVHUVUD", kind=GOODS)
		customer = make_party("Customer", "Test SE Kund AB", TAX_CATEGORY_SE)
		si = make_invoice("Sales Invoice", customer, [(item, 100)], submit=False)
		# Nya dokument får standardbrevhuvudet; utskriften använder dokumentets brevhuvud.
		self.assertEqual(si.letter_head, LETTER_HEAD)
		frappe.local.lang = "sv"
		html = frappe.get_print("Sales Invoice", si.name, print_format="Faktura Sverige", doc=si)
		header = html.split('class="letter-head"', 1)[1].split("</div>\n", 1)[0]
		self.assertIn(COMPANY, header)
		self.assertNotIn("Sales Invoice", header)
		self.assertNotIn(si.name, header)
