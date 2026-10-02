# TODO

Siten `svensk-erp.local`, ett bolag (SEK, kontoplan BAS 2024 med nummer).
Inga transaktioner är bokförda ännu. Gör klart steg 1 innan första verifikationen.

## 1. Bokföringsgrund (innan första verifikationen)

Klart för bolaget via `erpnext_sverige.setup.company.setup_swedish_company`:

- [x] Standardkonton: COGS 4000, kursdifferenser 3960, write-off 3740, kassarabatt 3731,
  förutbetalda intäkter 2970 / kostnader 1790
- [x] **Immutable Ledger** aktiverad (Bokföringslagen: verifikationer får inte ändras, bara rättas)
- [x] Moms på rätt BAS-konton (2611/2621/2631/2641) i stället för summakontona 2610–2640
- [x] Momskategorier Svensk moms / EU / Utanför EU med mallar och Tax Rules:
  EU-försäljning och export utan moms, EU-inköp med omvänd skattskyldighet (2645/2614),
  varuimport (2645/2615), tjänsteinköp utanför EU (manuellt val)
- [x] Artikelmomsmallar Moms 12 %, Moms 6 % och Momsfri. Sätt dem på artikeln med momskategori "Svensk moms".
- [x] Konto 3308 Försäljning tjänster till annat EU-land skapat

Kvar / begränsningar:
- [x] **Automatiskt kontoval utifrån momskategori och momssats** (`accounting/account_selection.py`,
  hook på Sales/Purchase Invoice `validate`). Nytt fält "Vara eller tjänst (moms)" på Item.
  - Sverige: 3001–3004 per momssats. EU: 3108/3308. Export: 3105/3305.
  - Inköp EU: 4515–4517 / 4535. Import: 4545 / 4531. Svenska inköp och lagerartiklar vid inköp lämnas orörda.
  - [x] Kreditfakturor och debetnotor testade (`tests/test_credit_notes.py`): konton, moms, omvänd
    skattskyldighet, momsdeklaration, utskrift "Kreditfaktura" utan OCR och förfallodatum
  - [x] Kassafaktura (Sales Invoice med kassa/POS) kontrollerad: moms, konto, kassa 1910, inget OCR
  - [ ] **Kassaregister**: ERPNext:s kassa är inte ett certifierat kassaregister. Kontant- och kortförsäljning
    till kunder på plats kräver ett certifierat kassaregister med kontrollenhet (Skatteverket). Används inte i dag.
- [ ] Omvänd skattskyldighet för varor med 12 och 6 % (2624/2634)
- [ ] Förskottskonton (2420/1480) om "bokför förskott på separat konto" ska användas. ERPNext kräver då
  att kontotyperna ändras (Receivable/Payable).
- [x] Momskategori sätts automatiskt utifrån adressens land (Sverige / EU / utanför EU); privatpersoner i EU får
  svensk moms. EU-företags momsreg.nr formatkontrolleras, krävs vid bokföring av EU-faktura och kan kontrolleras i VIES
  - [ ] OSS (köparlandets moms) om försäljningen till privatpersoner i EU överstiger 99 680 kr/år

## 2. Provkör ett helt flöde

Provkört 2026-09-28 på testsiten `test-erp.local`, som är en kopia av `svensk-erp.local`. Den riktiga bokföringen är orörd.

- [x] Kundfaktura (25 % + 12 %) → betalning: 1510 → 1930, moms på 2611 och 2621, 1510 nollställd
- [x] EU-kundfaktura → betalning: ingen moms, 1510 nollställd
- [x] Leverantörsfaktura → betalning: ingående moms på 2641, 2440 nollställd
- [x] EU-leverantörsfaktura → betalning: 2645 debet / 2614 kredit (omvänd skattskyldighet), 2440 nollställd
- [x] Makulering med Immutable Ledger: motverifikation bokförs, originalraderna ligger kvar

Fynd:
- [x] ~~ERPNext sparar första avvikande intäktskonto som artikelns standard~~. Löst av det automatiska
  kontovalet: hanterade konton skrivs alltid över utifrån momskategori (regressionstest finns).
- [x] ~~Svensk försäljning bokförs på 3000~~. Nu 3001/3002/3003/3004 per momssats.
- [x] ~~Momsomföring till 2650 vid periodens slut är inte testad~~. Finns nu i rapporten Momsdeklaration (punkt 3.2).

## 3. Funktioner i erpnext_sverige

1. [x] **SIE-export (SIE 4)**: rapporten "SIE-export" (modul Sweden Compliance) laddar ner en SIE 4-fil per
   räkenskapsår med kontoplan, IB/UB/RES, resultatenheter (dim 1), projekt (dim 6) och alla verifikationer
   (serie A journalposter, B kundfakturor, C leverantörsfakturor, D betalningar, E lager, F övrigt)
   - [ ] Provimportera filen i ett bokslutsprogram eller hos revisorn och kontrollera att allt kommer med
   - [ ] SIE-import (t.ex. ingående balanser från tidigare bokföringsprogram)
2. [x] **Momsdeklaration**: rapporten "Momsdeklaration" (modul Sweden Compliance) räknar fram Skatteverkets
   rutor ur huvudboken, laddar ner eSKD-fil och skapar momsomföring (utkast) mot 2650
   - [ ] **Verifiera eSKD-filen mot Skatteverkets aktuella specifikation** (filformat, elementnamn, OrgNr-format)
     innan den laddas upp på riktigt. Testa uppladdningen i Skatteverkets e-tjänst, gärna med en testdeklaration.
   - [ ] **Valbar redovisningsperiod** (månad, kvartal, år) per bolag. I dag utgår rapporten från räkenskapsåret
     (bolaget redovisar per år), men valfria datum kan väljas i filtret. Perioden ska styra standardfiltret och
     kontrollera att datumen motsvarar en hel redovisningsperiod.
   - [ ] Rutor som inte stöds och alltid är 0: 06 (uttag), 07 (vinstmarginal), 08 (frivillig skattskyldighet för hyra),
     37/38 (trepartshandel)
3. [x] **Fakturamall "Faktura Sverige"** (standard för kundfakturor): organisationsnummer, momsreg.nr,
   F-skatt (inställning på bolaget), underlag och moms per momssats, kundens momsreg.nr och hänvisning vid
   EU-försäljning/export, bankgiro/plusgiro/bankkonto/IBAN/BIC från bolagets bankkonto, OCR-nummer
   (inställning på bolaget). Svenska eller engelska efter kundens språk.
   - [ ] **Installera en PDF-generator**: wkhtmltopdf saknas, så PDF (utskrift, e-post) fungerar inte.
     Alternativt Chrome-generatorn i Utskriftsinställningar.
   - [x] Svenskt talformat (`# ###,##`) och SEK med "kr" efter beloppet samt måndag som första veckodag (`set_swedish_regional_settings`, ingår i grunduppsättningen)
   - [ ] Lägg in bolagets adress och bankkonto (Bank Account med bankgiro) på riktiga siten
4. [x] **Bankfiler**
   - Inbetalningar: "Bankgiroinbetalning" läser BgMax-filen, matchar mot kundfakturor via OCR och skapar
     betalningar (utkast). Dubbletter (samma löpnummer) stoppas.
   - Utbetalningar: "Leverantörsbetalning" samlar förfallna leverantörsfakturor och skapar betalfil enligt
     ISO 20022 pain.001.001.03 (bankgiro, plusgiro, bankkonto, IBAN; OCR som strukturerad referens) samt
     betalningar (utkast) som bokförs när banken betalat.
   - [ ] **Verifiera mot banken**: läs in en riktig BgMax-fil och ladda upp en provbetalfil hos banken.
     Positioner och element är skrivna enligt Bankgirots manual och bankernas anvisningar men inte provade skarpt.
   - [ ] Betalningar i utländsk valuta (EUR m.m.) i betalfilen; i dag bara SEK
   - [ ] Inläsning av bankens kontoutdrag (camt.053) för avstämning
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

## 5. Inför publicering (publikt repo eller Frappe Marketplace)

- [x] Byt `app_email` i `erpnext_sverige/hooks.py` och e-posten under `authors` i `pyproject.toml` till en
  adress som tar emot e-post, till exempel en vidarebefordringsadress (alias på egen domän eller SimpleLogin/Proton/Firefox Relay).
  Dagens adress är GitHubs anonyma adress, som inte kan ta emot e-post. Marketplace kräver en adress som fungerar.
  Commits kan behålla den anonyma adressen.
