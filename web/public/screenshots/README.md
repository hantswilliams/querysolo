# Screenshots

Unedited captures of the real QuerySolo React application in its browser test harness — the
same page the desktop window loads — backed by a real `querysolo serve`, at 2x. Nothing is
mocked: the rows, the verdict and the chart are the core's answers. Taken September 30,
2026 with `app/scripts/screenshots.mjs`, which is the whole recipe; run it again after a
UI change.

Only generated data from `examples/sample-data/make_sample.py` is shown: 5,000 orders for
a fictional lakeside shop, three saved questions over them. No real records, storage
credentials or sidecar tokens appear. The sample CSVs and the throwaway project stay
outside the repository. The timings describe those runs only.

| file | what it shows |
|---|---|
| `workspace.png`, `workspace-dark.png` | the Tables screen: SQL over the verdict, the chart and the rows; light and dark |
| `workspace-line.png` | a two-column date answer, charted as a line |
| `detail.png` | a table's detail in the results pane (columns, snapshots, what it feeds) |
| `questions.png` | the Questions screen in Simple mode, with **See the answer** |
| `answer.png` | a question's answer: `select * from revenue_by_region`, run |
| `models.png` | the Models screen in Technical mode, a model's detail with its versions |
| `lineage.png` | the Lineage screen |
| `changes.png` | the Changes screen |
| `gauge.png` | the Gauge screen: estimate against actual on this machine |
