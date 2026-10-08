# 04 - Receivables, payables, payments and document research

## Contents
1. Open items and aging (OP-Liste, Altersstruktur)
2. Reconciling subledger and general ledger
3. Unapplied payments and credits
4. Payment forecast and KPIs
5. Document research: find, chain, audit trail

---

## 1. Open items and aging

Source: `AccountsReceivableAging` (AR) and `AccountsPayableAging` (AP), one row per open document.
Amounts are in the subsidiary's base currency - aggregate per subsidiary.

```sql
SELECT BUILTIN.DF(ar.subsidiary) AS subsidiary, BUILTIN.DF(ar.subsidiaryBookCurrency) AS currency,
       BUILTIN.DF(ar.entity) AS customer, BUILTIN.DF(ar.transactionType) AS doc_type,
       ar.documentNumber, TO_CHAR(ar.transactionDate,'YYYY-MM-DD') AS doc_date,
       TO_CHAR(ar.dueDate,'YYYY-MM-DD') AS due_date,
       TO_DATE('2026-10-08','YYYY-MM-DD') - ar.dueDate AS days_overdue,
       ar.openBalance
FROM AccountsReceivableAging ar
WHERE ar.accountingBook = 1
  AND ar.transactionDate <= TO_DATE('2026-10-08','YYYY-MM-DD')   -- exclude future-dated documents
ORDER BY 1, 3, ar.dueDate
```
For AP use `AccountsPayableAging` - same fields; vendor is `entity` (there is no `vendor` field).

Buckets (by due date against the as-of date) - compute in SQL for summaries:
```sql
SUM(CASE WHEN TO_DATE('2026-10-08','YYYY-MM-DD') - ar.dueDate <= 0 THEN ar.openBalance ELSE 0 END) AS not_due,
SUM(CASE WHEN TO_DATE('2026-10-08','YYYY-MM-DD') - ar.dueDate BETWEEN 1 AND 30 THEN ar.openBalance ELSE 0 END) AS d1_30,
SUM(CASE WHEN TO_DATE('2026-10-08','YYYY-MM-DD') - ar.dueDate BETWEEN 31 AND 60 THEN ar.openBalance ELSE 0 END) AS d31_60,
SUM(CASE WHEN TO_DATE('2026-10-08','YYYY-MM-DD') - ar.dueDate BETWEEN 61 AND 90 THEN ar.openBalance ELSE 0 END) AS d61_90,
SUM(CASE WHEN TO_DATE('2026-10-08','YYYY-MM-DD') - ar.dueDate > 90 THEN ar.openBalance ELSE 0 END) AS d90_plus
```
- If the user asks for "0-30 Tage", state whether you age by due date (default, = overdue days)
  or by document date, and keep "not yet due" as its own column when ageing by due date.
- Payments and credit memos appear as negative rows; keep them in the list (they reduce the
  customer's balance) and also report them separately (section 3).
- Rows with `transactionDate` after the as-of date are future-dated: excluded above; count them
  and mention the count.

**Important limit:** `openBalance` is the open amount **today**, after all payments booked so far
- including future-dated payments. For an as-of date in the past, or when future-dated payments
exist, take the totals from the report "A/R Aging Summary" / "A/P Aging Summary" with
`dateTo` = as-of date, and use the table only for document detail. Say which source the totals
come from.

## 2. Reconciling subledger and general ledger

Three numbers per subsidiary, as of the same date:
1. Aging total (table, documents dated up to the as-of date).
2. GL control account balance:
```sql
SELECT BUILTIN.DF(tl.subsidiary) AS subsidiary, a.accttype, SUM(tal.amount) AS gl_balance
FROM transactionaccountingline tal
JOIN transaction t      ON t.id = tal.transaction
JOIN transactionline tl ON tl.transaction = tal.transaction AND tl.id = tal.transactionline
JOIN account a          ON a.id = tal.account
WHERE tal.posting = 'T' AND tal.accountingbook = 1
  AND a.accttype IN ('AcctRec','AcctPay')
  AND t.trandate <= TO_DATE('2026-10-08','YYYY-MM-DD')
GROUP BY BUILTIN.DF(tl.subsidiary), a.accttype
```
   AR: GL balance should equal the aging total. AP: GL balance is negative; compare its absolute
   value with the aging total.
3. Report "A/R Aging Summary" / "A/P Aging Summary" total (row `"0"`, column
   `empty > Open Balance`).

Verified on the demo account, 2026-10-08: Australia, Canada, France, Germany, United Kingdom tie
exactly on all three for AR and AP. United States does not (AR: aging table 436,432.89 · GL
537,557.18 · report 542,836.95). Typical causes to check and name:
- future-dated payments already reducing `openBalance` in the table;
- journal entries posted to AR/AP without a customer/vendor (report row "- No Customer/Project -");
- foreign-currency open items revalued in the GL but not in the subledger, or vice versa;
- documents in another accounting book.
Report the difference with its likely cause; never adjust numbers to make them tie.

## 3. Unapplied payments and credits

```sql
SELECT BUILTIN.DF(ar.subsidiary) AS subsidiary, BUILTIN.DF(ar.entity) AS customer,
       BUILTIN.DF(ar.transactionType) AS doc_type, ar.documentNumber,
       TO_CHAR(ar.transactionDate,'YYYY-MM-DD') AS doc_date, ar.openBalance
FROM AccountsReceivableAging ar
WHERE ar.openBalance < 0 AND ar.accountingBook = 1
ORDER BY ar.openBalance
```
Alternative on the documents: `transaction.foreignpaymentamountunused` (`CustPymt`) or
`transactionaccountingline.paymentamountunused`. These are follow-up items for the close
(apply or refund).

## 4. Payment forecast and KPIs

- **Cash-in / cash-out forecast:** open items (as of today, posted, not future-dated) grouped by
  due week or month: `TO_CHAR(ar.dueDate,'IYYY-IW')` or `TO_CHAR(ar.dueDate,'YYYY-MM')`, per
  subsidiary. Overdue items go into a separate "overdue now" bucket, not into past weeks.
- **Top debtors/creditors:** group by `entity`, order by open amount, per subsidiary.
- **DSO** (days sales outstanding) = AR balance / revenue of the last 90 days x 90. **DPO**
  analogously with AP and COGS + expenses. Show the formula used.
- Invoice-level fields if needed: `transaction.foreignamountunpaid`, `foreignamountpaid`,
  `foreigntotal`, `daysoverduesearch`, `duedate` (transaction currency).

## 5. Document research

### Find the document
```sql
SELECT t.id, t.tranid, t.type, BUILTIN.DF(t.status) AS status,
       TO_CHAR(t.trandate,'YYYY-MM-DD') AS doc_date, TO_CHAR(t.duedate,'YYYY-MM-DD') AS due_date,
       BUILTIN.DF(t.postingperiod) AS period, BUILTIN.DF(t.entity) AS partner,
       BUILTIN.DF(t.currency) AS currency, t.foreigntotal, t.foreignamountunpaid,
       BUILTIN.DF(t.approvalstatus) AS approval, t.voided,
       BUILTIN.DF(t.createdby) AS created_by, TO_CHAR(t.createddate,'YYYY-MM-DD HH24:MI') AS created_at,
       BUILTIN.DF(t.lastmodifiedby) AS modified_by, TO_CHAR(t.lastmodifieddate,'YYYY-MM-DD HH24:MI') AS modified_at
FROM transaction t
WHERE t.tranid = 'SS-2026-104'
```
`tranid` is not unique across types (an invoice and a bill can share a number) - if several rows
come back, ask or show all. Subsidiary: join `transactionline` with `mainline = 'T'`.
`foreigntotal` is negative for bills and bill credits - present the absolute value.

### Follow the chain
Query the link tables **flat** by document ID, in both directions, then load each linked document
with the query above:
```sql
SELECT ptl.linktype, ptl.previousdoc, BUILTIN.DF(ptl.previousdoc) AS previous_doc,
       ptl.nextdoc, BUILTIN.DF(ptl.nextdoc) AS next_doc, ptl.foreignamount
FROM PreviousTransactionLink ptl
WHERE ptl.nextdoc = 28677 OR ptl.previousdoc = 28677
```
Typical chains: Sales Order → Item Fulfillment → Invoice → Customer Payment / Credit Memo;
Purchase Order → Item Receipt → Bill → Bill Payment. No link row means no linked document (e.g. a
bill entered without a purchase order) - say so.
Verified: bill SS-2026-104 → link type "Payment" → "Bill Payment #2"; no purchase order.

### Audit trail (who did what, when)
```sql
SELECT TO_CHAR(sn.date,'YYYY-MM-DD') AS changed_on, BUILTIN.DF(sn.name) AS changed_by,
       sn.type, sn.field, sn.oldvalue, sn.newvalue, sn.context
FROM SystemNote sn
WHERE sn.recordid = 28677 AND sn.recordtypeid = -30
ORDER BY sn.date
```
- `type` 1 = created, 2 = field set at creation, 4 = field changed later. Summarise type 1 and
  type 4; list type 2 only for fields that matter (amount, date, period, entity, status).
- Field codes are internal (`TRANDOC.MAMOUNTMAIN` amount, `TRANDOC.DDATE` date,
  `TRANDOC.KPERIOD` period, `TRANDOC.KSTATUS` status, `TRANDOC.KENTITYMAIN` partner) - translate
  them into plain words.
- Values in system notes reflect the moment of the change; if they differ from the current
  header (e.g. period), report both and say the current value is authoritative.
- If `SystemNote` is not readable, fall back to `createdby / createddate / lastmodifiedby /
  lastmodifieddate` and say that the field-level history is not available.

### Requests to change the document
Void, cancel, approve, re-date, pay: this skill only reads. Decline in one sentence and name the
place in NetSuite (open the document → Edit, Void, or Approve, depending on role permissions).
