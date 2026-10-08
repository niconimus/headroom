# 05 - Tax, bank and cash

## Contents
1. VAT / sales tax (USt, Vorsteuer, Zahllast)
2. Bank balances
3. Liquidity overview

---

## 1. VAT / sales tax

### Find the tax accounts actually used
Tax setups differ (Legacy tax vs. SuiteTax, per-nexus control accounts such as
"VAT on Sales [1]" / "VAT on Purchases [1]" / "VAT Liability [1]"). Do not guess from names alone;
find the accounts that receive tax lines:

```sql
SELECT BUILTIN.DF(tl.subsidiary) AS subsidiary, a.id AS account_id, a.acctnumber,
       a.accountsearchdisplaynamecopy AS account_name, a.accttype,
       COUNT(*) AS n_lines, SUM(tal.amount) AS amount
FROM transactionaccountingline tal
JOIN transaction t      ON t.id = tal.transaction
JOIN transactionline tl ON tl.transaction = tal.transaction AND tl.id = tal.transactionline
JOIN account a          ON a.id = tal.account
WHERE tal.posting = 'T' AND tal.accountingbook = 1 AND tl.taxline = 'T'
  AND t.trandate >= TO_DATE('2026-01-01','YYYY-MM-DD')
GROUP BY BUILTIN.DF(tl.subsidiary), a.id, a.acctnumber, a.accountsearchdisplaynamecopy, a.accttype
ORDER BY 1
```
Verified example (2026): Germany GmbH → "VAT on Sales [1]" (liability) and
"VAT on Purchases [1]" (asset); France SARL → "VAT on Sales [2]". Tax control accounts often have
no account number - identify them by name and ID.

Also look for the settlement account (e.g. "VAT Liability [1]", "USt-Zahllast", "VAT Liability")
by name among `OthCurrLiab` accounts: the periodic VAT settlement journal moves balances there.

The `taxAcct` table (id, name, description, taxAcctType, nexus, country) describes tax control
accounts but has **no link to the GL account** - use it only to name nexus/country.

### VAT payable for a period (Zahllast)
Per subsidiary (one nexus / currency), for the tax period:
- Output VAT (USt) = credit movement on the "on Sales" accounts → present as positive.
- Input VAT (Vorsteuer) = debit movement on the "on Purchases" accounts → present as positive.
- **VAT payable = output VAT - input VAT.** Negative = refund claim (Erstattung).

```sql
SELECT BUILTIN.DF(tl.subsidiary) AS subsidiary, a.accountsearchdisplaynamecopy AS account_name,
       a.accttype, SUM(tal.amount) AS movement
FROM transactionaccountingline tal
JOIN transaction t      ON t.id = tal.transaction
JOIN transactionline tl ON tl.transaction = tal.transaction AND tl.id = tal.transactionline
JOIN account a          ON a.id = tal.account
WHERE tal.posting = 'T' AND tal.accountingbook = 1
  AND tl.subsidiary IN (7, 8)
  AND t.postingperiod = 477                       -- tax period; or use t.taxperiod if populated
  AND tal.account IN (373, 374, 378)              -- tax accounts found above
GROUP BY BUILTIN.DF(tl.subsidiary), a.accountsearchdisplaynamecopy, a.accttype
```
- Report each subsidiary separately (each files its own return, even with the same currency).
- The settlement journal (a `Journal` that clears the VAT accounts into the settlement account)
  moves balances but is not VAT of the period. Group the movement by `t.type` once; if a journal
  hits both a VAT account and the settlement account, show it as its own line ("Umbuchung auf
  Zahllastkonto") instead of netting it into output or input VAT.
- `transaction.taxperiod` exists; if populated it is the correct period filter for VAT.
- Cross-check with a VAT report by title, run for that subsidiary and period (`VAT on Sales
  Summary`, `VAT on Purchases Summary`, country-specific "Sales by Tax Code" / "Purchases by Tax
  Code" reports). Mention which report you used.
- A balance of zero or very small amounts is a valid result - report it as such ("keine
  USt-relevanten Buchungen im September") instead of searching elsewhere.

## 2. Bank balances

```sql
SELECT BUILTIN.DF(tl.subsidiary) AS subsidiary, a.acctnumber,
       a.accountsearchdisplaynamecopy AS account_name, BUILTIN.DF(a.currency) AS account_currency,
       SUM(tal.amount) AS balance_base_currency
FROM transactionaccountingline tal
JOIN transaction t      ON t.id = tal.transaction
JOIN transactionline tl ON tl.transaction = tal.transaction AND tl.id = tal.transactionline
JOIN account a          ON a.id = tal.account
WHERE tal.posting = 'T' AND tal.accountingbook = 1 AND a.accttype = 'Bank'
  AND t.trandate <= TO_DATE('2026-10-08','YYYY-MM-DD')
GROUP BY BUILTIN.DF(tl.subsidiary), a.acctnumber, a.accountsearchdisplaynamecopy, BUILTIN.DF(a.currency)
ORDER BY a.acctnumber
```
- Balances are **cumulative** up to the date, in the subsidiary's base currency.
- When the account currency equals the subsidiary base currency (the normal case), that is
  also the account balance. If they differ (foreign-currency bank account), the account-currency
  balance cannot be summed from `transactionline.foreignamount` across mixed transaction
  currencies - state the base-currency figure and point to the "Cash Statement" report or the
  account register for the account-currency balance.
- Negative bank balances are possible (overdraft or missing deposits in demo data) - report them
  as they are and flag them.
- Future-dated postings: count them separately (`t.trandate > today`) and mention them.
- Bank reconciliation status is not exposed in SuiteQL in most accounts; say that the
  reconciliation itself has to be checked in NetSuite (Reconcile Bank Statement / Match Bank
  Data) if asked.

## 3. Liquidity overview

For "Liquidität" questions present, per subsidiary and currency:
1. Bank balances (section 2).
2. Undeposited funds: account named "Undeposited Funds" (`OthCurrAsset`) - received but not yet
   deposited.
3. Credit card accounts (`CredCard`) - usually negative.
4. Expected cash-in: AR open items due within the next 30 days (and overdue separately).
5. Expected cash-out: AP open items due within the next 30 days (and overdue separately).
   (Open item queries: `04-ar-ap.md`.)

Never add the subsidiaries' figures across currencies. For a group view, translate with
`BUILTIN.CONSOLIDATE` (`06-multisub-fx-consol.md`) and label it "umgerechnet zum Stichtagskurs".
