"""Underlag till årsarkivet (bokföringslagen 7 kap.): en SIE 4-fil per bolag och räkenskapsår.

Körs av backup/erpnext-backup.sh:

    bench --site <site> execute erpnext_sverige.arkiv.skriv_sie_filer --kwargs "{'katalog': '/tmp/x', 'ar': 2026}"
"""

import os

import frappe

from erpnext_sverige.sweden_compliance.sie_export import build_sie


def skriv_sie_filer(katalog: str, ar: int) -> list[str]:
	"""Skriv SIE-filer för räkenskapsår som slutar under år `ar`. Returnerar sökvägarna."""
	os.makedirs(katalog, exist_ok=True)
	ar = int(ar)
	fiscal_years = frappe.get_all(
		"Fiscal Year",
		filters={"year_end_date": ["between", [f"{ar}-01-01", f"{ar}-12-31"]], "disabled": 0},
		pluck="name",
	)
	paths = []
	for fiscal_year in fiscal_years:
		companies = frappe.get_all(
			"Fiscal Year Company", filters={"parent": fiscal_year}, pluck="company"
		) or frappe.get_all("Company", pluck="name")
		for company in companies:
			path = os.path.join(katalog, f"{frappe.scrub(company)}-{frappe.scrub(fiscal_year)}.se")
			with open(path, "wb") as f:
				f.write(build_sie(company, fiscal_year))
			paths.append(path)
	for path in paths:
		print(path)
	return paths
