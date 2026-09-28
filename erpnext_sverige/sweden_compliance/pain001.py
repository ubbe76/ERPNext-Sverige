"""Betalfil för leverantörsbetalningar enligt ISO 20022 pain.001.001.03 (Customer Credit Transfer Initiation).

Mottagarkonto enligt de svenska bankernas implementeringsanvisningar:
- Bankgiro:   CdtrAcct/Othr/Id = bankgironummer, SchmeNm/Prtry = BGNR; CdtrAgt ClrSysMmbId SESBA 9900
- Plusgiro:   CdtrAcct/Othr/Id = plusgironummer, SchmeNm/Cd = BBAN; CdtrAgt ClrSysMmbId SESBA 9960
- Bankkonto:  CdtrAcct/Othr/Id = clearing + kontonummer, SchmeNm/Cd = BBAN; CdtrAgt ClrSysMmbId SESBA <clearing>
- IBAN:       CdtrAcct/IBAN och CdtrAgt/BIC
Betalningsreferens: OCR som strukturerad referens (SCOR), annars fakturanummer som fritext.

Verifiera mot den egna bankens implementeringsanvisning för pain.001 innan skarp användning.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from xml.etree import ElementTree as ET

NAMESPACE = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"

BANKGIRO = "Bankgiro"
PLUSGIRO = "Plusgiro"
BANK_ACCOUNT = "Bankkonto"
IBAN = "IBAN"


@dataclass
class Creditor:
	name: str
	method: str  # BANKGIRO, PLUSGIRO, BANK_ACCOUNT eller IBAN
	account: str  # bankgiro-/plusgironummer, clearing+konto eller IBAN
	clearing: str = ""
	bic: str = ""


@dataclass
class Transfer:
	end_to_end_id: str
	amount: float
	creditor: Creditor
	ocr: str = ""
	invoice_number: str = ""


@dataclass
class Debtor:
	name: str
	iban: str = ""
	bic: str = ""
	clearing: str = ""
	account_no: str = ""
	org_nr: str = ""


def digits(value: str | None) -> str:
	return re.sub(r"\D", "", value or "")


def build_pain001(message_id: str, debtor: Debtor, execution_date: date, transfers: list[Transfer]) -> bytes:
	ET.register_namespace("", NAMESPACE)
	document = ET.Element(f"{{{NAMESPACE}}}Document")
	root = _sub(document, "CstmrCdtTrfInitn")
	total = f"{sum(round(t.amount, 2) for t in transfers):.2f}"

	header = _sub(root, "GrpHdr")
	_sub(header, "MsgId", message_id[:35])
	_sub(header, "CreDtTm", datetime.now().replace(microsecond=0).isoformat())
	_sub(header, "NbOfTxs", str(len(transfers)))
	_sub(header, "CtrlSum", total)
	initiator = _sub(header, "InitgPty")
	_sub(initiator, "Nm", debtor.name[:70])
	if debtor.org_nr:
		other = _sub(_sub(_sub(initiator, "Id"), "OrgId"), "Othr")
		_sub(other, "Id", digits(debtor.org_nr))
		_sub(_sub(other, "SchmeNm"), "Cd", "BANK")

	info = _sub(root, "PmtInf")
	_sub(info, "PmtInfId", f"{message_id}-1"[:35])
	_sub(info, "PmtMtd", "TRF")
	_sub(info, "NbOfTxs", str(len(transfers)))
	_sub(info, "CtrlSum", total)
	_sub(_sub(_sub(info, "PmtTpInf"), "SvcLvl"), "Cd", "NURG")
	_sub(info, "ReqdExctnDt", execution_date.isoformat())
	_sub(_sub(info, "Dbtr"), "Nm", debtor.name[:70])

	debtor_account = _sub(_sub(info, "DbtrAcct"), "Id")
	if debtor.iban:
		_sub(debtor_account, "IBAN", debtor.iban.replace(" ", "").upper())
	else:
		other = _sub(debtor_account, "Othr")
		_sub(other, "Id", digits(debtor.clearing) + digits(debtor.account_no))
		_sub(_sub(other, "SchmeNm"), "Cd", "BBAN")
	debtor_agent = _sub(_sub(info, "DbtrAgt"), "FinInstnId")
	if debtor.bic:
		_sub(debtor_agent, "BIC", debtor.bic.upper())
	else:
		_clearing(debtor_agent, digits(debtor.clearing)[:4])

	for transfer in transfers:
		_transfer(info, transfer)

	ET.indent(document)
	return ET.tostring(document, encoding="UTF-8", xml_declaration=True)


def _transfer(info, transfer: Transfer):
	tx = _sub(info, "CdtTrfTxInf")
	payment_id = _sub(tx, "PmtId")
	_sub(payment_id, "InstrId", transfer.end_to_end_id[:35])
	_sub(payment_id, "EndToEndId", transfer.end_to_end_id[:35])
	_sub(_sub(tx, "Amt"), "InstdAmt", f"{round(transfer.amount, 2):.2f}", Ccy="SEK")

	creditor = transfer.creditor
	agent = _sub(_sub(tx, "CdtrAgt"), "FinInstnId")
	if creditor.method == IBAN and creditor.bic:
		_sub(agent, "BIC", creditor.bic.upper())
	elif creditor.method == BANKGIRO:
		_clearing(agent, "9900")
	elif creditor.method == PLUSGIRO:
		_clearing(agent, "9960")
	elif creditor.method == BANK_ACCOUNT:
		_clearing(agent, digits(creditor.clearing)[:4])

	_sub(_sub(tx, "Cdtr"), "Nm", creditor.name[:70])
	account = _sub(_sub(tx, "CdtrAcct"), "Id")
	if creditor.method == IBAN:
		_sub(account, "IBAN", creditor.account.replace(" ", "").upper())
	else:
		other = _sub(account, "Othr")
		_sub(other, "Id", digits(creditor.account))
		scheme = _sub(other, "SchmeNm")
		if creditor.method == BANKGIRO:
			_sub(scheme, "Prtry", "BGNR")
		else:
			_sub(scheme, "Cd", "BBAN")

	remittance = _sub(tx, "RmtInf")
	if transfer.ocr:
		reference = _sub(_sub(remittance, "Strd"), "CdtrRefInf")
		_sub(_sub(_sub(reference, "Tp"), "CdOrPrtry"), "Cd", "SCOR")
		_sub(reference, "Ref", digits(transfer.ocr))
	else:
		_sub(remittance, "Ustrd", (transfer.invoice_number or transfer.end_to_end_id)[:140])


def _clearing(parent, member_id: str):
	clearing = _sub(parent, "ClrSysMmbId")
	_sub(_sub(clearing, "ClrSysId"), "Cd", "SESBA")
	_sub(clearing, "MmbId", member_id)


def _sub(parent, tag: str, text: str | None = None, **attributes):
	element = ET.SubElement(parent, f"{{{NAMESPACE}}}{tag}", attributes)
	if text is not None:
		element.text = text
	return element
