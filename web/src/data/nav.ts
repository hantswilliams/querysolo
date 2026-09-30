export const nav = [
  { href: '/app',         label: 'The app' },
  { href: '/how-it-runs', label: 'How it runs' },
  { href: '/medallion',   label: 'Workflows' },
  { href: '/agents',      label: 'For agents' },
  { href: '/pricing',     label: 'Pricing' },
  { href: '/docs',        label: 'Docs' },
] as const;

export const site = {
  name: 'Lakelet',
  tagline: 'A warehouse for one',
  github: 'https://github.com/hantswilliams/lakelet',
  cta: { label: 'Try Lakelet', href: '/docs/install' },
  footer: {
    left: 'Lakelet · Open source under Apache 2.0 · Developer preview, macOS and Linux',
    right: 'Built on DuckDB, Apache Iceberg and dbt Core',
  },
  stackOptions: ['Snowflake', 'BigQuery', 'Databricks', 'MotherDuck', 'DuckDB on my laptop', 'Postgres', 'Other'],
};
