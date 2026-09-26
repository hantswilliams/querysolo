# The label against the six personas

*2026-09-24 · The personas are in `personas/`, all assumed and none observed; the page never names them. This file says what each one hears when the page says "a warehouse for one", which section was written for them, which feature wins their comparison, which wall the page discloses, and which door they walk through.*

## In one table

| Persona (`personas/`) | Is "for one" true for them | The sentence they hear | Section written for them | The feature that wins | The wall we disclose | Their door |
|---|---|---|---|---|---|---|
| The solo analyst with files (`analyst-files-no-warehouse.md`) | wholly | "mine, on my laptop, nothing uploaded" | 1, 2, 3, 6 | the verdict; tables in seconds with types kept; versions | from source until the installer; SQL required | a file |
| The data scientist in a notebook (`data-scientist-notebook.md`) | wholly | "one machine, pull once" | 2, 4 | the memory warning before the pull; snapshots; any engine reads (pyiceberg) | no cell entry yet; no PyPI yet | a file, then a bucket |
| The learner (`learner.md`) | wholly | "free, mine, no card, the real stack" | 1, 6, 8, 9 | the real stack in ten minutes; offline; the verdict as the teacher | from source; Windows | a file |
| The dbt person in a small team (`dbt-person-small-team.md`) | true, with the disclosure | "solo today, and they said so" | 7, then 3's second sentence, then 5 | the DAG by verdict; run only what is stale; the Changes feed; no credits | open-an-existing-project not built; one writer; no team | a bucket, or a file |
| The analyst on BigQuery or Databricks (`analyst-bigquery-databricks.md`) | today, partly | "the minutes and a refusal, and nothing uploaded" | 2's comparison line, 4, 6's third card | the verdict with seconds and a refusal; nothing uploaded | Windows; GCS; the slice not built | a file today; the third door when it exists |
| The coding agent (`coding-agent.md`) | for one person's agent | "cost before the run, a refusal it cannot argue with" | 5, the Agents page | the estimate before the query; the exit code; `AGENTS.md` | no budget; no MCP | the CLI and the API |

## What the table says

**"For one" is wholly true for three of six** and they are the free tier: the solo analyst, the data scientist, the learner. The page is written for them first, which is what N1 decided, and nothing on it needs a caveat for them beyond the installer and Windows.

**For the dbt person it is true only because the page says it.** Section 7 exists for them. Without it they find the one-writer boundary in an hour and read the silence as a claim. With it, "for one" is a fact they were told, and the arc "then for a team" is a reason to come back. Section 3's second sentence is the other thing they need to hear: the model they wrote gets a verdict, its checks, a version and a state, and nobody wrote it for them.

**For the platform analyst it is partly true today and wholly true at Day 2.** Today they walk through the file door with the export somebody sent, and the comparison line in section 2 is the thing they repeat to a colleague. Their real page, "the local half of your warehouse", waits on the third door and on routing, and the page marks that card planned rather than pretending. Their walls are the ones the page cannot fix with words: Windows and GCS.

**For the agent, "one" is the person it works for.** The page's fifth section, every button a command, is their section without saying so, and the Agents page carries the rest. The budget is the feature that makes them a customer and it is marked planned.

## How the three beats land, per persona

| Beat | Solo analyst | Data scientist | Learner | dbt person | Platform analyst | Agent |
|---|---|---|---|---|---|---|
| Know what fits | the six-gigabyte file, before | the pull, before | the lesson | a verdict per model | the minutes and the refusal | the estimate tool |
| Know what changed | last month against this month, and why the number moved | which snapshot trained it | which run made which number | run only what is stale; a changed table counts; the feed | the number in the deck has a commit behind it | the saved question and its diff at review |
| Nothing leaves, any engine reads | the NDA, the folder as backup | pyiceberg from the cloud notebook | offline in the classroom | Spark and Trino read the same tables | nothing uploaded; BigLake and Unity read Iceberg | credentials never in the folder |

## The routing, without naming anyone

The page routes by door, not by title. *A file* catches the solo analyst, the learner, the data scientist with an export, and the platform analyst on their first day. *A bucket* catches the dbt person with Parquet already there, the data scientist with a lake, the researcher with public data. *A warehouse you do not own* is the card that tells the platform analyst and the small-company analyst with a replica that we know they exist, and that it is planned. Nobody is asked what they are.

## What the personas say the page is missing, and what we do about it

- **The installer and Windows** gate three personas and no copy fixes that; the ship brief does. The page says "from source" and "macOS and Linux" until it changes.
- **A Python entry point** for the data scientist is not on the page because it is not built; when it is, section 5 gains one line and PyPI becomes their call to action.
- **The tutorial** the learner needs is content, not the page; the quickstart stands in until it exists.
- **The slice** three personas want most is the one planned card on the page, deliberately visible.
- **The budget** the agent needs is on the Agents page as planned, and the business model argues for moving it up; the page follows the build, not the other way round.
