"""Leverantörsbetalningar: samla förfallna leverantörsfakturor och skapa en betalfil (ISO 20022 pain.001).

"Skapa betalfil" skapar också en Payment Entry i utkastläge per faktura. Bokför dem ("Bokför betalningar")
när banken har genomfört betalningarna.
"""

import frappe
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from erpnext_sverige.sweden_compliance.invoice import format_org_nr
from erpnext_sverige.sweden_compliance.pain001 import (
	BANK_ACCOUNT,
	BANKGIRO,
	IBAN,
	PLUSGIRO,
	Creditor,
	Debtor,
	Transfer,
	build_pain001,
	digits,
)


class Leverantorsbetalning(Document):
	def validate(self):
		for row in self.invoices:
			self._fill_row(row)
		self.total_amount = sum(flt(row.amount) for row in self.invoices)

	@frappe.whitelist()
	def get_due_invoices(self):
		"""Lägg till obetalda leverantörsfakturor (SEK) som förfaller senast betalningsdagen."""
		self.check_permission("write")
		existing = {row.purchase_invoice for row in self.invoices}
		invoices = frappe.get_all(
			"Purchase Invoice",
			filters={
				"company": self.company,
				"docstatus": 1,
				"outstanding_amount": [">", 0],
				"due_date": ["<=", self.execution_date],
				"currency": "SEK",
				"on_hold": 0,
			},
			fields=["name", "outstanding_amount"],
			order_by="due_date, name",
		)
		for invoice in invoices:
			if invoice.name not in existing and not _in_other_batch(invoice.name, self.name):
				self.append(
					"invoices", {"purchase_invoice": invoice.name, "amount": invoice.outstanding_amount}
				)
		self.save()
		return len(self.invoices) - len(existing)

	@frappe.whitelist()
	def create_payment_file(self):
		"""Skapa betalfilen och Payment Entry (utkast) för varje faktura."""
		self.check_permission("write")
		if not self.invoices:
			frappe.throw(_("Lägg till minst en faktura"))
		missing = [row.purchase_invoice for row in self.invoices if not row.creditor_account]
		if missing:
			frappe.throw(
				_(
					"Leverantörens bankuppgifter saknas för: {0}. Lägg upp ett Bank Account för leverantören."
				).format(", ".join(missing))
			)

		content = build_pain001(
			self.name,
			self._debtor(),
			getdate(self.execution_date),
			[self._transfer(row) for row in self.invoices],
		)
		for row in self.invoices:
			if not row.payment_entry:
				row.payment_entry = self._make_payment_entry(row)

		if self.payment_file:
			frappe.delete_doc("File", {"file_url": self.payment_file}, ignore_permissions=True, force=True)
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"{self.name}-pain001.xml",
				"content": content,
				"is_private": 1,
				"attached_to_doctype": self.doctype,
				"attached_to_name": self.name,
			}
		).insert()
		self.payment_file = file_doc.file_url
		self.status = "Fil skapad"
		self.save()
		return file_doc.file_url

	@frappe.whitelist()
	def submit_payments(self):
		"""Bokför betalningarna när banken har genomfört dem."""
		self.check_permission("write")
		submitted = 0
		for row in self.invoices:
			if (
				row.payment_entry
				and frappe.db.get_value("Payment Entry", row.payment_entry, "docstatus") == 0
			):
				frappe.get_doc("Payment Entry", row.payment_entry).submit()
				submitted += 1
		self.status = "Bokförd"
		self.save()
		return submitted

	def _fill_row(self, row):
		invoice = frappe.db.get_value(
			"Purchase Invoice",
			row.purchase_invoice,
			["supplier", "due_date", "bill_no", "se_payment_reference", "company", "currency", "docstatus"],
			as_dict=True,
		)
		if not invoice or invoice.docstatus != 1 or invoice.company != self.company:
			frappe.throw(
				_("Faktura {0} är inte en bokförd leverantörsfaktura för {1}").format(
					row.purchase_invoice, self.company
				)
			)
		if invoice.currency != "SEK":
			frappe.throw(
				_("Faktura {0} är i {1}. Betalfilen hanterar bara SEK.").format(
					row.purchase_invoice, invoice.currency
				)
			)
		row.supplier, row.due_date = invoice.supplier, invoice.due_date
		row.reference = invoice.se_payment_reference or invoice.bill_no or row.purchase_invoice
		creditor = get_creditor(invoice.supplier)
		row.payment_method = creditor.method if creditor else None
		row.creditor_account = creditor.account if creditor else None

	def _transfer(self, row) -> Transfer:
		invoice = frappe.db.get_value(
			"Purchase Invoice", row.purchase_invoice, ["bill_no", "se_payment_reference"], as_dict=True
		)
		return Transfer(
			end_to_end_id=row.purchase_invoice,
			amount=flt(row.amount, 2),
			creditor=get_creditor(row.supplier),
			ocr=invoice.se_payment_reference or "",
			invoice_number=invoice.bill_no or row.purchase_invoice,
		)

	def _debtor(self) -> Debtor:
		account = frappe.get_doc("Bank Account", self.bank_account)
		if not account.is_company_account or account.company != self.company:
			frappe.throw(
				_("{0} är inte ett bankkonto för bolaget {1}").format(self.bank_account, self.company)
			)
		if not (account.iban or (account.branch_code and account.bank_account_no)):
			frappe.throw(_("Bolagets bankkonto saknar IBAN eller clearing- och kontonummer"))
		return Debtor(
			name=self.company,
			iban=account.iban or "",
			bic=frappe.get_cached_value("Bank", account.bank, "swift_number") if account.bank else "",
			clearing=account.branch_code or "",
			account_no=account.bank_account_no or "",
			org_nr=format_org_nr(frappe.get_cached_value("Company", self.company, "tax_id")) or "",
		)

	def _make_payment_entry(self, row) -> str:
		pe = get_payment_entry(
			"Purchase Invoice", row.purchase_invoice, party_amount=row.amount, bank_amount=row.amount
		)
		pe.paid_from = frappe.db.get_value("Bank Account", self.bank_account, "account") or pe.paid_from
		pe.posting_date = self.execution_date
		pe.reference_no = self.name
		pe.reference_date = self.execution_date
		pe.remarks = _("Leverantörsbetalning {0}, referens {1}").format(self.name, row.reference)
		pe.insert()
		return pe.name


def get_creditor(supplier: str) -> Creditor | None:
	"""Leverantörens betalningsmottagare: bankgiro före plusgiro, bankkonto och IBAN."""
	accounts = frappe.get_all(
		"Bank Account",
		filters={"party_type": "Supplier", "party": supplier, "disabled": 0},
		fields=["bank", "iban", "bank_account_no", "branch_code", "se_bankgiro", "se_plusgiro"],
		order_by="is_default desc, creation",
	)
	name = frappe.db.get_value("Supplier", supplier, "supplier_name") or supplier
	for account in accounts:
		if account.se_bankgiro:
			return Creditor(name, BANKGIRO, digits(account.se_bankgiro))
		if account.se_plusgiro:
			return Creditor(name, PLUSGIRO, digits(account.se_plusgiro))
		if account.branch_code and account.bank_account_no:
			return Creditor(
				name,
				BANK_ACCOUNT,
				digits(account.branch_code) + digits(account.bank_account_no),
				clearing=account.branch_code,
			)
		if account.iban:
			bic = frappe.get_cached_value("Bank", account.bank, "swift_number") if account.bank else ""
			return Creditor(name, IBAN, account.iban.replace(" ", ""), bic=bic or "")
	return None


def _in_other_batch(purchase_invoice: str, current: str) -> bool:
	return bool(
		frappe.db.sql(
			"""
			select 1 from `tabLeverantorsbetalning Rad` rad
			join `tabLeverantorsbetalning` lb on lb.name = rad.parent
			join `tabPayment Entry` pe on pe.name = rad.payment_entry
			where rad.purchase_invoice = %s and lb.name != %s and pe.docstatus = 0
			""",
			(purchase_invoice, current or ""),
		)
	)
