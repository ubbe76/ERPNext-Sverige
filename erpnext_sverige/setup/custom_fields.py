import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields as _create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

INVOICE_PRINT_FORMAT = "Faktura Sverige"
GOODS = "Vara"
SERVICE = "Tjänst"


def get_custom_fields():
	return {
		"Item": [
			{
				"fieldname": "se_goods_or_service",
				"label": _("Vara eller tjänst (moms)"),
				"fieldtype": "Select",
				"options": f"\n{GOODS}\n{SERVICE}",
				"insert_after": "is_stock_item",
				"description": _(
					"Styr intäkts- och kostnadskonto vid försäljning och inköp inom EU och utanför EU. "
					"Tomt: lagerartiklar räknas som varor, övriga som tjänster."
				),
			},
		],
		"Company": [
			{
				"fieldname": "se_f_skatt",
				"label": _("Godkänd för F-skatt"),
				"fieldtype": "Check",
				"insert_after": "tax_id",
				"description": _('Skriver "Godkänd för F-skatt" på fakturan.'),
			},
			{
				"fieldname": "se_use_ocr",
				"label": _("OCR-nummer på fakturor"),
				"fieldtype": "Check",
				"insert_after": "se_f_skatt",
				"description": _("Kundfakturor får ett OCR-nummer (betalningsreferens med kontrollsiffra)."),
			},
		],
		"Bank Account": [
			{
				"fieldname": "se_bankgiro",
				"label": _("Bankgiro"),
				"fieldtype": "Data",
				"insert_after": "bank_account_no",
			},
			{
				"fieldname": "se_plusgiro",
				"label": _("Plusgiro"),
				"fieldtype": "Data",
				"insert_after": "se_bankgiro",
			},
		],
		"Sales Invoice": [
			{
				"fieldname": "se_ocr",
				"label": _("OCR-nummer"),
				"fieldtype": "Data",
				"read_only": 1,
				"no_copy": 1,
				"insert_after": "due_date",
			},
		],
		"Purchase Invoice": [
			{
				"fieldname": "se_payment_reference",
				"label": _("OCR / betalningsreferens"),
				"fieldtype": "Data",
				"insert_after": "bill_date",
				"description": _("OCR-nummer från leverantörens faktura. Används i betalfilen."),
			},
		],
		"Journal Entry": [
			{
				"fieldname": "se_vat_settlement_period",
				"label": _("Momsomföring för period"),
				"fieldtype": "Data",
				"read_only": 1,
				"no_copy": 1,
				"insert_after": "user_remark",
				"description": _("Sätts av Momsdeklaration. Verifikationen räknas inte med i momsrapporten."),
			},
		],
	}


def create_custom_fields():
	_create_custom_fields(get_custom_fields(), update=True)
	set_default_invoice_print_format()


def set_default_invoice_print_format():
	"""Gör "Faktura Sverige" till standardmall för kundfakturor.

	ERPNext:s egna standardmallar ersätts, men en egen (icke-standard) mall som valts lämnas orörd.
	"""
	if not frappe.db.exists("Print Format", INVOICE_PRINT_FORMAT):
		return
	current = frappe.get_meta("Sales Invoice").default_print_format
	if current == INVOICE_PRINT_FORMAT:
		return
	if current and frappe.db.get_value("Print Format", current, "standard") == "No":
		return
	make_property_setter(
		"Sales Invoice", None, "default_print_format", INVOICE_PRINT_FORMAT, "Data", for_doctype=True
	)
