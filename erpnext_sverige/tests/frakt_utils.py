"""Testhjälpare för frakt."""

import frappe


def make_eur_pall(name="_Test EUR-pall", egenvikt=25):
	if not frappe.db.exists("Forpackningstyp", name):
		frappe.get_doc(
			{
				"doctype": "Forpackningstyp",
				"forpackningstyp_namn": name,
				"kollityp": "Pall",
				"langd_cm": 120,
				"bredd_cm": 80,
				"hojd_cm": 150,
				"egenvikt_kg": egenvikt,
				"stapelbar": 0,
				"flakmeter": 0.4,
			}
		).insert()
	return name


def make_frakt_item(item_code, weight_uom="Kg", uoms=None, **fields):
	"""Skapar eller uppdaterar en artikel med fraktfält. uoms: [(uom, conversion_factor)]."""
	doc = frappe.get_doc("Item", item_code) if frappe.db.exists("Item", item_code) else frappe.new_doc("Item")
	doc.update(
		{
			"item_code": item_code,
			"item_name": item_code,
			"item_group": "Services",
			"stock_uom": "Nos",
			"is_stock_item": 0,
			"weight_uom": weight_uom,
			**fields,
		}
	)
	if uoms:
		doc.uoms = []
		doc.append("uoms", {"uom": "Nos", "conversion_factor": 1})
		for uom, factor in uoms:
			doc.append("uoms", {"uom": uom, "conversion_factor": factor})
	doc.save()
	return doc.name
