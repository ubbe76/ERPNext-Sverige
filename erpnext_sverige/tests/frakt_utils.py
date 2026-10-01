"""Testhjälpare för frakt."""

import frappe

from erpnext_sverige.setup.company import TAX_CATEGORY_SE
from erpnext_sverige.tests.utils import COMPANY, account, ensure_test_company, make_party


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


def make_adress(titel, lank_doctype, lank_namn, foretag=False):
	namn = frappe.db.get_value("Address", {"address_title": titel})
	if namn:
		return namn
	return (
		frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": titel,
				"address_type": "Shipping" if not foretag else "Billing",
				"address_line1": "Testgatan 1",
				"city": "Göteborg",
				"pincode": "41107",
				"country": "Sweden",
				"is_your_company_address": int(foretag),
				"links": [{"link_doctype": lank_doctype, "link_name": lank_namn}],
			}
		)
		.insert()
		.name
	)


def make_kontakt(fornamn, lank_doctype, lank_namn, epost="test@example.com", telefon="0701234567"):
	namn = frappe.db.get_value("Contact", {"first_name": fornamn})
	if namn:
		return namn
	kontakt = frappe.get_doc(
		{
			"doctype": "Contact",
			"first_name": fornamn,
			"links": [{"link_doctype": lank_doctype, "link_name": lank_namn}],
		}
	)
	if epost:
		kontakt.append("email_ids", {"email_id": epost, "is_primary": 1})
	if telefon:
		kontakt.append("phone_nos", {"phone": telefon, "is_primary_mobile_no": 1})
	return kontakt.insert().name


def make_kund_med_adress(namn="_Test Fraktkund"):
	make_party("Customer", namn, TAX_CATEGORY_SE)
	make_adress(f"{namn} leverans", "Customer", namn)
	make_kontakt(f"{namn} kontakt", "Customer", namn)
	return namn


def aktivera_frakt(**andringar):
	ensure_test_company()
	inst = frappe.get_doc("Fraktinstallningar")
	inst.update(
		{
			"aktiverad": 1,
			"leverantor": "Sendify",
			"miljo": "Sandlåda",
			"api_nyckel": "test-nyckel",
			"bolag": COMPANY,
			"avsandaradress": make_adress("_Test Svenska AB lager", "Company", COMPANY, foretag=True),
			"avsandarkontakt": make_kontakt("_Test Lagerchef", "Company", COMPANY),
			"upphamtning_fran": "09:00:00",
			"upphamtning_till": "16:00:00",
			"paslag_procent": 10,
			"paslag_belopp": 20,
			"fraktkonto": account("3520"),
			"prisandring_grans_procent": 5,
			**andringar,
		}
	)
	inst.save()
	frappe.clear_document_cache("Fraktinstallningar", "Fraktinstallningar")
	return inst
