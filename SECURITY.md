# Security

QuerySolo is a developer preview. It runs on your machine, binds loopback only, and sends nothing anywhere unless you ask; `PRIVACY.md` says exactly what that means. If you find a way around any of it, please tell us privately first.

## Reporting a vulnerability

Use GitHub's private advisory form: **Security → Report a vulnerability** on github.com/hantswilliams/querysolo. That reaches the maintainer without a public issue.

If you cannot use the form, email hantsawilliams@gmail.com with "querysolo security" in the subject.

Please include the QuerySolo and DuckDB versions (`querysolo --version`), the operating system, and the steps; a project folder that reproduces it is ideal, but never send data you would not post publicly.

## What to expect

You will get an acknowledgement within a week during the preview. A confirmed report is fixed in a release before it is described anywhere, and you are credited unless you ask not to be. There is no bounty programme.

## In scope

- Anything that makes `querysolo serve` or `querysolo catalog serve` reachable from a page in a browser or from another machine (see the refusals in `PRIVACY.md`).
- Anything that makes QuerySolo send data off the machine without an explicit verb asking for it.
- A way for an `import`, `attach`, `refresh` or `run` to lose or silently corrupt a table.
- The bearer token leaking anywhere but `.querysolo/serve.json`.

## Out of scope

- SQL you run yourself doing what DuckDB lets SQL do (reading local files, reaching the network): that is the engine working as documented. The agent path (`querysolo mcp`) will lock this down when it exists.
- Vulnerabilities in DuckDB, pyiceberg, dbt or their extensions; report those upstream, and tell us so we can pin a fixed version.
