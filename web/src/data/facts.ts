// Dated, verified facts used on the landing page and the engineers section.
//
// Two kinds, and the second kind is the one a visitor cannot get anywhere else:
// what the industry did, and what QuerySolo did. Keep both dated, keep both checkable,
// and never put a fact here that /docs would contradict (web/TASKS.md, item 5).
export const facts = [
  { date: 'May 29, 2026', title: 'DuckDB 1.5 writes Iceberg',
    body: 'MERGE INTO, ALTER TABLE, bucket() and truncate() partition transforms, Iceberg V3 deletion vectors and row lineage, from an embedded engine against any REST catalog.' },
  { date: 'Aug 26, 2026', title: 'AWS acquires DuckLabs; DuckDB stays MIT',
    body: 'The company was acquired. The DuckDB project was explicitly not, and remains under the independent DuckDB Foundation.' },
  { date: 'Feb 19 · Apr 13 · Jun 2026', title: 'The open catalog and open dbt are settled',
    body: 'Apache Polaris became a Top-Level Project; DuckLake 1.0 shipped; dbt Core is Apache 2.0 with no usage limits.' },
  { date: 'Sep 8, 2026', title: 'Spark and Trino read what QuerySolo writes',
    body: "Both engines verified against QuerySolo's own Iceberg REST catalog through `querysolo catalog serve`, with Postgres as a second catalog dialect. The lock-in test is whether another engine can read your tables without QuerySolo; it can." },
  { date: 'Sep 11, 2026', title: '472 million rows attached with no AWS account',
    body: "Overture Maps' public bucket, read in place: 32 files, 21.9 GB, nothing copied, no credentials. The gauge then priced a bounding-box query at 8 seconds from the manifests it had written; it ran in 4.1." },
] as const;
