# Ändringslogg

## v0.1.0 – 2026-10-02 (pre-release)

Första versionen. Kräver Frappe och ERPNext version 16. Detaljer finns i [README](README.md) och i
[manualen](https://ubbe76.github.io/ERPNext-Sverige-docs/).

### Innehåll

- **Svenska översättningar:** drygt 11 000 rättade strängar från Frappe och ERPNext, utan särskrivningar och
  engelska versaler.
- **Grunduppsättning för BAS 2024:** standardkonton, momskonton, momskategorier (Svensk moms, EU, Utanför EU)
  med mallar och regler, svenskt talformat och Immutable Ledger.
- **Automatiskt kontoval** på kund- och leverantörsfakturor utifrån momskategori och momssats.
- **Momskategori från adressens land**, kontroll av EU-momsregistreringsnummer och knappen Kontrollera i VIES.
- **Fakturamall "Faktura Sverige"** med organisationsnummer, F-skatt, bankgiro, OCR-nummer och
  fakturanummer utan luckor (sätts när fakturan bokförs).
- **Momsdeklaration:** Skatteverkets rutor ur huvudboken, eSKD-fil, momsomföring mot 2650 och låsning av
  perioden efter deklarationen.
- **Grundbok** i registreringsordning och **SIE 4-export**.
- **Bankfiler:** inläsning av BgMax-filer med matchning via OCR, och betalfil för leverantörsbetalningar
  (ISO 20022 pain.001).
- **Frakt via Sendify:** priser, bokning, fraktsedel, etikett och spårning från följesedeln.
- **Skyddade bilagor:** underlag på bokförda verifikationer kan inte raderas eller flyttas.
- **Backup och årsarkiv:** krypterad backup till molntjänster med lagringstid enligt bokföringslagen.

### Inte provat skarpt

Det här är en pre-release. Följande är byggt enligt specifikationerna och testat automatiskt, men inte provat
mot verkligheten:

- **eSKD-filen** är inte kontrollerad mot Skatteverkets aktuella specifikation eller uppladdad i e-tjänsten.
- **SIE-filen** är inte inläst i ett annat bokslutsprogram.
- **Bankfilerna** (BgMax och betalfil) är inte provade mot en riktig bank.
- **Frakt** är provat mot Sendifys sandlåda, inte med riktiga bokningar.

ERPNext:s kassa är inte ett certifierat kassaregister och får inte användas för kontantförsäljning till
kunder på plats.
