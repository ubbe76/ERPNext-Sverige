from datetime import date
from xml.etree import ElementTree as ET

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import add_days, today

from erpnext_sverige.setup.company import TAX_CATEGORY_SE
from erpnext_sverige.setup.custom_fields import SERVICE
from erpnext_sverige.sweden_compliance.pain001 import (
	BANK_ACCOUNT,
	BANKGIRO,
	IBAN,
	NAMESPACE,
	PLUSGIRO,
	Creditor,
	Debtor,
	Transfer,
	build_pain001,
)
from erpnext_sverige.tests.utils import COMPANY, account, ensure_test_company, make_item, make_party

NS = {"p": NAMESPACE}


def parse(content: bytes):
	return ET.fromstring(content)


class TestBuildPain001(UnitTestCase):
	def build(self):
		transfers = [
			Transfer("PINV-1", 1250, Creditor("Leverantör BG AB", BANKGIRO, "56781234"), ocr="123456789"),
			Transfer("PINV-2", 99.5, Creditor("Leverantör PG AB", PLUSGIRO, "4711"), invoice_number="F-77"),
			Transfer("PINV-3", 10, Creditor("Konto AB", BANK_ACCOUNT, "50001234567", clearing="5000")),
			Transfer("PINV-4", 20, Creditor("GmbH", IBAN, "DE89370400440532013000", bic="COBADEFFXXX")),
		]
		debtor = Debtor(
			"Testbolaget AB", iban="SE4550000000058398257466", bic="ESSESESS", org_nr="556000-0000"
		)
		return parse(build_pain001("LB-2026-00001", debtor, date(2026, 10, 1), transfers))

	def test_header(self):
		root = self.build()
		self.assertEqual(root.findtext(".//p:GrpHdr/p:NbOfTxs", namespaces=NS), "4")
		self.assertEqual(root.findtext(".//p:GrpHdr/p:CtrlSum", namespaces=NS), "1379.50")
		self.assertEqual(root.findtext(".//p:PmtInf/p:ReqdExctnDt", namespaces=NS), "2026-10-01")
		self.assertEqual(
			root.findtext(".//p:DbtrAcct/p:Id/p:IBAN", namespaces=NS), "SE4550000000058398257466"
		)
		self.assertEqual(root.findtext(".//p:InitgPty/p:Id/p:OrgId/p:Othr/p:Id", namespaces=NS), "5560000000")

	def test_creditor_accounts(self):
		txs = self.build().findall(".//p:CdtTrfTxInf", NS)
		bg, pg, bank, iban = txs
		self.assertEqual(bg.findtext(".//p:CdtrAcct//p:Othr/p:Id", namespaces=NS), "56781234")
		self.assertEqual(bg.findtext(".//p:CdtrAcct//p:SchmeNm/p:Prtry", namespaces=NS), "BGNR")
		self.assertEqual(bg.findtext(".//p:CdtrAgt//p:MmbId", namespaces=NS), "9900")
		self.assertEqual(pg.findtext(".//p:CdtrAgt//p:MmbId", namespaces=NS), "9960")
		self.assertEqual(bank.findtext(".//p:CdtrAgt//p:MmbId", namespaces=NS), "5000")
		self.assertEqual(bank.findtext(".//p:CdtrAcct//p:SchmeNm/p:Cd", namespaces=NS), "BBAN")
		self.assertEqual(iban.findtext(".//p:CdtrAcct/p:Id/p:IBAN", namespaces=NS), "DE89370400440532013000")
		self.assertEqual(iban.findtext(".//p:CdtrAgt//p:BIC", namespaces=NS), "COBADEFFXXX")

	def test_references(self):
		bg, pg, *_rest = self.build().findall(".//p:CdtTrfTxInf", NS)
		self.assertEqual(bg.findtext(".//p:CdtrRefInf/p:Tp/p:CdOrPrtry/p:Cd", namespaces=NS), "SCOR")
		self.assertEqual(bg.findtext(".//p:CdtrRefInf/p:Ref", namespaces=NS), "123456789")
		self.assertEqual(pg.findtext(".//p:RmtInf/p:Ustrd", namespaces=NS), "F-77")
		self.assertEqual(bg.find(".//p:InstdAmt", NS).get("Ccy"), "SEK")


class TestLeverantorsbetalning(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()

	def setUp(self):
		self.service = make_item("TEST-SE-TJANST", kind=SERVICE)
		if not frappe.db.exists("Bank", "Testbanken"):
			frappe.get_doc(
				{"doctype": "Bank", "bank_name": "Testbanken", "swift_number": "TESTSESS"}
			).insert()
		self.company_account = frappe.get_doc(
			{
				"doctype": "Bank Account",
				"account_name": "Test Företagskonto",
				"bank": "Testbanken",
				"company": COMPANY,
				"is_company_account": 1,
				"account": account("1930"),
				"iban": "SE4550000000058398257466",
			}
		).insert()
		self.supplier_bg = make_party("Supplier", "Test Leverantör Bankgiro AB", TAX_CATEGORY_SE)
		self.supplier_none = make_party("Supplier", "Test Leverantör Utan Konto AB", TAX_CATEGORY_SE)
		frappe.get_doc(
			{
				"doctype": "Bank Account",
				"account_name": "Bankgiro",
				"bank": "Testbanken",
				"party_type": "Supplier",
				"party": self.supplier_bg,
				"se_bankgiro": "5678-1234",
			}
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def purchase_invoice(self, supplier, amount, due_in_days=0, ocr=None):
		doc = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"supplier": supplier,
				"company": COMPANY,
				"bill_no": frappe.generate_hash(length=8),
				"posting_date": today(),
				"due_date": add_days(today(), due_in_days),
				"se_payment_reference": ocr,
				"items": [{"item_code": self.service, "qty": 1, "rate": amount}],
			}
		)
		doc.set_missing_values()
		doc.insert()
		doc.submit()
		return doc

	def batch(self, execution_date=None):
		return frappe.get_doc(
			{
				"doctype": "Leverantorsbetalning",
				"company": COMPANY,
				"bank_account": self.company_account.name,
				"execution_date": execution_date or add_days(today(), 1),
			}
		).insert()

	def test_get_due_invoices_and_create_file(self):
		due = self.purchase_invoice(self.supplier_bg, 1000, ocr="1234567897")
		self.purchase_invoice(self.supplier_bg, 500, due_in_days=30)  # förfaller senare

		batch = self.batch()
		self.assertEqual(batch.get_due_invoices(), 1)
		batch.reload()
		row = batch.invoices[0]
		self.assertEqual(row.purchase_invoice, due.name)
		self.assertEqual(row.amount, 1250)
		self.assertEqual((row.payment_method, row.creditor_account), ("Bankgiro", "56781234"))
		self.assertEqual(row.reference, "1234567897")

		batch.create_payment_file()
		batch.reload()
		self.assertEqual(batch.status, "Fil skapad")
		content = frappe.get_doc("File", {"file_url": batch.payment_file}).get_content()
		root = parse(content if isinstance(content, bytes) else content.encode())
		self.assertEqual(root.findtext(".//p:GrpHdr/p:CtrlSum", namespaces=NS), "1250.00")
		self.assertEqual(root.findtext(".//p:CdtrRefInf/p:Ref", namespaces=NS), "1234567897")

		pe = frappe.get_doc("Payment Entry", batch.invoices[0].payment_entry)
		self.assertEqual((pe.docstatus, pe.payment_type, pe.paid_amount), (0, "Pay", 1250))
		self.assertEqual(pe.paid_from, account("1930"))

		self.assertEqual(batch.submit_payments(), 1)
		self.assertEqual(frappe.db.get_value("Purchase Invoice", due.name, "outstanding_amount"), 0)

	def test_missing_supplier_bank_details(self):
		invoice = self.purchase_invoice(self.supplier_none, 100)
		batch = self.batch()
		batch.append("invoices", {"purchase_invoice": invoice.name, "amount": 125})
		batch.save()
		self.assertFalse(batch.invoices[0].creditor_account)
		self.assertRaises(frappe.ValidationError, batch.create_payment_file)
