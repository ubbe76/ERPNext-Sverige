"""SIE 4-export av bokföringen för ett räkenskapsår.

Filen innehåller bolagsuppgifter, kontoplan, dimensioner (resultatenheter som dimension 1, projekt som
dimension 6), ingående/utgående balanser, periodens resultat och alla verifikationer med rader.
Teckenkodning PC8 (IBM codepage 437), belopp med punkt som decimaltecken, debet positivt.

Verifikationsserier per dokumenttyp:
A verifikationer, B kundfakturor, C leverantörsfakturor, D betalningar, E lager, F övrigt.
Numren löper i datumordning inom varje serie. ERPNext-namnet följer med i verifikationstexten.
Bokslutsverifikationer (Period Closing Voucher) exporteras inte; mottagande program gör eget bokslut.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime

import erpnext_sverige

SIE_ENCODING = "cp437"  # "PC8"
CANCELLATION_PREFIX = "On cancellation of"

SERIES = {
	"Journal Entry": ("A", "Verifikationer"),
	"Sales Invoice": ("B", "Kundfakturor"),
	"POS Invoice": ("B", "Kundfakturor"),
	"Purchase Invoice": ("C", "Leverantörsfakturor"),
	"Payment Entry": ("D", "Betalningar"),
	"Stock Entry": ("E", "Lager"),
	"Delivery Note": ("E", "Lager"),
	"Purchase Receipt": ("E", "Lager"),
	"Stock Reconciliation": ("E", "Lager"),
}
OTHER_SERIES = ("F", "Övrigt")

ACCOUNT_TYPE = {"Asset": "T", "Liability": "S", "Equity": "S", "Income": "I", "Expense": "K"}
BALANCE_SHEET = {"Asset", "Liability", "Equity"}
DIM_COST_CENTER = 1
DIM_PROJECT = 6


@dataclass
class Voucher:
	series: str
	date: object
	voucher_type: str
	voucher_no: str
	text: str
	reg_date: object
	rows: list = field(default_factory=list)
	number: int = 0


def build_sie(company: str, fiscal_year: str) -> bytes:
	start, end = frappe.db.get_value("Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"])
	accounts = _get_accounts(company)
	lines = _header(company, start, end)

	previous = _previous_fiscal_year(start)
	if previous:
		lines.append(f"#RAR -1 {_date(previous[0])} {_date(previous[1])}")
	lines.append(f"#KPTYP {_quote('BAS2024')}")
	lines.append(f"#VALUTA {frappe.get_cached_value('Company', company, 'default_currency')}")

	for number, account in sorted(accounts.items()):
		lines.append(f"#KONTO {number} {_quote(account.account_name)}")
		lines.append(f"#KTYP {number} {ACCOUNT_TYPE.get(account.root_type, 'K')}")

	cost_centers, projects = _get_objects(company)
	lines.append(f"#DIM {DIM_COST_CENTER} {_quote('Kostnadsställe')}")
	lines.append(f"#DIM {DIM_PROJECT} {_quote('Projekt')}")
	lines += [
		f"#OBJEKT {DIM_COST_CENTER} {_quote(oid)} {_quote(name)}" for oid, name in cost_centers.values()
	]
	lines += [f"#OBJEKT {DIM_PROJECT} {_quote(oid)} {_quote(name)}" for oid, name in projects.values()]

	years = [(0, start, end)] + ([(-1, previous[0], previous[1])] if previous else [])
	for index, year_start, year_end in years:
		lines += _balances(company, accounts, index, year_start, year_end)

	for voucher in get_vouchers(company, start, end, accounts, cost_centers, projects):
		lines.append(
			f"#VER {voucher.series} {voucher.number} {_date(voucher.date)} {_quote(voucher.text)} "
			f"{_date(voucher.reg_date)}"
		)
		lines.append("{")
		for number, objects, amount in voucher.rows:
			lines.append(f"   #TRANS {number} {{{objects}}} {_amount(amount)}")
		lines.append("}")

	return ("\r\n".join(lines) + "\r\n").encode(SIE_ENCODING, errors="replace")


def _header(company: str, start, end) -> list[str]:
	org_nr = format_sie_org_nr(frappe.get_cached_value("Company", company, "tax_id"))
	lines = [
		"#FLAGGA 0",
		f"#PROGRAM {_quote('ERPNext Sverige')} {_quote(erpnext_sverige.__version__)}",
		"#FORMAT PC8",
		f"#GEN {_date(now_datetime())} {_quote(frappe.session.user)}",
		"#SIETYP 4",
		f"#FNAMN {_quote(company)}",
	]
	if org_nr:
		lines.append(f"#ORGNR {org_nr}")
	lines.append(f"#RAR 0 {_date(start)} {_date(end)}")
	return lines


def _balances(company: str, accounts: dict, index: int, start, end) -> list[str]:
	"""#IB/#UB för balanskonton och #RES för resultatkonton."""
	opening = _sum_by_account(company, "gle.posting_date < %(start)s", start, end)
	movement = _sum_by_account(company, "gle.posting_date between %(start)s and %(end)s", start, end)
	result = _sum_by_account(
		company,
		"gle.posting_date between %(start)s and %(end)s and gle.voucher_type != 'Period Closing Voucher'",
		start,
		end,
	)

	lines = []
	for number, account in sorted(accounts.items()):
		if account.root_type in BALANCE_SHEET:
			ib = opening.get(number, 0)
			ub = ib + movement.get(number, 0)
			if flt(ib, 2):
				lines.append(f"#IB {index} {number} {_amount(ib)}")
			if flt(ub, 2):
				lines.append(f"#UB {index} {number} {_amount(ub)}")
		elif flt(result.get(number, 0), 2):
			lines.append(f"#RES {index} {number} {_amount(result[number])}")
	return lines


def _sum_by_account(company: str, condition: str, start, end) -> dict[str, float]:
	rows = frappe.db.sql(
		f"""
		select acc.account_number, sum(gle.debit) - sum(gle.credit) as balance
		from `tabGL Entry` gle
		join `tabAccount` acc on acc.name = gle.account
		where gle.company = %(company)s and gle.is_cancelled = 0 and {condition}
		group by acc.account_number
		""",
		{"company": company, "start": start, "end": end},
		as_dict=True,
	)
	return {row.account_number: flt(row.balance) for row in rows if row.account_number}


def get_vouchers(company: str, start, end, accounts=None, cost_centers=None, projects=None) -> list[Voucher]:
	"""Verifikationer med rader, numrerade per serie i datumordning."""
	accounts = accounts or _get_accounts(company)
	if cost_centers is None or projects is None:
		cost_centers, projects = _get_objects(company)
	number_by_account = {account.name: number for number, account in accounts.items()}

	entries = frappe.db.sql(
		"""
		select gle.voucher_type, gle.voucher_no, gle.posting_date, gle.account, gle.debit, gle.credit,
			gle.cost_center, gle.project, gle.party, gle.remarks, gle.creation
		from `tabGL Entry` gle
		where gle.company = %(company)s and gle.is_cancelled = 0
			and gle.posting_date between %(start)s and %(end)s
			and gle.voucher_type != 'Period Closing Voucher'
		order by gle.posting_date, gle.creation, gle.name
		""",
		{"company": company, "start": start, "end": end},
		as_dict=True,
	)

	vouchers: dict[tuple, Voucher] = {}
	missing_numbers = set()
	for entry in entries:
		cancellation = (entry.remarks or "").startswith(CANCELLATION_PREFIX)
		key = (entry.voucher_type, entry.voucher_no, entry.posting_date, cancellation)
		voucher = vouchers.get(key)
		if not voucher:
			series = SERIES.get(entry.voucher_type, OTHER_SERIES)[0]
			text = f"{entry.voucher_no} {entry.party or ''}".strip()
			if cancellation:
				text = f"Makulering av {text}"
			voucher = vouchers[key] = Voucher(
				series, entry.posting_date, entry.voucher_type, entry.voucher_no, text, entry.creation
			)

		number = number_by_account.get(entry.account)
		if not number:
			missing_numbers.add(entry.account)
			continue
		objects = []
		if entry.cost_center in cost_centers:
			objects.append(f"{DIM_COST_CENTER} {_quote(cost_centers[entry.cost_center][0])}")
		if entry.project in projects:
			objects.append(f"{DIM_PROJECT} {_quote(projects[entry.project][0])}")
		voucher.rows.append((number, " ".join(objects), flt(entry.debit) - flt(entry.credit)))

	if missing_numbers:
		frappe.throw(
			_("Följande konton saknar kontonummer och kan inte exporteras till SIE: {0}").format(
				", ".join(sorted(missing_numbers))
			)
		)

	counters = defaultdict(int)
	result = []
	for voucher in sorted(vouchers.values(), key=lambda v: (v.date, v.reg_date)):
		counters[voucher.series] += 1
		voucher.number = counters[voucher.series]
		result.append(voucher)
	return result


def _get_accounts(company: str) -> dict:
	rows = frappe.get_all(
		"Account",
		filters={"company": company, "is_group": 0},
		fields=["name", "account_number", "account_name", "root_type"],
	)
	return {row.account_number: row for row in rows if row.account_number}


def _get_objects(company: str) -> tuple[dict, dict]:
	"""Resultatenheter och projekt: namn -> (objekt-id, benämning)."""
	cost_centers = {
		row.name: (row.cost_center_number or row.cost_center_name, row.cost_center_name)
		for row in frappe.get_all(
			"Cost Center",
			filters={"company": company, "is_group": 0},
			fields=["name", "cost_center_name", "cost_center_number"],
		)
	}
	projects = {
		row.name: (row.name, row.project_name or row.name)
		for row in frappe.get_all("Project", filters={"company": company}, fields=["name", "project_name"])
	}
	return cost_centers, projects


def _previous_fiscal_year(start):
	return frappe.db.get_value(
		"Fiscal Year",
		{"year_end_date": ["<", start]},
		["year_start_date", "year_end_date"],
		order_by="year_end_date desc",
	)


def format_sie_org_nr(tax_id: str | None) -> str | None:
	"""Organisationsnummer som NNNNNN-NNNN."""
	value = (tax_id or "").strip().upper()
	digits = re.sub(r"\D", "", value)
	if value.startswith("SE") and len(digits) == 12 and digits.endswith("01"):
		digits = digits[:10]
	if len(digits) == 12:
		digits = digits[2:]
	if len(digits) != 10:
		return None
	return f"{digits[:6]}-{digits[6:]}"


def _quote(value) -> str:
	text = re.sub(r"[\r\n\t]+", " ", str(value or "")).replace("\\", "\\\\").replace('"', '\\"')
	return f'"{text}"'


def _date(value) -> str:
	return getdate(value).strftime("%Y%m%d")


def _amount(value) -> str:
	return f"{flt(value, 2):.2f}"


@frappe.whitelist()
def download_sie(company: str, fiscal_year: str):
	frappe.has_permission("GL Entry", "read", throw=True)
	safe_company = re.sub(r"[^A-Za-z0-9_-]+", "_", company).strip("_")
	frappe.response["filename"] = f"{safe_company}-{fiscal_year}.se"
	frappe.response["filecontent"] = build_sie(company, fiscal_year)
	frappe.response["type"] = "download"
