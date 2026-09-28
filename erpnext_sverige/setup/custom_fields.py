from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields as _create_custom_fields

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
