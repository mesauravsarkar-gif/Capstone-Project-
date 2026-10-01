# Mamaearth Returns & Growth Intelligence Pipeline

This repository is a three-layer analytics pipeline for the Mamaearth returns scenario:

1. `sql/` builds the raw relational store and SQL reports.
2. `analysis/` cleans the same raw CSVs independently with pandas, reconciles the cleaned revenue against SQL, and writes `narrator/findings.json`.
3. `narrator/` turns the verified findings into a Situation-Complication-Resolution business narrative, using Gemini when a key is available and a deterministic offline fallback otherwise.

## Repository Structure

```text
.
├── README.md
├── sql/
│   ├── schema.sql
│   ├── seed_data.sql
│   └── reports.sql
├── data/
│   ├── customers.csv
│   ├── products.csv
│   └── orders.csv
├── analysis/
│   ├── clean_and_eda.py
│   └── visualize.py
├── visualizations/
│   ├── return_rate_by_payment.png
│   └── monthly_revenue_trend.png
└── narrator/
    ├── findings.json
    ├── generate_narrative.py
    └── sample_output.txt
```

## 1. Run The SQL Layer

Use SQLite from the repository root:

```bash
sqlite3 mamaearth.db < sql/schema.sql
sqlite3 mamaearth.db < sql/seed_data.sql
sqlite3 mamaearth.db < sql/reports.sql
```

`schema.sql` creates the `customers`, `products`, and `orders` tables with primary and foreign keys. `seed_data.sql` loads the three CSV datasets into those tables with blank `discount_pct` and `rating` cells represented as SQL `NULL`.

After loading, these counts should match:

```sql
SELECT COUNT(*) FROM customers; -- 45
SELECT COUNT(*) FROM products;  -- 16
SELECT COUNT(*) FROM orders;    -- 180
```

`reports.sql` contains each required report query with the expected output pasted as comments above the query. The raw SQL revenue report produces:

```text
total_orders = 180
total_revenue = 99860.20
avg_order_value = 554.78
```

## 2. Run The Pandas Analysis Layer

Install the Python packages if needed:

```bash
pip install pandas matplotlib google-genai
```

Then run the scripts in order:

```bash
python analysis/clean_and_eda.py
python analysis/visualize.py
```

`clean_and_eda.py` reads `data/orders.csv`, `data/customers.csv`, and `data/products.csv` directly. It does not depend on the SQL database, so the SQL and pandas layers can be graded independently.

The script prints every checked result, including:

```text
orders.shape before cleaning: (180, 9)
Duplicate rows flagged: 5
Dropped order_id values: ['O0176', 'O0177', 'O0178', 'O0179', 'O0180']
Cleaned total revenue across 175 rows: INR 97,358.30
Duplicate dropped-row order_value total: INR 2,501.90
COD return rate: 44.4%
Highest-risk segment: COD + Tier-2 cities at 54.5%
True peak month after excluding outliers: 2026-03 at INR 20,318.90
```

At the end of the pandas run, Task 5 writes `narrator/findings.json`. This file is generated from the computed results, not hand-typed, so the GenAI layer receives the same verified numbers produced by the analysis layer.

`visualize.py` regenerates:

```text
visualizations/return_rate_by_payment.png
visualizations/monthly_revenue_trend.png
```

The required implementation uses Matplotlib when it is installed. A small image fallback is included only so the PNGs can still be regenerated in minimal local runtimes.

## 3. Run The GenAI Narrator

Free-path requirement: Google AI Studio provides a free Gemini API key with a free usage tier. Use that free key only; this project does not require a paid-only key. The narrator also has a fully offline fallback, so it can run with zero API spend and no network access.

To use Gemini, set one of these environment variables:

```bash
export GEMINI_API_KEY="your-free-google-ai-studio-key"
# or
export GOOGLE_API_KEY="your-free-google-ai-studio-key"
```

On Windows PowerShell:

```powershell
$env:GEMINI_API_KEY = "your-free-google-ai-studio-key"
```

Then run:

```bash
python narrator/generate_narrative.py
```

If no key is configured, or if the API call fails, the script uses `generate_scr_narrative_offline(findings)` and still produces a three-section SCR narrative. The script also runs a numeric checklist to verify that the narrative contains these required figures:

```text
97,358.30 cleaned revenue
44.4 COD return rate
54.5 COD + Tier-2 return rate
2,501.90 duplicate reconciliation delta
March and 20,318.90 true peak month
```

The latest generated narrative is saved to `narrator/sample_output.txt` for grading without a live API call.
