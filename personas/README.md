# Personas

One file per person the product is for: who they are, the tools their day already runs on, what hurts, the scenarios where the product enters that day, where they hit a wall today, and the questions only a recorded session with a real one of them can answer. The point is the last column of every scenario: does the product fit the workflow they already have, or does it ask them to change it. Started 2026-09-24 (`build-sessions/lakelet-build-sessions_092426b.md`).

## Rules for this folder

- **Assumed or observed.** Every file says which it is at the top. A persona is *assumed* until an outsider session (`decisions-for-review_092426.md` N3, step 2) has been recorded with one; then the file gains a "What we saw" section and the assumptions that were wrong are struck, not deleted.
- **Built or planned.** Every scenario ends with which parts are on `main` today and which wait on a named brief or decision. The README's status block is the authority on "built".
- **A persona changes the build order only through a decisions file.** A file here can say "this suggests the warehouse door should open on BigQuery before Postgres"; it cannot decide it. The tick box lives in `build-sessions/decisions-for-review_<MMDDYY>.md`.
- **No names, no partner data.** A persona is a composite. A recorded session is summarised, never transcribed, and the person is not identifiable.
- **The product name** is QuerySolo (QuerySolo until 2026-09-30).

## The personas

| File | Who | Status |
|---|---|---|
| `analyst-bigquery-databricks.md` | The mid-tier analyst whose day runs on BigQuery or Databricks | assumed, 2026-09-24 |
| `analyst-files-no-warehouse.md` | The solo analyst or data scientist with files, a bucket, or a warehouse they do not own, and no dbt project: N1's first user; the PRD's P3 where they write SQL | assumed, 2026-09-24 |
| `dbt-person-small-team.md` | The dbt person, solo or in a team of two to ten, whose data fits on a machine: the PRD's P1 and N1's second reader | assumed, 2026-09-24 |
| `data-scientist-notebook.md` | The notebook person: pandas, a Jupyter kernel, a slice of a warehouse; the solo analyst's fourth composite seen from the cell | assumed, 2026-09-24 |
| `learner.md` | Building portfolio projects for a lakehouse job, and the instructor with a classroom: the PRD's P2 | assumed, 2026-09-24 |
| `coding-agent.md` | The agent that runs SQL on a person's behalf, read-only by default, under a budget: `docs/lakelet-agent-first-strategy.md` | assumed, 2026-09-24 |

## The template

    # <The persona, as a phrase>
    *Persona · written <date> · Status: assumed | observed on <date> · Product name: QuerySolo*
    ## Who
    ## Tools, and where the day goes        (a table: task | tool | what they see)
    ## What hurts
    ## Scenarios                              (each: the situation; today; with the product; built / planned)
    ## Where this persona hits walls today
    ## What this suggests for the order      (suggestions, not decisions)
    ## Questions for the outsider session
    ## What we saw                            (only after a recorded session)
