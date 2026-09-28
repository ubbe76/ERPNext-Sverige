# Svenska utskriftsmallar – design

## Bakgrund

Försäljningsorder skrivs i dag ut med ERPNext:s "Sales Order with Item Image". Mallen har hårdkodade engelska
etiketter ("Customer Name:", "Bill to:"), en kolumnrubrik `_("No")` som översätts till "Nej", skriver ut
enhetens namn oöversatt ("Nos") och visar ett felformaterat belopp i ord. Samma sorts mallar är förvalda för
offert, följesedel och inköpsorder.

Kundfakturan har redan en egen svensk mall, "Faktura Sverige" (`sweden_compliance/print_format/faktura_sverige`),
som är förvald via `setup/custom_fields.py`.

## Mål

- Svenska utskriftsmallar för **Offert** (Quotation), **Orderbekräftelse** (Sales Order), **Följesedel**
  (Delivery Note) och **Inköpsorder** (Purchase Order), med samma utseende som "Faktura Sverige".
- Inga engelska rester i utskriften på svenska.
- Mallarna förvalda för sina dokumenttyper.
- "Faktura Sverige" byggs om på samma byggstenar utan att dess utskrift ändras.

Utanför: belopp i ord (utelämnas på alla mallar, som på fakturan), betalningsuppgifter på andra dokument än
fakturan, momssammanställning per skattesats för inköp.

## Struktur

### Gemensamma makron – `erpnext_sverige/templates/includes/se_print.html`

Jinja-makron som varje mall importerar med
`{% from "erpnext_sverige/templates/includes/se_print.html" import … %}`:

| Makro | Innehåll |
|---|---|
| `styles()` | CSS (`.se-*`), flyttad oförändrad från fakturamallen |
| `header(title, meta_rows, party_label, party_name, address, vat_no, extra)` | Titel och etikett/värde-rader till vänster, part och adress till höger. `meta_rows` är en lista `[(etikett, värde)]`; rader med tomt värde hoppas över. `extra` är en valfri lista `[(etikett, adress)]` under parten, t.ex. leveransadress |
| `items(doc, show_prices)` | Artikeltabell: Beskrivning, Antal, Enhet (`_(item.uom)`), och med priser även À-pris och Belopp |
| `totals(doc, ctx, total_label)` | Summa exkl. moms, moms per sats (`ctx.vat_summary`) eller en momsrad, avrundning, totalt, moms i SEK vid utländsk valuta |
| `notes(ctx)` | Undantagstexter (EU/export) |
| `footer(doc, ctx, show_payment)` | Bolag och adress, organisationsnummer, momsregistreringsnummer, F-skatt; betalningsuppgifter om `show_payment` |

### Kontext – `erpnext_sverige/sweden_compliance/print_context.py`

`get_print_context(doc) -> dict`, registreras i `hooks.py` under `jinja.methods`. Innehåll:

- `org_nr`, `vat_no`, `f_skatt` – från bolaget (flyttar `format_org_nr`, `vat_number` hit eller importerar dem)
- `payment` – `get_payment_details(doc.company)`
- `vat_summary` – `get_vat_summary(doc)` för försäljningsdokument (utgående moms, konton 2611/2621/2631),
  tom lista för Purchase Order
- `notes` – `get_exemption_notes(doc)` för Quotation, Sales Order och Sales Invoice, annars tom
- `customer_vat_no` – kundens momsnummer när parten är en Customer

`get_invoice_context(doc)` i `invoice.py` finns kvar med samma returvärde (lägger till `ocr`), så att befintliga
anrop och tester fungerar.

### Mallar – `erpnext_sverige/sweden_compliance/print_format/<namn>/`

Var och en med `<namn>.json` (`standard: Yes`, `custom_format: 1`, `print_format_type: Jinja`,
`default_print_language: sv`, `module: Sweden Compliance`) och `<namn>.html`.

| Katalog | Namn | Doctype |
|---|---|---|
| `faktura_sverige` | Faktura Sverige | Sales Invoice (ombyggd) |
| `offert_sverige` | Offert Sverige | Quotation |
| `orderbekraftelse_sverige` | Orderbekräftelse Sverige | Sales Order |
| `foljesedel_sverige` | Följesedel Sverige | Delivery Note |
| `inkopsorder_sverige` | Inköpsorder Sverige | Purchase Order |

## Innehåll per dokument

| | Offert | Orderbekräftelse | Följesedel | Inköpsorder |
|---|---|---|---|---|
| Titel | Offert | Orderbekräftelse | Följesedel | Inköpsorder |
| Rader vänster | Offertnr, Datum (`transaction_date`), Giltig till (`valid_till`), Er referens, Kundnr (bara om `quotation_to == "Customer"`) | Ordernr, Orderdatum, Leveransdatum (`delivery_date`), Er referens, Ert ordernr (`po_no`), Kundnr | Följesedelsnr, Datum (`posting_date`), Ordernr (unika `items.against_sales_order`), Er referens, Ert ordernr (`po_no`), Transportör (`transporter_name`), Fraktsedelsnr (`lr_no`) | Inköpsordernr, Datum, Önskat leveransdatum (`schedule_date`), Leverantörsnr |
| Höger | Kund (`customer_name`), `address_display`, kundens momsnr | Kund, `address_display`, kundens momsnr; leveransadress (`shipping_address_display`) om den skiljer sig | Leveransadress (`shipping_address_display`, annars `address_display`) med kundnamn | Leverantör (`supplier_name`), `address_display`; vår leveransadress (`shipping_address_display`) |
| Priser | Ja | Ja | Nej | Ja |
| Summor | Per momssats | Per momssats | – | En momsrad (`total_taxes_and_charges`) |
| Undantagstext | Ja | Ja | Nej | Nej |
| Betalning i sidfot | Nej | Nej | Nej | Nej |

**Er referens** är kundens kontaktperson (`contact_display`) och **Ert ordernr** är kundens eget ordernummer
(`po_no`), på alla försäljningsdokument. Fakturan ändras på samma sätt: dagens rad "Er referens" (`po_no`)
byter etikett till "Ert ordernr" och en rad "Er referens" (`contact_display`) läggs till. I övrigt ska fakturans
utskrift vara oförändrad.

Villkor (`doc.terms`) skrivs ut under tabellen när de finns. Brevhuvud visas som på fakturan
(`letter_head and not no_letterhead`).

## Standardmallar

`set_default_invoice_print_format()` i `setup/custom_fields.py` ersätts av `set_default_print_formats()`, som
går igenom `PRINT_FORMATS = {doctype: mallnamn}` och för varje doctype sätter `default_print_format` via
Property Setter – om mallen finns och nuvarande standardmall saknas, är en standardmall (`standard == "Yes"`)
eller redan är vår. En egen (icke-standard) mall lämnas orörd. Körs vid `after_install` och `after_migrate`.

## Felhantering

- Tomma fält (organisationsnummer, bankkonto, adress, referenser) ger ingen rad – inga fel.
- Ingen kontaktperson eller inget ordernummer: raden utelämnas.
- Offert till Lead: inget kundnummer och inget kundmomsnummer.
- Utländsk valuta: belopp i dokumentvalutan, momsen även i bolagets valuta (som fakturan).

## Översättningar

Nya etiketter skrivs på engelska i `_()` och översätts i `erpnext_sverige/locale/sv.po` (t.ex. "Quotation No",
"Valid Till", "Delivery Note No", "Carrier", "Waybill No", "Your Order No"). Tänk på att Frappe trimmar blanksteg före uppslag.

## Tester – `erpnext_sverige/tests/test_print_formats.py`

För varje ny mall: skapa dokumentet, rendera med `frappe.get_print(doctype, name, print_format=…, doc=doc)` med
`frappe.local.lang = "sv"`, och kontrollera:

- titel och svenska rubriker finns ("Offert", "Giltig till", "Leveransdatum", …)
- inga engelska rester ("Customer Name", "Bill to", "Nos", ">Item<")
- följesedeln saknar À-pris och belopp
- inköpsordern visar leverantörens namn och en momsrad
- `set_default_print_formats()` sätter rätt mall och lämnar en egen mall orörd

`test_invoice.py` och `test_credit_notes.py` ska passera oförändrade. Fakturans renderade text jämförs före och
efter ombyggnaden; den enda tillåtna skillnaden är referensraderna ovan.

## Verifiering

Rendera `SAL-ORD-2026-00001` på svensk-erp.local med "Orderbekräftelse Sverige" och jämför med skärmbilden
från 2026-09-28.
