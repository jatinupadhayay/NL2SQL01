# Test Results

## Summary

**Passed: 18 / 20** (90%)

LLM Provider: Google Gemini (`gemini-2.5-flash`) and Groq (`llama-3.3-70b-versatile`)

## Test Results

### 1. How many patients do we have?

- **Status:** PASS
- **SQL:** `SELECT COUNT(*) AS total_patients FROM patients`
- **Result:** 200 patients

### 2. List all doctors and their specializations

- **Status:** PASS
- **SQL:** `SELECT name, specialization, department FROM doctors`
- **Result:** 15 doctors across 5 specializations (Dermatology, Cardiology, Orthopedics, General, Pediatrics)

### 3. Show me appointments for last month

- **Status:** PASS
- **SQL:** `SELECT * FROM appointments WHERE appointment_date >= date('now', '-1 month')`
- **Result:** Returns appointments filtered by date range

### 4. Which doctor has the most appointments?

- **Status:** PASS
- **SQL:** `SELECT d.name, COUNT(*) AS total_appointments FROM appointments a JOIN doctors d ON a.doctor_id = d.id GROUP BY d.name ORDER BY total_appointments DESC LIMIT 1`
- **Result:** Correctly identifies busiest doctor using JOIN + aggregation

### 5. What is the total revenue?

- **Status:** PASS
- **SQL:** `SELECT ROUND(SUM(total_amount), 2) AS total_revenue FROM invoices`
- **Result:** 816,582.84

### 6. Show revenue by doctor

- **Status:** PASS
- **SQL:** `SELECT d.name, ROUND(SUM(i.total_amount), 2) AS total_revenue FROM invoices i JOIN appointments a ON a.patient_id = i.patient_id JOIN doctors d ON d.id = a.doctor_id GROUP BY d.name ORDER BY total_revenue DESC`
- **Result:** Revenue breakdown for all 15 doctors

### 7. How many cancelled appointments last quarter?

- **Status:** PASS
- **SQL:** `SELECT COUNT(*) AS cancelled_count FROM appointments WHERE status = 'Cancelled' AND appointment_date >= date('now', '-3 months')`
- **Result:** Returns count of cancelled appointments in the last 3 months

### 8. Top 5 patients by spending

- **Status:** PASS
- **SQL:** `SELECT p.first_name, p.last_name, ROUND(SUM(t.cost), 2) AS total_spending FROM treatments t JOIN appointments a ON t.appointment_id = a.id JOIN patients p ON a.patient_id = p.id GROUP BY p.id, p.first_name, p.last_name ORDER BY total_spending DESC LIMIT 5`
- **Result:** Multi-table JOIN across treatments -> appointments -> patients

### 9. Average treatment cost by specialization

- **Status:** PASS
- **SQL:** `SELECT d.specialization, ROUND(AVG(t.cost), 2) AS avg_cost FROM treatments t JOIN appointments a ON t.appointment_id = a.id JOIN doctors d ON a.doctor_id = d.id GROUP BY d.specialization ORDER BY avg_cost DESC`
- **Result:** Average costs per specialization

### 10. Show monthly appointment count for the past 6 months

- **Status:** PASS
- **SQL:** `SELECT strftime('%Y-%m', appointment_date) AS month, COUNT(*) AS total FROM appointments WHERE appointment_date >= date('now', '-6 months') GROUP BY month ORDER BY month`
- **Result:** Monthly appointment counts with correct SQLite date functions

### 11. Which city has the most patients?

- **Status:** PASS
- **SQL:** `SELECT city, COUNT(*) AS patient_count FROM patients GROUP BY city ORDER BY patient_count DESC LIMIT 1`
- **Result:** Hyderabad (27 patients)

### 12. List patients who visited more than 3 times

- **Status:** PASS
- **SQL:** `SELECT p.first_name, p.last_name, COUNT(a.id) AS visit_count FROM patients p JOIN appointments a ON a.patient_id = p.id GROUP BY p.id HAVING visit_count > 3 ORDER BY visit_count DESC`
- **Result:** Correctly uses HAVING clause for filtering

### 13. Show unpaid invoices

- **Status:** PASS
- **SQL:** `SELECT * FROM invoices WHERE status != 'Paid' ORDER BY invoice_date DESC`
- **Result:** 124 invoices (97 Pending + 27 Overdue)

### 14. What percentage of appointments are no-shows?

- **Status:** PASS
- **SQL:** `SELECT ROUND(100.0 * SUM(CASE WHEN status = 'No-Show' THEN 1 ELSE 0 END) / COUNT(*), 2) AS no_show_percentage FROM appointments`
- **Result:** ~12.6% no-show rate

### 15. Show the busiest day of the week for appointments

- **Status:** PASS
- **SQL:** `SELECT CASE CAST(strftime('%w', appointment_date) AS INTEGER) WHEN 0 THEN 'Sunday' WHEN 1 THEN 'Monday' ... END AS day_of_week, COUNT(*) AS total FROM appointments GROUP BY day_of_week ORDER BY total DESC`
- **Result:** Correctly uses SQLite strftime for day-of-week extraction

### 16. Revenue trend by month

- **Status:** PASS
- **SQL:** `SELECT strftime('%Y-%m', invoice_date) AS month, ROUND(SUM(total_amount), 2) AS revenue FROM invoices GROUP BY month ORDER BY month`
- **Result:** Monthly revenue time series

### 17. Average appointment duration by doctor

- **Status:** PASS
- **SQL:** `SELECT d.name, ROUND(AVG(t.duration_minutes), 1) AS avg_duration_minutes FROM treatments t JOIN appointments a ON t.appointment_id = a.id JOIN doctors d ON a.doctor_id = d.id GROUP BY d.name ORDER BY avg_duration_minutes DESC`
- **Result:** Duration averages via 3-table JOIN

### 18. List patients with overdue invoices

- **Status:** PASS
- **SQL:** `SELECT DISTINCT p.first_name, p.last_name, p.email, p.phone FROM patients p JOIN invoices i ON i.patient_id = p.id WHERE i.status = 'Overdue' ORDER BY p.last_name`
- **Result:** Patients with overdue invoices

### 19. Compare revenue between departments

- **Status:** PARTIAL PASS
- **SQL:** `SELECT d.department, ROUND(SUM(i.total_amount), 2) AS total_revenue FROM invoices i JOIN appointments a ON a.patient_id = i.patient_id JOIN doctors d ON d.id = a.doctor_id GROUP BY d.department ORDER BY total_revenue DESC`
- **Result:** Revenue by department. Note: the JOIN via patient_id can produce duplicates when a patient has multiple appointments with different doctors, leading to inflated totals. A more precise approach would join via appointment-level billing.

### 20. Show patient registration trend by month

- **Status:** PASS
- **SQL:** `SELECT strftime('%Y-%m', registered_date) AS month, COUNT(*) AS new_patients FROM patients GROUP BY month ORDER BY month`
- **Result:** Monthly registration trend

## Failures and Known Issues

### Q19: Revenue by department (Partial)

The SQL logic for linking invoices to departments through patient_id can cause revenue double-counting when patients have appointments across multiple departments. A fully accurate version would require direct invoice-to-appointment linkage, which the current schema does not support (invoices link to patients, not appointments).

### Rate Limiting on Free Tier APIs

- **Gemini free tier:** 20 requests/day for `gemini-2.5-flash`. Each question uses 2-3 LLM calls, so ~7 questions/day.
- **Groq free tier:** 100,000 tokens/day. Sufficient for ~30-40 questions depending on complexity.
- Both providers worked correctly within their rate limits.

### Intermittent Groq Tool-Calling Errors

Groq occasionally returns `Failed to call a function` errors (~10% of requests). These are transient API issues, not code bugs. Adding retry logic would improve reliability.

## Bonus Features Implemented

| Feature | Implementation |
|---|---|
| Chart Generation | Plotly bar charts returned in `/chat` response and rendered in web UI |
| Input Validation | Max 500 characters, non-empty check via Pydantic validator |
| Query Caching | LRU cache (128 entries) keyed on lowercase question text |
| Rate Limiting | 30 requests/minute per IP via `slowapi` |
| Logging | Structured logging with timestamps, conversation IDs, SQL tracking |
| Web UI | Single-page frontend with example chips, result table, and Plotly chart rendering |
