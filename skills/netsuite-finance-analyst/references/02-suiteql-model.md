# 02 - SuiteQL data model, syntax and error handling

Read before writing the first query of a conversation.

## Contents
1. Syntax rules
2. Core tables and verified fields
3. The canonical GL query
4. Pagination and completeness
5. Error messages and what they mean
6. Fallback matrix

---

## 1. Syntax rules

SuiteQL is SQL-92 with Oracle functions. Rules that bite:
- No `WITH` / CTEs - use inline subqueries.
- No `OFFSET ... FETCH` - use the tool's `pageSize` / `pageIndex`.
- ANSI joins only; no Oracle `(+)`; do not mix comma joins with `JOIN`.
- Dates: `TO_DATE('2026-09-30','YYYY-MM-DD')`. In SELECT, return dates as
  `TO_CHAR(t.trandate,'YYYY-MM-DD')` - raw dates come back as `M/D/YYYY` strings ("10/7/2026" is
  7 October).
- String concatenation with `||`.
- `IN (...)` lists max 1,000 items - chunk or use a subquery.
- Boolean fields are `'T'` / `'F'` strings.
- `BUILTIN.DF(field)` returns the display text of a list/record field (status, currency, entity,
  subsidiary, period, account). Group by the same expression you select.
- `ROWNUM <= n` limits rows (apply inside a subquery if you also ORDER BY).
- `CASE WHEN ... THEN ... END` works inside `SUM()` - use it for aging buckets and pivots.

## 2. Core tables and verified fields

Field lists below were verified with `ns_getSuiteQLMetadata` on a OneWorld account. Custom fields
(`custbody_*`, `custcol_*`) vary per account - check metadata before using one.

### transaction (document header)
`id, tranid` (document number, **not unique across types** - filter `type` too)`, type`
(code, e.g. `CustInvc`)`, status` (letter; `BUILTIN.DF` gives "Invoice : Open")`, trandate,
duedate, postingperiod, posting, voided, void, isreversal, reversal, approvalstatus, entity,
currency, exchangerate, foreigntotal, foreignamountpaid, foreignamountunpaid,
foreignpaymentamountunused, daysoverduesearch, daysopen, memo, createdby, createddate,
lastmodifiedby, lastmodifieddate, intercompany, tosubsidiary, journaltype,
openingbalancetransaction, terms, nexus, taxperiod, trandisplayname`.

Does **not** exist: `subsidiary` (use `transactionline` with `mainline = 'T'`),
`foreignamountremaining` (use `foreignamountunpaid`).
`foreigntotal` is in transaction currency and negative for vendor bills.

### transactionline (document lines)
`transaction, id` (line number; 0 = main line on most documents)`, mainline, taxline, subsidiary,
department, class, location, entity, netamount, foreignamount, memo, eliminate,
accountinglinetype`. `foreignamount` is in **transaction** currency - never sum it across
currencies.

### transactionaccountingline (GL impact - the source of truth for balances)
`transaction, transactionline, accountingbook, account, amount` (base currency, + debit /
- credit)`, debit, credit, netamount, posting, amountunpaid, amountpaid, paymentamountunused,
paymentamountused, exchangerate, accounttype, glauditnumber`.

### account
`id, acctnumber, accountsearchdisplaynamecopy` (name)`, fullname, accttype, currency,
subsidiary, issummary, isinactive, parent, eliminate, generalrate, cashflowrate`.

### subsidiary
`id, name, fullname, parent, iselimination, isinactive, currency, country`.

### AccountsReceivableAging / AccountsPayableAging (open items, one row per open document)
`transaction, transactionLine, documentNumber, transactionType, transactionDate, dueDate,
closeDate, openBalance, transactionAmountTransactionCurrency, subsidiary,
subsidiaryBookCurrency, accountingBook, account, entity, location, department, class, memo`.
AR also has `customer`; AP has **no** `vendor` field - use `entity`.
- `openBalance` is in subsidiary base currency. AR: invoices positive, unapplied payments and
  credits negative. AP: bills positive (while the GL control account is negative).
- Rows reflect **today's** state, including future-dated documents and payments.

### AccountPeriodActivity (GL activity per period - also the period-list fallback)
`accountingPeriod, account, subsidiary, accountingBook, department, amount, isCustomGlLine`.

### Document links and audit trail
- `PreviousTransactionLink`, `NextTransactionLink`: `previousdoc, nextdoc, linktype` (e.g.
  "Payment"), `foreignamount`. Query them **flat** with a WHERE on a document ID; joining them to
  `transaction` with GROUP BY returned "Invalid or unsupported search".
- `SystemNote`: `recordid, recordtypeid` (-30 = transaction)`, date, name` (who)`, field, type`
  (1 = record created, 2 = field set on create, 4 = field changed)`, context, oldvalue, newvalue`.

### Others that exist
`currency, currencyRate, consolidatedExchangeRate, taxAcct` (id, name, description,
taxAcctType, nexus, country, isInactive - no GL account link)`, SubsidiaryNexus,
subsidiaryTaxRegistration, TransactionStatus, term, accountType, IntercompanyJournalEntry,
AdvIntercompanyJournalEntry, budgetCategory, customerPaymentApplyLine, vendorPaymentApplyLine`.

### Type codes you will filter on
`CustInvc` invoice · `CustCred` credit memo · `CustPymt` customer payment · `CustDep` deposit ·
`CustRfnd` refund · `VendBill` bill · `VendCred` bill credit · `VendPymt` bill payment ·
`VPrep` vendor prepayment · `Journal` journal entry · `Check` · `Deposit` · `Transfer` ·
`ExpRept` expense report · `FxReval` currency revaluation · `SysJrnl` system journal ·
`ItemRcpt` item receipt · `ItemShip` item fulfillment · `SalesOrd` · `PurchOrd` · `TrnfrOrd`.
Order types (`SalesOrd`, `PurchOrd`) are non-posting and never appear in GL figures.

## 3. The canonical GL query

Every balance, trial balance, P&L or movement starts from this shape:

```sql
SELECT a.acctnumber, a.accountsearchdisplaynamecopy AS account_name, a.accttype,
       SUM(tal.debit) AS debit, SUM(tal.credit) AS credit, SUM(tal.amount) AS balance
FROM transactionaccountingline tal
JOIN transaction t      ON t.id = tal.transaction
JOIN transactionline tl ON tl.transaction = tal.transaction AND tl.id = tal.transactionline
JOIN account a          ON a.id = tal.account
WHERE tal.posting = 'T'
  AND tal.accountingbook = 1                      -- primary book ID from the profile
  AND tl.subsidiary = 7                            -- one subsidiary (base currency!)
  AND t.trandate <= TO_DATE('2026-09-30','YYYY-MM-DD')   -- balances as of a date
  -- or: AND t.postingperiod = 477                -- movements of one period
GROUP BY a.acctnumber, a.accountsearchdisplaynamecopy, a.accttype
ORDER BY a.acctnumber
```

- The join to `transactionline` is needed only for subsidiary/department/class/location.
- `debit`/`credit` are NULL when there is none - wrap with `NVL(...,0)` before arithmetic.
- `tal.amount` debit positive, credit negative.

## 4. Pagination and completeness

1. First call: `pageSize: 1000, pageIndex: 0`.
2. Read `totalResults` and `numberOfPages`.
3. Fetch pages 1..numberOfPages-1.
4. Assert fetched rows = `totalResults` before answering.
Small dimension tables (subsidiary, currency, account types) and aggregated queries with few
groups do not need paging - but still compare `resultCount` with `totalResults`.

## 5. Error messages and what they mean

| Message | Meaning | Action |
|---|---|---|
| `An unexpected SuiteScript error has occurred` | Usually one invalid column (e.g. `foreignamountremaining`) | Check fields with metadata; halve the column list until the culprit is found |
| `Record 'X' was not found` | Table not exposed to this role/connector | Use the fallback (section 6); never read as "no data" |
| `Invalid or unsupported search` | Construct not supported for this table (e.g. join + GROUP BY on link tables) | Query the table flat, aggregate yourself |
| HTTP 403 from `ns_getRecord` naming a permission | Role lacks the permission | Report the missing permission by name |
| `totalResults` > rows received | Truncated | Paginate |

## 6. Fallback matrix

| Needed | First choice | Fallback | Last resort |
|---|---|---|---|
| Period list | `accountingperiod` | `AccountPeriodActivity` (IDs + names) or `BUILTIN.DF(t.postingperiod)` | Ask the user for dates |
| Period closed/locked | `accountingperiod.closed / alllocked` | - | Say it is not readable and which permission is missing ("Manage Accounting Periods") |
| Fiscal year start | `accountingperiod` with `isyear = 'T'` | Ask once | Calendar year, stated explicitly |
| Open items | `AccountsReceivableAging` / `AccountsPayableAging` | `transaction.foreignamountunpaid` on CustInvc / VendBill (transaction currency) | A/R or A/P Aging Summary report |
| As-of-date aging in the past | A/R or A/P Aging Summary report with `dateTo` | GL control account balance as of the date | - |
| Who created / changed | `SystemNote` | `transaction.createdby / createddate / lastmodifiedby` | - |
| Document chain | `PreviousTransactionLink` / `NextTransactionLink` | `customerPaymentApplyLine` / `vendorPaymentApplyLine` | `transaction.createdfrom` if exposed |
| Consolidated figures | `BUILTIN.CONSOLIDATE` | Consolidated report (`subsidiaryId` negative) | Per subsidiary, no total |
