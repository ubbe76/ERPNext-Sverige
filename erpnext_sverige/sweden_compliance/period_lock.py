"""Låsning av bokföringen efter momsdeklaration.

En deklarerad period ska inte kunna ändras i efterhand. "Lås perioden" i rapporten Momsdeklaration sätter
bolagets "Accounts Frozen Till Date": därefter stoppar ERPNext all bokföring, ändring och makulering med
datum till och med låsdatumet, även för Administrator. Bara rollen i "Roles Allowed to Set and Edit Frozen
Account Entries" på bolaget undantas, om en sådan är vald.
"""

import frappe
from frappe import _
from frappe.utils import formatdate, getdate, today

LOCK_ROLES = ("Accounts Manager", "System Manager")
# Dokument som bokförs med posting_date. Ett utkast i en låst period kan aldrig bokföras.
DRAFT_DOCTYPES = (
	"Sales Invoice",
	"Purchase Invoice",
	"Journal Entry",
	"Payment Entry",
	"Delivery Note",
	"Purchase Receipt",
	"Stock Entry",
)


@frappe.whitelist()
def las_period(company: str, to_date: str) -> str:
	"""Lås bolagets bokföring till och med `to_date`. Flyttar aldrig ett befintligt låsdatum bakåt."""
	frappe.only_for(LOCK_ROLES)
	to_date = getdate(to_date)
	if to_date > getdate(today()):
		frappe.throw(_("Det går inte att låsa en period som inte är slut"))
	from erpnext_sverige.sweden_compliance.vat_return import kontrollera_periodslut

	kontrollera_periodslut(company, to_date)

	current = frappe.db.get_value("Company", company, "accounts_frozen_till_date")
	if current and getdate(current) >= to_date:
		return _("Bokföringen är redan låst till och med {0}").format(formatdate(current))

	drafts = utkast_i_perioden(company, to_date)
	if drafts:
		frappe.throw(
			_("Bokför eller ta bort utkasten med datum till och med {0} först: {1}").format(
				formatdate(to_date), ", ".join(drafts[:10]) + (" …" if len(drafts) > 10 else "")
			),
			title=_("Det finns utkast i perioden"),
		)

	doc = frappe.get_doc("Company", company)
	doc.accounts_frozen_till_date = to_date
	doc.save()
	return _("Bokföringen är låst till och med {0}").format(formatdate(to_date))


def utkast_i_perioden(company: str, to_date) -> list[str]:
	drafts = []
	for doctype in DRAFT_DOCTYPES:
		drafts += frappe.get_all(
			doctype,
			filters={"company": company, "docstatus": 0, "posting_date": ["<=", to_date]},
			pluck="name",
		)
	return drafts
