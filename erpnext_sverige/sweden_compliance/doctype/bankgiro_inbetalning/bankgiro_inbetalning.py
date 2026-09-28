"""Inläsning av Bankgirots inbetalningsfil (BgMax) med matchning mot kundfakturor via OCR.

Matchade betalningar blir Payment Entry i utkastläge, som granskas och bokförs med "Bokför betalningar".
Bankgirots löpnummer sparas som referens på betalningen, så samma betalning kan inte registreras två gånger.
"""

import frappe
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from erpnext_sverige.sweden_compliance.bgmax import BgMaxError, parse_bgmax

MATCHED = "Matchad"
UNMATCHED = "Ej matchad"
DUPLICATE = "Redan registrerad"
DEDUCTION = "Avdrag"
REFERENCE_PREFIX = "BG"


class BankgiroInbetalning(Document):
	def validate(self):
		if not self.bank_account and self.company:
			self.bank_account = frappe.get_cached_value("Company", self.company, "default_bank_account")

	@frappe.whitelist()
	def read_file(self):
		"""Tolka BgMax-filen, matcha mot fakturor och skapa betalningar (utkast)."""
		self.check_permission("write")
		if any(row.payment_entry for row in self.payments):
			frappe.throw(_("Filen är redan inläst och har betalningar. Skapa en ny inläsning för en ny fil."))

		file_doc = frappe.get_doc("File", {"file_url": self.bgmax_file})
		try:
			bgmax = parse_bgmax(file_doc.get_content())
		except BgMaxError as e:
			frappe.throw(_("Filen kunde inte läsas: {0}").format(e))

		self.test_file = int(bgmax.test_mark)
		self.set("payments", [])
		for payment in bgmax.payments:
			row = self.append(
				"payments",
				{
					"reference": payment.reference,
					"amount": payment.amount,
					"payer_name": payment.payer_name,
					"payer_bankgiro": payment.payer_bankgiro,
					"payer_org_nr": payment.payer_org_nr,
					"bgc_serial": payment.bgc_serial,
					"payment_date": payment.payment_date,
					"message": "\n".join(payment.information),
				},
			)
			self.receiving_bankgiro = self.receiving_bankgiro or payment.receiving_bankgiro
			self.payment_date = self.payment_date or payment.payment_date
			if payment.is_deduction:
				row.status = DEDUCTION
			elif self._is_registered(payment.bgc_serial):
				row.status = DUPLICATE
			else:
				row.sales_invoice = self._find_invoice(payment.reference)
				row.status = MATCHED if row.sales_invoice else UNMATCHED

		self.total_amount = sum(flt(row.amount) for row in self.payments)
		self.status = "Inläst"
		self._create_payments()

	@frappe.whitelist()
	def create_payments(self):
		"""Skapa betalningar för rader där kundfaktura valts manuellt."""
		self.check_permission("write")
		self._create_payments()

	@frappe.whitelist()
	def submit_payments(self):
		"""Bokför alla betalningar (utkast) från inläsningen."""
		self.check_permission("write")
		submitted = 0
		for row in self.payments:
			if (
				row.payment_entry
				and frappe.db.get_value("Payment Entry", row.payment_entry, "docstatus") == 0
			):
				frappe.get_doc("Payment Entry", row.payment_entry).submit()
				submitted += 1
		if all(row.payment_entry or row.status in (DUPLICATE, DEDUCTION) for row in self.payments):
			self.status = "Bokförd"
		self.save()
		return submitted

	def _create_payments(self):
		for row in self.payments:
			if row.payment_entry or not row.sales_invoice or row.status in (DUPLICATE, DEDUCTION):
				continue
			row.customer = frappe.db.get_value("Sales Invoice", row.sales_invoice, "customer")
			row.payment_entry = self._make_payment_entry(row)
			row.status = MATCHED
		self.matched_count = sum(1 for row in self.payments if row.payment_entry)
		self.unmatched_count = sum(
			1 for row in self.payments if row.status == UNMATCHED and not row.sales_invoice
		)
		self.save()

	def _make_payment_entry(self, row) -> str:
		pe = get_payment_entry(
			"Sales Invoice", row.sales_invoice, party_amount=row.amount, bank_amount=row.amount
		)
		if self.bank_account:
			pe.paid_to = self.bank_account
		pe.posting_date = row.payment_date or self.payment_date or frappe.utils.today()
		pe.reference_no = f"{REFERENCE_PREFIX} {row.bgc_serial}".strip()
		pe.reference_date = pe.posting_date
		pe.remarks = _("Bankgiroinbetalning {0}, OCR {1}, {2}").format(
			self.name, row.reference, row.payer_name or ""
		)
		pe.insert()
		return pe.name

	def _find_invoice(self, reference: str) -> str | None:
		if not reference:
			return None
		invoices = frappe.get_all(
			"Sales Invoice",
			filters={
				"company": self.company,
				"docstatus": 1,
				"se_ocr": reference.lstrip("0"),
				"outstanding_amount": [">", 0],
			},
			pluck="name",
			limit=2,
		)
		return invoices[0] if len(invoices) == 1 else None

	def _is_registered(self, bgc_serial: str) -> bool:
		return bool(
			bgc_serial
			and frappe.db.exists(
				"Payment Entry",
				{
					"reference_no": f"{REFERENCE_PREFIX} {bgc_serial}",
					"docstatus": ["<", 2],
					"company": self.company,
				},
			)
		)
