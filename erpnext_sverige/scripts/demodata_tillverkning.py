"""Testdata för en tillverkande verkstad (plåt och svets): artiklar, stycklistor, arbetsstationer, parter och lager.

Skapar bara det som saknas, så skriptet kan köras flera gånger. Påhittade parter och nummer. Körs bara på sajter
med allow_tests i site_config (test- och demosajter), aldrig i produktion:

	bench --site <demosite> execute erpnext_sverige.scripts.demodata_tillverkning.skapa \\
		--kwargs "{'company': 'Exempelbolaget AB'}"
"""

import frappe
from frappe import _
from frappe.utils import nowdate

from erpnext_sverige.setup.custom_fields import GOODS

# Arbetsstationer: timkostnad i kr uppdelad på personal, el, förbrukning och hyra (maskin och lokal)
ARBETSSTATIONER = {
	"Bandsåg": (380, 20, 20, 30),
	"Fiberlaser": (450, 250, 150, 550),
	"Kantpress": (450, 60, 40, 200),
	"Svetscell": (450, 80, 70, 50),
	"Lackeringslinje": (450, 200, 150, 100),
	"Monteringsbänk": (420, 10, 20, 30),
	"Packstation": (380, 10, 10, 20),
}

# ERPNext:s standardkomponenter för timkostnaden, i samma ordning som i ARBETSSTATIONER
KOMPONENTER = ("Wages", "Electricity", "Consumables", "Rent")

MOMENT = {
	"Kapning": "Bandsåg",
	"Laserskärning": "Fiberlaser",
	"Kantpressning": "Kantpress",
	"Svetsning": "Svetscell",
	"Pulverlackering": "Lackeringslinje",
	"Montering": "Monteringsbänk",
	"Packning": "Packstation",
}

# Leverantörer: namn, leverantörsgrupp, land, momsregistreringsnummer (EU) och adress
LEVERANTORER = [
	(
		"Stålgrossisten i Mälardalen AB",
		"Raw Material",
		"Sweden",
		None,
		("Industrigatan 12", "721 34", "Västerås"),
	),
	("Pulverfärg Norden AB", "Raw Material", "Sweden", None, ("Färgarvägen 3", "431 37", "Mölndal")),
	("Fästelement i Jönköping AB", "Hardware", "Sweden", None, ("Skruvgatan 8", "553 03", "Jönköping")),
	("Möbelkomponenter i Småland AB", "Raw Material", "Sweden", None, ("Snickarvägen 21", "352 46", "Växjö")),
	("Förpackningshuset AB", "Local", "Sweden", None, ("Kartongvägen 5", "602 23", "Norrköping")),
	("Schweißtechnik Krüger GmbH", "Hardware", "Germany", "DE123456789", ("Hafenstraße 40", "24143", "Kiel")),
]

# Kunder: namn, land, momsregistreringsnummer (EU) och adress
KUNDER = [
	("Verkstadsservice i Västerås AB", "Sweden", None, ("Mekanikervägen 4", "723 48", "Västerås")),
	("Lagerlogistik Göteborg AB", "Sweden", None, ("Terminalgatan 17", "418 78", "Göteborg")),
	("Byggvaruhuset i Umeå AB", "Sweden", None, ("Handelsvägen 30", "906 20", "Umeå")),
	("Industrimontage Norrköping AB", "Sweden", None, ("Montörsgatan 9", "602 38", "Norrköping")),
	("Værkstedsudstyr Jensen ApS", "Denmark", "DK12345678", ("Industrivej 14", "8000", "Aarhus")),
]

# Råmaterial: kod, namn, enhet, inköpspris (kr), leverantör, ingående lager, beställningspunkt, beställningsmängd
RAMATERIAL = [
	("RM-PLAT-15", "Stålplåt DC01 1,5 mm", "Kg", 32, "Stålgrossisten i Mälardalen AB", 1500, 400, 1000),
	("RM-ROR-4040", "Fyrkantsrör 40x40x2 mm", "Meter", 55, "Stålgrossisten i Mälardalen AB", 300, 60, 240),
	("RM-PLATTST-405", "Plattstång 40x5 mm", "Meter", 28, "Stålgrossisten i Mälardalen AB", 100, 20, 60),
	("RM-PULVER-7035", "Pulverfärg RAL 7035 ljusgrå", "Kg", 120, "Pulverfärg Norden AB", 60, 15, 50),
	("RM-PULVER-9005", "Pulverfärg RAL 9005 svart", "Kg", 125, "Pulverfärg Norden AB", 25, 10, 25),
	("RM-SVETSTRAD-10", "Svetstråd SG2 1,0 mm", "Kg", 45, "Schweißtechnik Krüger GmbH", 30, 10, 30),
	("RM-SKRUV-M8", "Skruv M8x20 med mutter", "Nos", 1.2, "Fästelement i Jönköping AB", 2000, 500, 2000),
	("RM-STALLFOT-M10", "Ställfot M10", "Nos", 18, "Fästelement i Jönköping AB", 200, 40, 200),
	(
		"RM-BANKSKIVA-1206",
		"Bänkskiva björk 1200x600x40 mm",
		"Nos",
		650,
		"Möbelkomponenter i Småland AB",
		20,
		5,
		20,
	),
	("RM-EMBALLAGE", "Emballage wellpapp", "Nos", 35, "Förpackningshuset AB", 100, 30, 100),
]

# Halvfabrikat och färdiga produkter: kod, namn, artikelgrupp, försäljningspris, vikt (kg), fraktmått (kollityp, l, b, h)
TILLVERKADE = [
	("HF-HYLLPLAN-900", "Hyllplan 900x400 mm, lackat", "Sub Assemblies", None, 6.0, None),
	("HF-GAVEL-1800", "Gavel 1800x400 mm, svetsad och lackad", "Sub Assemblies", None, 9.0, None),
	("HF-BANKSTATIV-1200", "Bänkstativ 1200x600 mm, svetsat och lackat", "Sub Assemblies", None, 18.0, None),
	("HF-KONSOL-300", "Väggkonsol 300 mm, lackad", "Sub Assemblies", None, 1.3, None),
	("AB-1200", "Arbetsbänk AB-1200", "Products", 5900, 42.0, ("Pall", 130, 70, 95)),
	("LH-900", "Lagerhylla LH-900, 4 hyllplan", "Products", 4900, 46.0, ("Paket", 190, 45, 15)),
	("VH-600", "Vägghylla VH-600", "Products", 1290, 9.0, ("Paket", 95, 45, 8)),
]

# Stycklistor: material (kod, antal) och arbetsmoment (moment, minuter per styck)
STYCKLISTOR = {
	"HF-HYLLPLAN-900": (
		[("RM-PLAT-15", 6.6), ("RM-PULVER-7035", 0.15)],
		[("Laserskärning", 4), ("Kantpressning", 6), ("Pulverlackering", 5)],
	),
	"HF-GAVEL-1800": (
		[("RM-ROR-4040", 4.4), ("RM-PLATTST-405", 0.8), ("RM-SVETSTRAD-10", 0.08), ("RM-PULVER-7035", 0.25)],
		[("Kapning", 8), ("Svetsning", 20), ("Pulverlackering", 8)],
	),
	"HF-BANKSTATIV-1200": (
		[("RM-ROR-4040", 9.0), ("RM-SVETSTRAD-10", 0.15), ("RM-PULVER-9005", 0.4)],
		[("Kapning", 12), ("Svetsning", 35), ("Pulverlackering", 10)],
	),
	"HF-KONSOL-300": (
		[("RM-PLAT-15", 1.5), ("RM-PULVER-9005", 0.05)],
		[("Laserskärning", 2), ("Kantpressning", 2), ("Pulverlackering", 2)],
	),
	"AB-1200": (
		[
			("HF-BANKSTATIV-1200", 1),
			("RM-BANKSKIVA-1206", 1),
			("RM-STALLFOT-M10", 4),
			("RM-SKRUV-M8", 8),
			("RM-EMBALLAGE", 1),
		],
		[("Montering", 20), ("Packning", 10)],
	),
	"LH-900": (
		[("HF-GAVEL-1800", 2), ("HF-HYLLPLAN-900", 4), ("RM-SKRUV-M8", 16), ("RM-EMBALLAGE", 1)],
		[("Montering", 15), ("Packning", 10)],
	),
	"VH-600": (
		[("HF-KONSOL-300", 2), ("HF-HYLLPLAN-900", 1), ("RM-SKRUV-M8", 4), ("RM-EMBALLAGE", 1)],
		[("Montering", 5), ("Packning", 5)],
	),
}

TILLFALLIGT_KONTO = "Ingående balanser (tillfälligt)"


def skapa(company: str = "Exempelbolaget AB") -> dict:
	# Skydd mot produktion: bara sajter där tester är tillåtna (allow_tests i site_config)
	if not frappe.conf.get("allow_tests"):
		frappe.throw(_("Testdata läggs bara in på test- och demosajter (allow_tests i site_config)."))
	before = _antal()
	lager = _lager(company)
	_tillverkningslager(company, lager)
	_arbetsstationer()
	_leverantorer()
	_kunder()
	_artiklar(company, lager)
	_priser()
	_stycklistor(company)
	_ingaende_lager(company, lager)
	return {doctype: antal - before[doctype] for doctype, antal in _antal().items()}


def _antal() -> dict:
	return {
		dt: frappe.db.count(dt)
		for dt in ("Item", "BOM", "Workstation", "Operation", "Supplier", "Customer", "Stock Reconciliation")
	}


def _konto(company: str, nummer: str) -> str:
	return frappe.db.get_value("Account", {"company": company, "account_number": nummer, "is_group": 0})


def _hitta_lager(company: str, *namn) -> str:
	return frappe.db.get_value(
		"Warehouse", {"company": company, "warehouse_name": ("in", namn), "is_group": 0}
	)


def _lager(company: str) -> dict:
	"""ERPNext:s standardlager, kopplade till BAS-kontona för råvaror, produkter i arbete och färdiga varor."""
	lager = {
		"ravaror": _hitta_lager(company, "Lager", "Stores"),
		"pagaende": _hitta_lager(company, "Pågående", "Work In Progress"),
		"fardiga": _hitta_lager(company, "Färdigartiklar", "Finished Goods"),
	}
	for nyckel, nummer in (("ravaror", "1410"), ("pagaende", "1440"), ("fardiga", "1450")):
		if not lager[nyckel]:
			frappe.throw(_("Standardlagren saknas för {0}").format(company))
		if not frappe.db.get_value("Warehouse", lager[nyckel], "account") and (
			konto := _konto(company, nummer)
		):
			frappe.db.set_value("Warehouse", lager[nyckel], "account", konto)
	return lager


def _tillverkningslager(company: str, lager: dict) -> None:
	"""Lager för pågående tillverkning och färdiga produkter; i v16 ligger standardvärdena på bolaget."""
	for falt, nyckel in (("default_wip_warehouse", "pagaende"), ("default_fg_warehouse", "fardiga")):
		if not frappe.db.get_value("Company", company, falt):
			frappe.db.set_value("Company", company, falt, lager[nyckel])


def _arbetsstationer() -> None:
	for komponent in KOMPONENTER:
		if not frappe.db.exists("Workstation Operating Component", komponent):
			frappe.get_doc(
				{"doctype": "Workstation Operating Component", "component_name": komponent}
			).insert()
	for namn, (personal, el, forbrukning, hyra) in ARBETSSTATIONER.items():
		if not frappe.db.exists("Workstation", namn):
			frappe.get_doc(
				{
					"doctype": "Workstation",
					"workstation_name": namn,
					"production_capacity": 1,
					"workstation_costs": [
						{"operating_component": komponent, "operating_cost": kostnad}
						for komponent, kostnad in zip(
							KOMPONENTER, (personal, el, forbrukning, hyra), strict=True
						)
					],
				}
			).insert()
	for moment, station in MOMENT.items():
		if not frappe.db.exists("Operation", moment):
			frappe.get_doc({"doctype": "Operation", "__newname": moment, "workstation": station}).insert()


def _adress(titel, rad, postnr, ort, land, doctype, namn) -> None:
	if frappe.db.exists(
		"Dynamic Link", {"parenttype": "Address", "link_doctype": doctype, "link_name": namn}
	):
		return
	frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": titel,
			"address_type": "Billing",
			"address_line1": rad,
			"pincode": postnr,
			"city": ort,
			"country": land,
			"is_primary_address": 1,
			"is_shipping_address": 1,
			"links": [{"link_doctype": doctype, "link_name": namn}],
		}
	).insert()


def _orgnr(nio: str) -> str:
	"""Påhittat organisationsnummer med korrekt kontrollsiffra (Luhn)."""
	summa = 0
	for i, siffra in enumerate(nio):
		produkt = int(siffra) * (2 if i % 2 == 0 else 1)
		summa += produkt // 10 + produkt % 10
	return f"{nio[:6]}-{nio[6:]}{(10 - summa % 10) % 10}"


def _leverantorer() -> None:
	for i, (namn, grupp, land, momsnr, (rad, postnr, ort)) in enumerate(LEVERANTORER):
		if not frappe.db.exists("Supplier", namn):
			frappe.get_doc(
				{
					"doctype": "Supplier",
					"supplier_name": namn,
					"supplier_group": grupp,
					"supplier_type": "Company",
					"country": land,
					"tax_id": momsnr or _orgnr(f"55690{i:04d}"),
				}
			).insert()
		_adress(namn, rad, postnr, ort, land, "Supplier", namn)


def _kunder() -> None:
	for i, (namn, land, momsnr, (rad, postnr, ort)) in enumerate(KUNDER):
		if not frappe.db.exists("Customer", namn):
			frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": namn,
					"customer_type": "Company",
					"customer_group": "Commercial",
					"territory": "Sweden" if land == "Sweden" else "Rest Of The World",
					"tax_id": momsnr or _orgnr(f"55680{i:04d}"),
				}
			).insert()
		_adress(namn, rad, postnr, ort, land, "Customer", namn)


def _artiklar(company: str, lager: dict) -> None:
	for kod, namn, enhet, pris, leverantor, _ingaende, punkt, mangd in RAMATERIAL:
		if frappe.db.exists("Item", kod):
			continue
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": kod,
				"item_name": namn,
				"item_group": "Raw Material",
				"stock_uom": enhet,
				"is_stock_item": 1,
				"include_item_in_manufacturing": 1,
				"is_purchase_item": 1,
				"is_sales_item": 0,
				"valuation_rate": pris,
				"se_goods_or_service": GOODS,
				"lead_time_days": 5,
				"item_defaults": [
					{
						"company": company,
						"default_warehouse": lager["ravaror"],
						"default_supplier": leverantor,
					}
				],
				"supplier_items": [{"supplier": leverantor}],
				"reorder_levels": [
					{
						"warehouse": lager["ravaror"],
						"warehouse_reorder_level": punkt,
						"warehouse_reorder_qty": mangd,
						"material_request_type": "Purchase",
					}
				],
			}
		).insert()

	for kod, namn, grupp, _pris, vikt, frakt in TILLVERKADE:
		if frappe.db.exists("Item", kod):
			continue
		produkt = grupp == "Products"
		doc = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": kod,
				"item_name": namn,
				"item_group": grupp,
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"include_item_in_manufacturing": 1,
				"is_purchase_item": 0,
				"is_sales_item": int(produkt),
				"default_material_request_type": "Manufacture",
				"se_goods_or_service": GOODS,
				"weight_per_unit": vikt,
				"weight_uom": "Kg",
				"item_defaults": [
					{"company": company, "default_warehouse": lager["fardiga" if produkt else "ravaror"]}
				],
			}
		)
		if frakt:
			kollityp, langd, bredd, hojd = frakt
			doc.update(
				{
					"fraktsatt": "Egna mått",
					"frakt_kollityp": kollityp,
					"frakt_langd_cm": langd,
					"frakt_bredd_cm": bredd,
					"frakt_hojd_cm": hojd,
				}
			)
		doc.insert()


def _priser() -> None:
	for kod, _namn, enhet, pris, leverantor, *_resten in RAMATERIAL:
		if not frappe.db.exists("Item Price", {"item_code": kod, "price_list": "Standard Buying"}):
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"item_code": kod,
					"price_list": "Standard Buying",
					"price_list_rate": pris,
					"uom": enhet,
					"supplier": leverantor,
				}
			).insert()
	for kod, _namn, _grupp, pris, *_resten in TILLVERKADE:
		if pris and not frappe.db.exists("Item Price", {"item_code": kod, "price_list": "Standard Selling"}):
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"item_code": kod,
					"price_list": "Standard Selling",
					"price_list_rate": pris,
				}
			).insert()


def _stycklistor(company: str) -> None:
	# Halvfabrikaten först: deras kostnad ingår i produkternas stycklistor
	for kod, (material, moment) in STYCKLISTOR.items():
		if frappe.db.exists("BOM", {"item": kod, "docstatus": 1, "company": company}):
			continue
		bom = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": kod,
				"company": company,
				"quantity": 1,
				"with_operations": 1,
				"rm_cost_as_per": "Valuation Rate",
				"items": [{"item_code": artikel, "qty": antal} for artikel, antal in material],
				"operations": [
					{"operation": namn, "workstation": MOMENT[namn], "time_in_mins": minuter}
					for namn, minuter in moment
				],
			}
		)
		bom.insert()
		bom.submit()
		# Halvfabrikatens värde = stycklistans kostnad, så att produkternas stycklistor räknar rätt
		frappe.db.set_value("Item", kod, "valuation_rate", bom.total_cost / bom.quantity)


def _tillfalligt_konto(company: str) -> str:
	namn = frappe.db.get_value("Account", {"company": company, "account_name": TILLFALLIGT_KONTO})
	if namn:
		return namn
	tillgangar = frappe.db.get_value(
		"Account",
		{"company": company, "root_type": "Asset", "is_group": 1, "parent_account": ("in", ("", None))},
	)
	return (
		frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": TILLFALLIGT_KONTO,
				"company": company,
				"parent_account": tillgangar,
				"account_type": "Temporary",
				"root_type": "Asset",
				"report_type": "Balance Sheet",
			}
		)
		.insert()
		.name
	)


def _ingaende_lager(company: str, lager: dict) -> None:
	koder = [rad[0] for rad in RAMATERIAL]
	if frappe.db.exists("Stock Ledger Entry", {"item_code": ("in", koder), "is_cancelled": 0}):
		return
	sr = frappe.get_doc(
		{
			"doctype": "Stock Reconciliation",
			"company": company,
			"purpose": "Opening Stock",
			"posting_date": nowdate(),
			"expense_account": _tillfalligt_konto(company),
			"cost_center": frappe.get_cached_value("Company", company, "cost_center"),
			"items": [
				{"item_code": kod, "warehouse": lager["ravaror"], "qty": antal, "valuation_rate": pris}
				for kod, _namn, _enhet, pris, _lev, antal, *_resten in RAMATERIAL
			],
		}
	)
	sr.insert()
	sr.submit()
