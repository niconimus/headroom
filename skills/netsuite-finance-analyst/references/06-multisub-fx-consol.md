# 06 - Several subsidiaries, consolidation, intercompany, FX and books

## Contents
1. Subsidiary structure
2. Translating and consolidating with BUILTIN.CONSOLIDATE
3. Consolidated statements
4. Intercompany
5. Exchange rates and FX results
6. Multiple accounting books

---

## 1. Subsidiary structure

From the profile (`01-connection-discovery.md`): `subsidiary` with `parent`, `currency`,
`iselimination`. The top parent's currency is the consolidation currency. The elimination
subsidiary (`iselimination = 'T'`) holds elimination entries; include it only in consolidated
views. Hierarchies can be nested (`FullSubsidiaryHierarchy` exists if you need all levels).

Every amount in `transactionaccountingline.amount` is in the base currency of the line's
subsidiary. Two subsidiaries with the same currency (e.g. two EUR companies) can be listed side
by side and summed **for information**, but they are still separate legal entities - label such
a sum "Summe (nicht konsolidiert)".

## 2. Translating and consolidating with BUILTIN.CONSOLIDATE

Verified signature:
```sql
BUILTIN.CONSOLIDATE(tal.amount, 'LEDGER', 'DEFAULT', 'DEFAULT', <target_subsidiary_id>, <target_period_id>, 'DEFAULT')
```
- Translates each line's amount into the target subsidiary's currency using the consolidated
  exchange rates of the target period. `'DEFAULT'` rate types follow each account's
  `generalrate` setting (balance sheet accounts usually CURRENT, P&L accounts AVERAGE).
- The target period must be a period ID. For several periods, translate each period with its
  own rate - one `CASE` per period works in one query (verified):

```sql
SELECT BUILTIN.DF(tl.subsidiary) AS subsidiary, a.acctnumber, a.accountsearchdisplaynamecopy AS account_name,
       SUM(CASE WHEN t.postingperiod = 476
                THEN BUILTIN.CONSOLIDATE(tal.amount,'LEDGER','DEFAULT','DEFAULT',1,476,'DEFAULT') ELSE 0 END) AS aug,
       SUM(CASE WHEN t.postingperiod = 477
                THEN BUILTIN.CONSOLIDATE(tal.amount,'LEDGER','DEFAULT','DEFAULT',1,477,'DEFAULT') ELSE 0 END) AS sep
FROM transactionaccountingline tal
JOIN transaction t      ON t.id = tal.transaction
JOIN transactionline tl ON tl.transaction = tal.transaction AND tl.id = tal.transactionline
JOIN account a          ON a.id = tal.account
WHERE tal.posting = 'T' AND tal.accountingbook = 1
  AND t.postingperiod IN (476, 477) AND a.accttype = 'Expense'
GROUP BY BUILTIN.DF(tl.subsidiary), a.acctnumber, a.accountsearchdisplaynamecopy
```
Verified: plain `SUM(tal.amount)` across subsidiaries for Oct 2026 income gave -2,218,815 (mixed
currencies, meaningless), consolidated -2,109,343.80 USD.

- Results carry many decimals - round to 2 for presentation.
- For a variance between two periods in consolidated currency, part of the change is pure FX
  (different average rates). If the user asks "why", split: change at constant rate (period-2
  amounts translated at period-1 rate) vs. FX effect, or at least mention the rate change from
  `consolidatedExchangeRate`.

## 3. Consolidated statements

- **Consolidated P&L:** sum of translated amounts over all subsidiaries **including** the
  elimination subsidiary, per period. Cross-check with report "Income Statement" run with the
  negative consolidated subsidiary ID (e.g. `-1`), if `supports_consolidation` is true.
- **Consolidated balance sheet:** translated cumulative balances do not balance on their own -
  the currency translation adjustment (CTA) and translated retained earnings are computed by
  NetSuite at report time. Take consolidated balance sheet totals from the report "Balance Sheet"
  with the consolidated subsidiary ID; use SuiteQL only for account detail, and explain any CTA
  line.
- State "konsolidiert auf <parent> in <currency>, Kurse: <period> (Durchschnitt für GuV,
  Stichtag für Bilanz)" in the Basis line.

## 4. Intercompany

- Intercompany documents: `transaction.intercompany = 'T'`, `transaction.tosubsidiary`,
  journal types via `BUILTIN.DF(t.journaltype)`; tables `IntercompanyJournalEntry`,
  `AdvIntercompanyJournalEntry`.
- Intercompany balances: accounts with `account.eliminate = 'T'` or named "Intercompany ...",
  "Due to/from". Per pair of subsidiaries, receivable in A should equal payable in B after
  translation to one currency. Example (demo, 2026-09-30): United States "Intercompany
  Receivables" 1,156.00 USD vs. United Kingdom "Intercompany Payables" -829.02 GBP
  (= -1,068.88 USD at the Sep 2026 current rate 1.289324) → difference 87.12 USD to explain
  (FX or a missing counter-entry).
- Cross-check with reports "Intercompany Reconciliation" and "Intercompany Elimination".

## 5. Exchange rates and FX results

- `consolidatedExchangeRate`: `postingperiod, fromsubsidiary, tosubsidiary, currentrate,
  averagerate, historicalrate, accountingbook` - one row per subsidiary pair and period
  (verified).
- `currencyRate`: daily transaction exchange rates (base/transaction currency, effective date).
- Transaction rate on the document: `transaction.exchangerate`;
  `transactionaccountingline.exchangerate`.
- FX revaluation runs post `FxReval` transactions; realised/unrealised gains and losses: reports
  "Realized Exchange Rate Gains and Losses", "Unrealized Exchange Rate Gains and Losses", and
  the system accounts in the trial balance ("Realized Gain/Loss", "Unrealized Gain/Loss",
  "Cumulative Translation Adjustment").

## 6. Multiple accounting books

- `ns_getAccountingBooks` lists the books. `transactionaccountingline.accountingbook` separates
  them - **always** filter one book, otherwise amounts are counted once per book.
- Book-specific journals exist only in a secondary book.
- Reports accept `book` (and `book2` for comparisons) when `supports_book` is true.
- Name the book in the Basis line whenever more than one exists.
