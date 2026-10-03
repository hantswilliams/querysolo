# Sample data

A small made-up dataset to try QuerySolo on: a lakeside shop's orders. Nothing here is
real, and no data file is committed (the repo's rule); the script writes the files where
you ask, the same bytes every time.

```bash
python3 examples/sample-data/make_sample.py               # writes ~/querysolo-demo/sample
python3 examples/sample-data/make_sample.py ~/elsewhere   # or anywhere
```

Four CSV files, about 500 KB in all: `orders.csv` (5,000 rows, January to September 2026),
`customers.csv` (200), `products.csv` (12), `daily_sales.csv` (250 days), plus a `notes.txt`
the importer skips.

## Things to try in the app

Drop the whole `sample` folder on the window: the preview lists the four files with their
columns and types (the `.txt` is left out), one click imports four tables. Or drop one file.

Then in the SQL box:

```sql
-- a bar chart: one categorical column, one numeric
select region, round(sum(amount)) as revenue from orders where status = 'paid' group by 1 order by 2 desc;

-- another
select category, count(*) as orders from orders group by 1 order by 2 desc;

-- a line chart: a date and a numeric
select day, revenue from daily_sales order by day;

-- a join; more than two columns, so no chart, just the grid
select c.name, c.region, count(*) as orders, round(sum(o.amount), 2) as spent
from orders o join customers c using (customer_id)
where o.status = 'paid' group by 1, 2 order by spent desc limit 20;

-- refunds by product
select product, count(*) as refunds from orders where status = 'refunded' group by 1 order by 2 desc;
```

The same from a terminal:

```bash
cd ~/querysolo-demo
querysolo import sample
querysolo sql "select region, round(sum(amount)) as revenue from orders where status = 'paid' group by 1 order by 2 desc"
```

Bigger: `--orders 200000` writes a 20 MB `orders.csv`; the gauge line stays Green on a
laptop but the grid's 100,000-row cap shows itself on `select * from orders`.
