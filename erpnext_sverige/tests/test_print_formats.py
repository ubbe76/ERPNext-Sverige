import frappe
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from erpnext_sverige.setup.company import TAX_CATEGORY_EU, TAX_CATEGORY_SE
from erpnext_sverige.setup.custom_fields import GOODS, PRINT_FORMATS, SERVICE, set_default_print_formats
from erpnext_sverige.sweden_compliance.print_context import get_print_context
from erpnext_sverige.tests.utils import COMPANY, account, ensure_test_company, make_item, make_party

# Datum som krävs på raderna för att dokumenten ska gå att spara
ROW_DATES = {
	"Sales Order": {"delivery_date": add_days(today(), 14)},
	"Purchase Order": {"schedule_date": add_days(today(), 14)},
}


def make_doc(doctype, items, submit=False, **fields):
	"""items: [(item_code, rate)]; qty är alltid 2."""
	doc = frappe.get_doc(
		{
			"doctype": doctype,
			"company": COMPANY,
			**fields,
			"items": [
				{"item_code": code, "qty": 2, "rate": rate, **ROW_DATES.get(doctype, {})}
				for code, rate in items
			],
		}
	)
	doc.update(ROW_DATES.get(doctype, {}))
	doc.set_missing_values()
	doc.insert()
	if submit:
		doc.submit()
	return doc


def render(doc) -> str:
	frappe.local.lang = "sv"
	return frappe.get_print(doc.doctype, doc.name, print_format=PRINT_FORMATS[doc.doctype], doc=doc)


class PrintTestCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		frappe.db.set_value("Company", COMPANY, {"tax_id": "5560000000", "se_f_skatt": 1})
		frappe.db.commit()

	def setUp(self):
		self.service = make_item("TEST-SE-TJANST", kind=SERVICE)
		self.goods = make_item("TEST-SE-VARA", kind=GOODS)
		self.customer_se = make_party("Customer", "Test SE Kund AB", TAX_CATEGORY_SE)
		self.customer_eu = make_party("Customer", "Test EU Kunde GmbH", TAX_CATEGORY_EU)
		self.supplier_se = make_party("Supplier", "Test SE Leverantör AB", TAX_CATEGORY_SE)
		self.supplier_eu = make_party("Supplier", "Test EU Lieferant GmbH", TAX_CATEGORY_EU)

	def tearDown(self):
		frappe.db.rollback()
		frappe.local.lang = "en"


class TestPrintContext(PrintTestCase):
	def test_sales_order_context(self):
		so = make_doc("Sales Order", [(self.service, 1000)], customer=self.customer_se)
		ctx = get_print_context(so)
		self.assertEqual(ctx["org_nr"], "556000-0000")
		self.assertEqual(ctx["vat_no"], "SE556000000001")
		self.assertEqual(ctx["customer"], self.customer_se)
		self.assertEqual({row["rate"]: row["vat"] for row in ctx["vat_summary"]}, {25: 500})
		self.assertEqual(ctx["notes"], [])

	def test_eu_quotation_has_notes_and_customer_vat_number(self):
		qtn = make_doc(
			"Quotation", [(self.service, 100)], quotation_to="Customer", party_name=self.customer_eu
		)
		ctx = get_print_context(qtn)
		self.assertTrue(ctx["notes"])
		self.assertEqual(ctx["customer"], self.customer_eu)
		self.assertEqual(ctx["customer_vat_no"], "DE123456789")

	def test_purchase_order_has_no_vat_summary_or_customer(self):
		po = make_doc("Purchase Order", [(self.service, 100)], supplier=self.supplier_se)
		ctx = get_print_context(po)
		self.assertEqual(ctx["vat_summary"], [])
		self.assertEqual(ctx["notes"], [])
		self.assertIsNone(ctx["customer"])
		self.assertIsNone(ctx["customer_vat_no"])


class TestQuotationPrint(PrintTestCase):
	def test_renders_in_swedish(self):
		qtn = make_doc(
			"Quotation",
			[(self.service, 1000)],
			quotation_to="Customer",
			party_name=self.customer_se,
			valid_till=add_days(today(), 30),  # sätts annars bara av formuläret i webbläsaren
		)
		qtn.contact_display = "Anna Andersson"
		html = render(qtn)
		for text in ("Offert", "Offertnr", "Giltig till", "Er referens", "Anna Andersson", "Kundnummer"):
			self.assertIn(text, html)
		for text in ("Moms 25 % på", "Totalt inkl. moms", ">St<", "556000-0000"):
			self.assertIn(text, html)
		for text in ("Customer Name", "Bill to", ">Nos<", "In Words", "Grand Total", "Bankgiro"):
			self.assertNotIn(text, html)

	def test_quotation_to_lead(self):
		lead = frappe.get_doc({"doctype": "Lead", "lead_name": "Test Leadsson"}).insert()
		qtn = make_doc(
			"Quotation",
			[(self.service, 1000)],
			quotation_to="Lead",
			party_name=lead.name,
			currency="SEK",  # en Lead har ingen standardvaluta
			conversion_rate=1,
		)
		html = render(qtn)
		self.assertIn("Offert", html)
		self.assertNotIn("Kundnummer", html)
		self.assertIn("Test Leadsson", html)

	def test_foreign_currency_shows_vat_in_sek(self):
		qtn = make_doc(
			"Quotation",
			[(self.service, 1000)],
			quotation_to="Customer",
			party_name=self.customer_se,
			currency="EUR",
			conversion_rate=11.5,
		)
		html = render(qtn)
		self.assertIn(frappe._("VAT in {0}", lang="sv").format("SEK"), html)


class TestSalesOrderPrint(PrintTestCase):
	def test_renders_in_swedish(self):
		so = make_doc("Sales Order", [(self.service, 1000)], customer=self.customer_se, po_no="PO-4711")
		so.contact_display = "Anna Andersson"
		html = render(so)
		for text in ("Orderbekräftelse", "Orderdatum", "Leveransdatum", "Ert ordernr", "PO-4711"):
			self.assertIn(text, html)
		for text in ("Er referens", "Anna Andersson", "Moms 25 % på", "Totalt inkl. moms", ">St<"):
			self.assertIn(text, html)
		for text in ("Customer Name", "Bill to", ">Nos<", "In Words", "Grand Total", ">Nej<"):
			self.assertNotIn(text, html)

	def test_empty_references_are_left_out(self):
		so = make_doc("Sales Order", [(self.service, 1000)], customer=self.customer_se)
		so.contact_display = None
		html = render(so)
		self.assertNotIn("Ert ordernr", html)
		self.assertNotIn("Er referens", html)


class TestDeliveryNotePrint(PrintTestCase):
	def make_delivery_note(self, *orders):
		dn = make_delivery_note(orders[0].name)
		for order in orders[1:]:
			dn = make_delivery_note(order.name, target_doc=dn)
		dn.insert()
		return dn

	def test_renders_without_prices(self):
		so = make_doc(
			"Sales Order", [(self.service, 1000)], submit=True, customer=self.customer_se, po_no="PO-4711"
		)
		dn = self.make_delivery_note(so)
		dn.transporter_name = "Schenker"
		dn.lr_no = "FS-123"
		html = render(dn)
		for text in ("Följesedel", "Följesedelsnr", "Leveransadress", so.name, "Ert ordernr", "PO-4711"):
			self.assertIn(text, html)
		for text in ("Transportör", "Schenker", "Fraktsedelsnr", "FS-123", ">St<"):
			self.assertIn(text, html)
		for text in ("Enhetspris", "Belopp", "Totalt", "Moms 25", ">Nos<", "Customer Name", "Bankgiro"):
			self.assertNotIn(text, html)

	def test_lists_each_sales_order_once(self):
		first = make_doc("Sales Order", [(self.service, 100)], submit=True, customer=self.customer_se)
		second = make_doc(
			"Sales Order", [(self.service, 200), (self.goods, 300)], submit=True, customer=self.customer_se
		)
		dn = self.make_delivery_note(first, second)
		html = render(dn)
		self.assertIn(", ".join(sorted([first.name, second.name])), html)
		self.assertEqual(html.count(second.name), 1)

	def test_empty_carrier_is_left_out(self):
		so = make_doc("Sales Order", [(self.service, 1000)], submit=True, customer=self.customer_se)
		html = render(self.make_delivery_note(so))
		self.assertNotIn("Transportör", html)
		self.assertNotIn("Fraktsedelsnr", html)


class TestPurchaseOrderPrint(PrintTestCase):
	def test_renders_in_swedish(self):
		po = make_doc("Purchase Order", [(self.service, 1000)], supplier=self.supplier_se)
		html = render(po)
		for text in ("Inköpsorder", "Inköpsordernr", "Önskat leveransdatum", "Leverantörsnr", "Leverantör"):
			self.assertIn(text, html)
		for text in ("Test SE Leverantör AB", ">Moms<", "Totalt inkl. moms", ">St<"):
			self.assertIn(text, html)
		for text in ("Kundnummer", "Moms 25 % på", ">Nos<", "In Words", "Bankgiro"):
			self.assertNotIn(text, html)

	def test_eu_reverse_charge_has_no_vat_row(self):
		po = make_doc("Purchase Order", [(self.service, 1000)], supplier=self.supplier_eu)
		self.assertFalse(po.total_taxes_and_charges)
		html = render(po)
		self.assertNotIn(">Moms<", html)
		self.assertEqual(po.grand_total, po.net_total)


class TestDefaultPrintFormats(PrintTestCase):
	def test_swedish_formats_are_default(self):
		set_default_print_formats()
		for doctype, print_format in PRINT_FORMATS.items():
			frappe.clear_cache(doctype=doctype)
			self.assertEqual(frappe.get_meta(doctype).default_print_format, print_format, doctype)

	def test_own_print_format_is_kept(self):
		own = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": "Test egen offert",
				"doc_type": "Quotation",
				"standard": "No",
				"custom_format": 1,
				"print_format_type": "Jinja",
				"html": "<p>egen</p>",
			}
		).insert()
		make_property_setter("Quotation", None, "default_print_format", own.name, "Data", for_doctype=True)
		set_default_print_formats()
		frappe.clear_cache(doctype="Quotation")
		self.assertEqual(frappe.get_meta("Quotation").default_print_format, own.name)


class TestOtherCharges(PrintTestCase):
	"""Frakt och andra avgifter i skattetabellen är inte moms och ska visas på en egen rad."""

	def add_freight(self, doc, account_number):
		doc.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": account(account_number),
				"description": "Frakt",
				"tax_amount": 100,
				"category": "Total",
				"add_deduct_tax": "Add",
			},
		)
		doc.save()
		return doc

	def test_sales_order_shows_freight(self):
		so = make_doc("Sales Order", [(self.service, 1000)], customer=self.customer_se)
		self.add_freight(so, "3520")
		html = render(so)
		self.assertIn("Övriga avgifter", html)
		self.assertIn("100,00 kr", html)
		self.assertIn("2 600,00 kr", html)  # 2 000 + 500 moms + 100 frakt

	def test_purchase_order_does_not_call_freight_vat(self):
		frappe.db.set_value("Account", account("5710"), "account_type", "Chargeable")
		po = make_doc("Purchase Order", [(self.service, 1000)], supplier=self.supplier_se)
		self.add_freight(po, "5710")
		html = render(po)
		self.assertIn("Övriga avgifter", html)
		self.assertIn(
			'<td>Moms</td><td class="se-right">500,00 kr</td>', html
		)  # frakten räknas inte som moms
