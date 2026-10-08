# 08 - Glossary German ↔ English / NetSuite

## Contents
1. Accounting terms
2. Account types (`account.accttype`)
3. Transaction types (`transaction.type`)
4. Frequent statuses

---

## 1. Accounting terms

| Deutsch | English / NetSuite | Where in NetSuite |
|---|---|---|
| Hauptbuch | General Ledger | `transactionaccountingline`; report "General Ledger" |
| Summen- und Saldenliste, Saldenliste | Trial Balance | report "Trial Balance"; `03-gl-close.md` §2 |
| Bilanz | Balance Sheet | report "Balance Sheet" |
| GuV, Gewinn- und Verlustrechnung | Income Statement, P&L | report "Income Statement" |
| Gewinnvortrag | Retained Earnings | computed, not posted (`03-gl-close.md` §4) |
| Jahresüberschuss / Jahresergebnis | Net Income | computed |
| Buchungsperiode | Accounting Period / Posting Period | `transaction.postingperiod` |
| Geschäftsjahr | Fiscal Year | `accountingperiod` with `isyear = 'T'` |
| Periodenabschluss, Monatsabschluss | Period Close, Month-End Close | Period Close Checklist (UI) |
| Periode gesperrt / geschlossen | Period locked (AR/AP/All) / closed | `accountingperiod.closed / alllocked` |
| Beleg | Transaction, Document | `transaction` |
| Belegnummer | Document Number | `transaction.tranid` |
| Buchungssatz, Journalbuchung | Journal Entry | `type = 'Journal'` |
| Debitor / Kunde | Customer | `entity`, `customer` |
| Kreditor / Lieferant | Vendor | `entity` |
| Ausgangsrechnung | Invoice | `CustInvc` |
| Gutschrift (Kunde) | Credit Memo | `CustCred` |
| Eingangsrechnung | Vendor Bill, Bill | `VendBill` |
| Gutschrift (Lieferant) | Vendor Credit, Bill Credit | `VendCred` |
| Zahlungseingang | Customer Payment | `CustPymt` |
| Zahlungsausgang | Bill Payment, Vendor Payment | `VendPymt` |
| Offene Posten, OP-Liste | Open Items, Open Balance | `AccountsReceivableAging`, `AccountsPayableAging` |
| Altersstruktur, Fälligkeitsanalyse | Aging | reports "A/R Aging Summary", "A/P Aging Summary" |
| Forderungen aus L+L | Accounts Receivable, Trade Receivables | `accttype = 'AcctRec'` |
| Verbindlichkeiten aus L+L | Accounts Payable | `accttype = 'AcctPay'` |
| Sammelkonto, Abstimmkonto | Control Account | AR / AP accounts |
| Nebenbuch | Subledger | aging tables |
| Nicht zugeordnete Zahlung | Unapplied Payment | negative `openBalance` |
| Umsatzsteuer (USt) | Output VAT, VAT on Sales | tax accounts, `transactionline.taxline = 'T'` |
| Vorsteuer | Input VAT, VAT on Purchases | tax accounts |
| USt-Zahllast | VAT payable | output VAT - input VAT |
| Steuerperiode | Tax Period | `transaction.taxperiod` |
| Bankkonto | Bank Account | `accttype = 'Bank'` |
| Noch nicht eingezahlte Beträge | Undeposited Funds | account "Undeposited Funds" |
| Liquidität | Liquidity, Cash Position | `05-tax-bank-cash.md` §3 |
| Gesellschaft, Tochtergesellschaft | Subsidiary | `subsidiary`, `transactionline.subsidiary` |
| Konzern, konsolidiert | Consolidated | `BUILTIN.CONSOLIDATE`, negative subsidiary ID in reports |
| Eliminierung | Elimination | subsidiary with `iselimination = 'T'` |
| Intercompany-Verrechnung | Intercompany | `transaction.intercompany`, IC accounts |
| Hauswährung, Basiswährung | Base Currency | `subsidiary.currency` |
| Belegwährung | Transaction Currency | `transaction.currency` |
| Kursdifferenz (realisiert / unrealisiert) | Realized / Unrealized FX Gain/Loss | FX reports, `FxReval` |
| Währungsumrechnungsdifferenz | Cumulative Translation Adjustment (CTA) | consolidated balance sheet |
| Abgrenzung, RAP | Accrual, Deferral | `DeferRevenue`, `DeferExpense` |
| Kostenstelle | Department | `transactionline.department` |
| Kostenträger, Klasse | Class | `transactionline.class` |
| Standort | Location | `transactionline.location` |
| Storno | Void / Reversal | `transaction.voided`, `isreversal`, `reversal` |
| Genehmigung | Approval | `transaction.approvalstatus` |
| Änderungsprotokoll | System Notes | `SystemNote` |

## 2. Account types (`account.accttype`)

| Code | English | Deutsch | Group |
|---|---|---|---|
| `Bank` | Bank | Bank | Asset |
| `AcctRec` | Accounts Receivable | Forderungen | Asset |
| `UnbilledRec` | Unbilled Receivable | Noch nicht fakturierte Forderungen | Asset |
| `OthCurrAsset` | Other Current Asset | Sonstiges Umlaufvermögen | Asset |
| `FixedAsset` | Fixed Asset | Anlagevermögen | Asset |
| `OthAsset` | Other Asset | Sonstige Vermögenswerte | Asset |
| `DeferExpense` | Deferred Expense | Aktive RAP | Asset |
| `AcctPay` | Accounts Payable | Verbindlichkeiten L+L | Liability |
| `CredCard` | Credit Card | Kreditkarte | Liability |
| `OthCurrLiab` | Other Current Liability | Sonstige kurzfristige Verbindlichkeiten | Liability |
| `LongTermLiab` | Long Term Liability | Langfristige Verbindlichkeiten | Liability |
| `DeferRevenue` | Deferred Revenue | Passive RAP | Liability |
| `Equity` | Equity | Eigenkapital | Equity |
| `Income` | Income | Umsatzerlöse | P&L |
| `OthIncome` | Other Income | Sonstige Erträge | P&L |
| `COGS` | Cost of Goods Sold | Wareneinsatz / Herstellungskosten | P&L |
| `Expense` | Expense | Betriebsaufwand | P&L |
| `OthExpense` | Other Expense | Sonstige Aufwendungen | P&L |
| `NonPosting` | Non Posting | nicht buchend | excluded |
| `Stat` | Statistical | statistisch | excluded |

## 3. Transaction types (`transaction.type`)

| Code | English | Deutsch | Posting |
|---|---|---|---|
| `CustInvc` | Invoice | Ausgangsrechnung | yes |
| `CashSale` | Cash Sale | Barverkauf | yes |
| `CustCred` | Credit Memo | Kundengutschrift | yes |
| `CustPymt` | Customer Payment | Zahlungseingang | yes |
| `CustDep` | Customer Deposit | Anzahlung Kunde | yes |
| `CustRfnd` | Customer Refund | Rückzahlung an Kunden | yes |
| `VendBill` | Bill | Eingangsrechnung | yes |
| `VendCred` | Bill Credit | Lieferantengutschrift | yes |
| `VendPymt` | Bill Payment | Zahlungsausgang | yes |
| `VPrep` | Vendor Prepayment | Anzahlung an Lieferanten | yes |
| `Journal` | Journal Entry | Journalbuchung | yes (once approved) |
| `Check` | Check | Scheck / Auszahlung | yes |
| `Deposit` | Deposit | Einzahlung | yes |
| `Transfer` | Transfer | Umbuchung zwischen Konten | yes |
| `ExpRept` | Expense Report | Spesenabrechnung | yes (once approved) |
| `FxReval` | Currency Revaluation | Währungsneubewertung | yes |
| `SysJrnl` | System Journal | Systembuchung | yes |
| `ItemRcpt` | Item Receipt | Wareneingang | yes (inventory/accrual) |
| `ItemShip` | Item Fulfillment | Warenausgang / Lieferung | yes when shipped |
| `InvAdjst` | Inventory Adjustment | Bestandskorrektur | yes |
| `SalesOrd` | Sales Order | Kundenauftrag | no |
| `PurchOrd` | Purchase Order | Bestellung | no |
| `TrnfrOrd` | Transfer Order | Umlagerungsauftrag | no |
| `Estimate` | Estimate / Quote | Angebot | no |
| `Opprtnty` | Opportunity | Verkaufschance | no |

## 4. Frequent statuses (`BUILTIN.DF(transaction.status)`)

| Text | Meaning |
|---|---|
| Invoice : Open / Paid In Full | Rechnung offen / vollständig bezahlt |
| Bill : Open / Paid In Full / Payment In-Transit | Eingangsrechnung offen / bezahlt / Zahlung unterwegs |
| Bill : Pending Approval | Eingangsrechnung wartet auf Genehmigung (nicht gebucht) |
| Journal : Pending Approval / Approved for Posting | Journal wartet auf Genehmigung (nicht gebucht) / gebucht |
| Payment : Deposited / Not Deposited / Unapplied | Zahlung eingezahlt / nicht eingezahlt / nicht zugeordnet |
| Credit Memo : Open / Fully Applied | Gutschrift offen / vollständig verrechnet |
| Sales Order : Pending Fulfillment / Pending Billing / Billed | Auftrag offen / zu fakturieren / fakturiert |
| Purchase Order : Pending Receipt / Pending Bill / Fully Billed | Bestellung offen / Rechnung fehlt / abgerechnet |
| Item Fulfillment : Picked / Packed / Shipped | kommissioniert / verpackt / versendet (erst "Shipped" bucht) |
| Bill Payment : In-Transit | Zahlung unterwegs |

Status letters (`transaction.status`, e.g. `A`, `B`) mean different things per type - always use
the text from `BUILTIN.DF` or filter type and letter together.
