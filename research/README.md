# Research

Articles read for the build, with what each changed. The copies themselves (PDFs saved from
the browser) are gitignored: this is a public repository and they are other people's work.
The decisions they led to are in `build-sessions/decisions-for-review_<MMDDYY>.md`.

## September 15, 2026 (`decisions-for-review_091526.md`, V1 to V4)

| Article | Date | Takeaway for Lakelet |
|---|---|---|
| DataExpert, [DuckDB Just Put a $400K/Year Skill on Your Laptop](https://medium.com/@dataexpert/duckdb-just-put-a-400k-year-skill-on-your-laptop-fc4c86201a44) (Medium) | Sep 3, 2026 | The thesis in someone else's words: DuckDB 1.5.3 Iceberg writes + Iceberg maturity + dbt Core = a laptop lakehouse. Its "honest gap" list is a roadmap audit: concurrent writes (our catalog), lineage (versions round step 4), run observability (history), and small-file / delete-file accumulation with no compaction (V2). Market figures unverified; none used. |
| VeloDB, [Apache Doris 4.1 on Iceberg V3](https://medium.com/towards-data-engineering/apache-doris-4-1-on-iceberg-v3-running-the-full-lakehouse-lifecycle-from-one-sql-engine-0530fc178067) (Towards Data Engineering) | Sep 2, 2026 | Under format-version 2 every `DELETE` is a position-delete file anti-joined on read; V3 deletion vectors keep read cost flat, and row lineage gives a per-row watermark. Our `table` materialisation is `DELETE` then `INSERT` per run on V2 tables (V1, V2). |
| Arshad Ansari, [Is DuckDB safe for production? The honest limitations](https://publication.hikmahtechnologies.com/is-duckdb-safe-for-production-the-honest-limitations-2d1e776eb7e8) (Hikmah Techstack) | Sep 11, 2026 | The recommended shape (immutable Parquet, read-only readers, the `.duckdb` file a cache) is Lakelet's shape; one durability sentence for the docs and the site (V4). |
| Shawn Gordon, [What the Heck is Renart?](https://progrockrec.medium.com/what-the-heck-is-renart-fc428c6f4849) (Medium) | Sep 7, 2026 | The nearest comparable: Git-native, files-as-assets, a desktop window, public alpha. Its content-fingerprint staleness ("Build stale") is one field and one selector for us once lineage lands (V3). It is an IDE over a warehouse; Lakelet is the warehouse (V4). |

## September 24 to 26, 2026 (`lakelet-build-sessions_092426b.md` §1, `website-story-v2-plan.md` W10)

| Article | Date | Takeaway for Lakelet |
|---|---|---|
| Amina Okanovic, [DuckLake didn't fix Iceberg's metadata bottleneck. It moved it into a single Postgres instance](https://medium.com/@kabirbakovic/ducklake-didnt-fix-iceberg-s-metadata-bottleneck-it-moved-it-into-a-single-postgres-instance-342443419c09) (Medium) | Sep 7, 2026 | Iceberg serialises on one pointer swap per commit; DuckLake on a multi-row transaction in a shared database, which fails on connections and retries before metadata volume. Her table calls a SQLite-backed DuckLake "local dev only", and a reader may apply that to us: the site says "one writer" first. The site's "why Iceberg" line: the tables outlive the tool. `remote-catalog-plan.md` R4 must be sized for connections. Her figures come from DuckLake issues and DuckDB Labs; none used. |
| Nazmul Hasan, [I appended 5,000 rows 200 times. Iceberg wrote more metadata than data](https://blog.gopenai.com/i-appended-5-000-rows-200-times-iceberg-wrote-more-metadata-than-data-beb03fe734a9) (GoPenAI) | Sep 10, 2026 | Our stack (pyiceberg 0.12 SqlCatalog on SQLite, DuckDB 1.5.5), no maintenance: 19.41 MB of metadata for 15.0 MB of data, 806 files, a full scan 27 ms → 223 ms. The objection a technical reader brings: the site claims no "maintenance-free" anything, names `expire`, and does not claim compaction, which is not built. His script is the natural gate for V2. |
| Dean J Murphy, [What the heck is Duckle](https://dean-joseph-murphy.medium.com/what-the-heck-is-duckle-1ca049ba895e) (Medium) | Sep 24, 2026 | A no-code ETL canvas over DuckDB with a local assistant; no table format, catalog, versions or dbt. The comparison row in `marketing/warehouse-for-one.md` §7; no connector-count race. |
| Harsh Gupta, [Why Direct Lake isn't the magic bullet everyone promised](https://medium.com/@harsh1995hg/why-direct-lake-isnt-the-magic-bullet-everyone-promised-a-senior-bi-post-mortem-514e00b73b5f) (Medium) | Sep 24, 2026 | Power BI's Direct Lake falls back to DirectQuery without a warning. The framing, not the product: the verdict is the opposite of a silent fallback ("No silent fallback" on the home page). His "800 ms → 25 s" has no source; not used. |
