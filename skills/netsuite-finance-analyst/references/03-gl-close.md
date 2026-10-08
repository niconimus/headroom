# 03 - General ledger, financial statements and month-end close

## Contents
1. Account type groups and signs
2. Trial balance
3. Income statement (P&L)
4. Balance sheet with computed retained earnings
5. Variance analysis ("why did X change?")
6. Journals and document lists
7. Month-end close checks

All queries use the canonical GL join from `02-suiteql-model.md`. Replace the IDs (book 1,
subsidiary 2, period 477) with the ones from this account's profile.

---

## 1. Account type groups and signs

| Group | `accttype` codes | Normal balance | Present as |
|---|---|---|---|
| Assets | `Bank, AcctRec, UnbilledRec, OthCurrAsset, FixedAsset, OthAsset, DeferExpense` | debit (+) | as is |
| Liabilities | `AcctPay, CredCard, OthCurrLiab, LongTermLiab, DeferRevenue` | credit (-) | flip sign |
| Equity | `Equity` | credit (-) | flip sign |
| Revenue | `Income, OthIncome` | credit (-) | flip sign |
| Costs | `COGS, Expense, OthExpense` | debit (+) | as is |
| Not financial | `Stat, NonPosting` | - | exclude |

Check: for one subsidiary, the sum of all `tal.amount` (all types except Stat/NonPosting) up to any
date is 0. Verified: United States to 2026-09-30, balance sheet accounts +1,989,652.44 and P&L
accounts -1,989,652.44.

## 2. Trial balance

```sql
SELECT a.acctnumber, a.accountsearchdisplaynamecopy AS account_name, a.accttype,
       NVL(SUM(tal.debit),0) AS debit, NVL(SUM(tal.credit),0) AS credit, SUM(tal.amount) AS balance
FROM transactionaccountingline tal
JOIN transaction t      ON t.id = tal.transaction
JOIN transactionline tl ON tl.transaction = tal.transaction AND tl.id = tal.transactionline
JOIN account a          ON a.id = tal.account
WHERE tal.posting = 'T' AND tal.accountingbook = 1 AND tl.subsidiary = 7
  AND t.trandate <= TO_DATE('2026-09-30','YYYY-MM-DD')
  AND a.accttype NOT IN ('Stat','NonPosting')
GROUP BY a.acctnumber, a.accountsearchdisplaynamecopy, a.accttype
HAVING SUM(tal.amount) <> 0
ORDER BY a.acctnumber
```
- One subsidiary per trial balance (base currency). For all subsidiaries: one block each.
- Cross-check with report "Trial Balance" (`dateTo` = period end, `subsidiaryId`). Verified equal
  for Germany GmbH at 2026-09-30.
- If the report and the query differ only on P&L and equity accounts, the report is likely
  showing P&L fiscal-year-to-date with prior years in retained earnings - compare balance sheet
  accounts directly and P&L accounts as fiscal-year-to-date before calling it a difference.

## 3. Income statement (P&L)

Movements of one or more periods, by account, sign-flipped for presentation:

```sql
SELECT a.accttype, a.acctnumber, a.accountsearchdisplaynamecopy AS account_name,
       -SUM(tal.amount) AS amount_presented      -- revenue positive, costs negative
FROM transactionaccountingline tal
JOIN transaction t      ON t.id = tal.transaction
JOIN transactionline tl ON tl.transaction = tal.transaction AND tl.id = tal.transactionline
JOIN account a          ON a.id = tal.account
WHERE tal.posting = 'T' AND tal.accountingbook = 1 AND tl.subsidiary = 2
  AND t.postingperiod IN (475, 476, 477)          -- Q3 2026 = Jul, Aug, Sep
  AND a.accttype IN ('Income','OthIncome','COGS','Expense','OthExpense')
GROUP BY a.accttype, a.acctnumber, a.accountsearchdisplaynamecopy
ORDER BY a.accttype, a.acctnumber
```
Presentation order: Revenue (`Income`) - COGS = Gross profit - Operating expenses (`Expense`) =
Operating result + Other income (`OthIncome`) - Other expenses (`OthExpense`) = Net income.
"Operating expenses" / "Betriebsaufwand" means `Expense` only unless the user includes COGS.

Consolidated P&L: wrap the amount with `BUILTIN.CONSOLIDATE` per period - see
`06-multisub-fx-consol.md`. Cross-check with report "Income Statement" (`dateFrom`/`dateTo`).

## 4. Balance sheet with computed retained earnings

NetSuite does not post a year-end closing entry. A balance sheet built from the ledger therefore
needs two computed lines:

- **Retained earnings (Gewinnvortrag)** = minus the sum of all P&L account amounts dated before
  the start of the current fiscal year.
- **Net income current year (Jahresergebnis lfd. GJ)** = minus the sum of P&L amounts from fiscal
  year start to the balance sheet date.

```sql
SELECT
  SUM(CASE WHEN a.accttype NOT IN ('Income','OthIncome','COGS','Expense','OthExpense')
           THEN tal.amount ELSE 0 END)                                         AS bs_accounts_sum,
  -SUM(CASE WHEN a.accttype IN ('Income','OthIncome','COGS','Expense','OthExpense')
             AND t.trandate <  TO_DATE('2026-01-01','YYYY-MM-DD') THEN tal.amount ELSE 0 END)
                                                                               AS retained_earnings,
  -SUM(CASE WHEN a.accttype IN ('Income','OthIncome','COGS','Expense','OthExpense')
             AND t.trandate >= TO_DATE('2026-01-01','YYYY-MM-DD') THEN tal.amount ELSE 0 END)
                                                                               AS net_income_ytd
FROM transactionaccountingline tal
JOIN transaction t      ON t.id = tal.transaction
JOIN transactionline tl ON tl.transaction = tal.transaction AND tl.id = tal.transactionline
JOIN account a          ON a.id = tal.account
WHERE tal.posting = 'T' AND tal.accountingbook = 1 AND tl.subsidiary = 2
  AND t.trandate <= TO_DATE('2026-09-30','YYYY-MM-DD')
  AND a.accttype NOT IN ('Stat','NonPosting')
```
Then list balance sheet accounts (group by account, `accttype` in the asset/liability/equity
lists) and add the two computed lines to equity. Assets = Liabilities + Equity must hold. Label
both lines "berechnet" / "computed". Fiscal year start comes from the profile; if unknown, ask.
Cross-check totals with report "Balance Sheet" (`dateTo`, `subsidiaryId`).

## 5. Variance analysis ("why did X change?")

1. **Both periods in one query**, by account (and subsidiary if several):
```sql
SELECT BUILTIN.DF(tl.subsidiary) AS subsidiary, a.acctnumber,
       a.accountsearchdisplaynamecopy AS account_name,
       SUM(CASE WHEN t.postingperiod = 476 THEN tal.amount ELSE 0 END) AS p1,
       SUM(CASE WHEN t.postingperiod = 477 THEN tal.amount ELSE 0 END) AS p2
FROM transactionaccountingline tal
JOIN transaction t      ON t.id = tal.transaction
JOIN transactionline tl ON tl.transaction = tal.transaction AND tl.id = tal.transactionline
JOIN account a          ON a.id = tal.account
WHERE tal.posting = 'T' AND tal.accountingbook = 1
  AND t.postingperiod IN (476, 477) AND a.accttype = 'COGS' AND tl.subsidiary = 2
GROUP BY BUILTIN.DF(tl.subsidiary), a.acctnumber, a.accountsearchdisplaynamecopy
```
2. Delta = p2 - p1 per row; rank by absolute delta.
3. **Drill into the top 3-5 accounts**: same query grouped by `t.type`, `BUILTIN.DF(t.entity)`
   or document (`t.tranid`) to name the postings that drive the change (e.g. "two inventory
   adjustments of 40k", "missing accrual reversal").
4. Present: total change, the top drivers with amounts, and "Sonstige / other" so that drivers +
   other = total change exactly.
5. Across several subsidiaries with different currencies: translate with `BUILTIN.CONSOLIDATE`
   first (per period), or analyse per subsidiary.

## 6. Journals and document lists

- Count documents with `COUNT(DISTINCT t.id)`. On journals **every line has `mainline = 'T'`**
  (verified), so joining on the main line multiplies journals by their line count.
- Journal with lines: `t.type = 'Journal'`, join `transactionaccountingline` for account/amount,
  `transactionline.memo` for line text. Intercompany journals have lines in several
  subsidiaries (`tl.subsidiary` per line).
- Who and when: `BUILTIN.DF(t.createdby)`, `TO_CHAR(t.createddate,'YYYY-MM-DD HH24:MI')`;
  changes from `SystemNote` (see `04-ar-ap.md`).

## 7. Month-end close checks

Answer "is period X ready to close?" with a checklist. Each check has a status (ok / attention /
blocker / not determinable), a count or amount, and the documents behind it. The verdict is
"ready" only if no blocker remains. **Never** state that a period is closed or locked unless you
read it from `accountingperiod`.

Base filter for document checks (one subsidiary, one period):
```sql
FROM transaction t
JOIN transactionline tl ON tl.transaction = t.id AND tl.mainline = 'T'
WHERE tl.subsidiary = 2 AND t.voided = 'F'
  AND t.trandate BETWEEN TO_DATE('2026-09-01','YYYY-MM-DD') AND TO_DATE('2026-09-30','YYYY-MM-DD')
```
Group by `t.type, BUILTIN.DF(t.status), t.posting` and count `DISTINCT t.id`.

| # | Check | How | Typical status |
|---|---|---|---|
| 1 | Journals pending approval | `type = 'Journal'`, status "Journal : Pending Approval" (`posting = 'F'`) | blocker |
| 2 | Bills pending approval | `type = 'VendBill'`, `BUILTIN.DF(t.approvalstatus) = 'Pending Approval'` | blocker |
| 3 | Fulfillments picked/packed but not shipped | `type = 'ItemShip'`, status Picked/Packed, `posting = 'F'` | attention (cut-off) |
| 4 | Sales orders pending billing | `type = 'SalesOrd'`, status "Pending Billing" | attention (unbilled revenue) |
| 5 | Receipts not billed / POs pending bill | `type = 'PurchOrd'`, status "Pending Bill" / "Pending Billing/Partially Received"; GRNI (accrued purchases) account balance | attention (accrual) |
| 6 | Payments in transit | `VendPymt` / `VendBill` status "In-Transit" | attention |
| 7 | AR subledger = AR control account | aging report total at period end vs. GL `AcctRec` balance (see `04-ar-ap.md`) | blocker if unexplained |
| 8 | AP subledger = AP control account | same for `AcctPay` | blocker if unexplained |
| 9 | Unapplied payments / credits | AR aging rows with negative `openBalance` (Payment, Credit Memo) | attention |
| 10 | Back-posted or future-dated documents | `t.postingperiod = P` but `trandate` outside P; `trandate` after today | attention |
| 11 | FX revaluation run | any `type = 'FxReval'` in the period for subsidiaries with foreign-currency balances | attention if missing |
| 12 | Intercompany balances net to zero | see `06-multisub-fx-consol.md` | blocker if unexplained |
| 13 | Clearing / suspense accounts | accounts whose name contains Clearing, Suspense, Interim, Verrechnung with balance <> 0 | attention |
| 14 | Period status | `accountingperiod.closed / alllocked` if readable; else "not determinable" + missing permission | not determinable |

Present blockers first, each with the documents (number, date, amount, who created it).
