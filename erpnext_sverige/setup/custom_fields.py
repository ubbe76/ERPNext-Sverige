import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields as _create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from erpnext_sverige.frakt.custom_fields import get_custom_fields as get_frakt_custom_fields

INVOICE_PRINT_FORMAT = "Faktura Sverige"
# Svenska utskriftsmallar (sweden_compliance/print_format) per doctype
PRINT_FORMATS = {
	"Quotation": "Offert Sverige",
	"Sales Order": "Orderbekräftelse Sverige",
	"Delivery Note": "Följesedel Sverige",
	"Sales Invoice": INVOICE_PRINT_FORMAT,
	"Purchase Order": "Inköpsorder Sverige",
}
GOODS = "Vara"
SERVICE = "Tjänst"


def _get_base_custom_fields():
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


def get_custom_fields():
	fields = _get_base_custom_fields()
	for doctype, frakt_fields in get_frakt_custom_fields().items():
		fields.setdefault(doctype, []).extend(frakt_fields)
	return fields


def create_custom_fields():
	from erpnext_sverige.frakt.artikel import sakerstall_fraktartikel

	_create_custom_fields(get_custom_fields(), update=True)
	set_default_print_formats()
	sakerstall_fraktartikel()


def set_default_print_formats():
	"""Gör de svenska mallarna (PRINT_FORMATS) till standardmallar.

	ERPNext:s egna standardmallar ersätts, men en egen (icke-standard) mall som valts lämnas orörd.
	"""
	for doctype, print_format in PRINT_FORMATS.items():
		if not frappe.db.exists("Print Format", print_format):
			continue
		current = frappe.get_meta(doctype).default_print_format
		if current == print_format:
			continue
		if current and frappe.db.get_value("Print Format", current, "standard") == "No":
			continue
		make_property_setter(doctype, None, "default_print_format", print_format, "Data", for_doctype=True)
