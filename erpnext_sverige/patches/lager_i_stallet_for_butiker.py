"""ERPNext:s standardlager Stores översattes till "Butiker" (affärer). Nu heter det "Lager".

ERPNext letar upp standardlagret med det översatta namnet (_("Stores")), så befintliga lager döps om. rename_doc
uppdaterar alla länkar (artiklars standardlager, lagerinställningar, lagertransaktioner). Finns redan ett lager
med det nya namnet lämnas bolagets lager orört.
"""

import frappe


def execute():
	for lager in frappe.get_all(
		"Warehouse", filters={"warehouse_name": "Butiker", "is_group": 0}, fields=["name"]
	):
		ny = "Lager" + lager.name.removeprefix("Butiker")
		if frappe.db.exists("Warehouse", ny):
			continue
		frappe.rename_doc("Warehouse", lager.name, ny, force=True, show_alert=False)
		frappe.db.set_value("Warehouse", ny, "warehouse_name", "Lager", update_modified=False)
