# TODO

Siten `svensk-erp.local`, bolag **BOLAG** (SEK, kontoplan BAS 2024 med nummer).
Inga transaktioner är bokförda ännu. Gör klart steg 1 innan första verifikationen.

## 1. Bokföringsgrund (innan första verifikationen)

- [ ] Sätt standardkonton som saknas på bolaget BOLAG:
  - [ ] Standard kostnadskonto (t.ex. 4010 eller 4000)
  - [ ] Konto för valutakursvinst/-förlust (3960 / 7960)
  - [ ] Avskrivningskonto för småbelopp/write-off (t.ex. 3740 eller 6990)
  - [ ] Rabattkonto
- [ ] Aktivera **Immutable Ledger** i Bokföringsinställningar (Bokföringslagen: verifikationer får inte ändras, bara rättas)
- [ ] Moms utöver "Svensk moms":
  - [ ] Momskategori och mallar för omvänd skattskyldighet vid EU-försäljning/-inköp
  - [ ] Momsfri export utanför EU
  - [ ] Skatteregler (Tax Rule) som väljer rätt mall utifrån kundens/leverantörens land

## 2. Provkör ett helt flöde

- [ ] Kundfaktura → betalning → kontrollera huvudbok och momskonton (2611, 2641, 2650)
- [ ] Leverantörsfaktura → betalning → kontrollera samma sak

## 3. Funktioner i erpnext_sverige

1. [ ] **SIE-export (SIE 4)**: för revisor och bokslutsprogram
2. [ ] **Momsdeklaration**: summera Skatteverkets rutor (05, 10, 20, 30, 48 …) från huvudboken
3. [ ] **Fakturakrav**: utskriftsmall med organisationsnummer, momsregistreringsnummer,
   "Godkänd för F-skatt", bankgiro och OCR-nummer
4. [ ] Bankfiler (senare): Bankgirots betalfiler och inläsning av inbetalningar
5. [ ] **PAXml-export till svenska lönesystem** (Visma Lön, Hogia, Fortnox Lön m.fl.)
   - Exportera tidrapporter och frånvaro per anställd och löneperiod som PAXml-fil
   - Bestäm datakälla: ERPNext:s tidrapporter (Timesheet) räcker för tid. Frånvaro och
     närvaro kräver Frappe HRMS, som inte är installerat i dag.
   - Mappning mellan aktivitetstyper/frånvaroorsaker och lönearter per lönesystem
6. [ ] **Transportbokning i Sverige**
   - Bygg på ERPNext:s doctype Shipment (skapas från försäljningsföljesedel)
   - Välj integrationsväg: direkt mot transportörer (PostNord, DHL Freight, Schenker, Bring, DSV)
     eller via en fraktaggregator (t.ex. nShift/Unifaun) som täcker flera transportörer med ett API
   - Boka sändning, hämta pris, skriv ut fraktsedel/etikett, spara sändnings-ID och spårningslänk
   - Svenska tjänster: t.ex. PostNord MyPack, DHL Paket/Pall, ombudsval
7. [ ] **Breddat stöd för e-faktura i Sverige**
   - Utgående: skapa Peppol BIS Billing 3.0 (UBL) från försäljningsfaktura och kreditnota.
     Det är krav vid fakturering till offentlig sektor (lag 2018:1277).
   - Inkommande: läs in Peppol-fakturor som leverantörsfakturor, med matchning mot inköpsorder
   - Överföring via Peppol-accesspunkt (t.ex. InExchange, Pagero eller Crediflow)
   - Svenska fält: Peppol-ID/GLN, organisationsnummer, referens/beställar-ID, bankgiro och OCR i betalinstruktionen
   - Utgå från ERPNext:s kodlistor (modulen EDI: Code List, Common Code). Undersök om en befintlig
     EU-e-fakturaapp för Frappe kan återanvändas innan egen UBL-generering byggs.

## 4. Översättningar och namn

- [ ] Granska sakfel som flaggades vid rättningen av `locale/sv.po`, t.ex.:
  - "Balance Sheet" översatt inkonsekvent ("Saldo Rapport"/"Balans Rapport"), bör vara "Balansräkning"
  - "Payment Receipt Note" översatt som "Betalningspåminnelse"
  - "Year of Passing" översatt som "Antal år"
  - "Workflow Builder ID" och "Year Start/End Date" saknar ord i översättningen
- [ ] Döp om särskrivna namn som är sparade i databasen, t.ex. momsmallarna
  "Försäljning Moms 25% - G" → "Försäljningsmoms 25 % - G"
- [ ] Efter uppdatering av frappe/erpnext: kör kontrollskriptet och rätta nya strängar
  ```bash
  bench --site svensk-erp.local execute erpnext_sverige.scripts.sarskrivningar.report --kwargs "{'title_case_only': True}"
  ```
