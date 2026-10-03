// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

const base = process.env.SITE_BASE || '/querysolo/';

// Markdown pages (the docs) link with root-relative paths such as /docs/cli, and show
// images from /screenshots; on GitHub
// Pages the site lives under /querysolo/, so prefix them the way src/lib/url.ts does for
// .astro pages. Hand-rolled walk rather than a dependency: the tree is small.
function rehypeBasePath() {
  const prefix = base.replace(/\/$/, '');
  const walk = node => {
    if (node.type === 'element' && (node.tagName === 'a' || node.tagName === 'img')) {
      const key = node.tagName === 'a' ? 'href' : 'src';
      const value = node.properties?.[key];
      if (typeof value === 'string' && value.startsWith('/') && !value.startsWith('//')) node.properties[key] = prefix + value;
    }
    node.children?.forEach(walk);
  };
  return tree => { if (prefix) walk(tree); };
}

// A deploy with no waitlist endpoint captures nothing. That happened once (the forms
// reported success and dropped every signup between 2026-09-09 and 2026-09-11), so the
// build says so rather than letting it pass quietly. See web/TASKS.md, item 1.
if (!process.env.PUBLIC_WAITLIST_URL) {
  console.warn(
    '\n  ⚠ PUBLIC_WAITLIST_URL is not set: the waitlist forms will tell visitors that signups\n' +
    '    are not open rather than collecting anything. Set it as a repo variable\n' +
    '    (Settings → Secrets and variables → Actions → Variables) to a Formspree endpoint,\n' +
    '    e.g. https://formspree.io/f/<id>. Local dev: put it in web/.env\n'
  );
}

// https://astro.build/config
export default defineConfig({
  // SITE_URL / SITE_BASE are set by the GitHub Pages workflow (see .github/workflows/deploy-pages.yml).
  // The default is where the site actually lives today: the project page at <owner>.github.io/<repo>.
  // It is NOT a custom domain, because none is owned yet -- defaulting to one nobody owns put a wrong
  // canonical on every page and a wrong sitemap URL in robots.txt. When a domain is bought, set the
  // SITE_URL repo variable and the workflow flips SITE_BASE to '/' on its own; nothing here changes.
  site: process.env.SITE_URL || 'https://hantswilliams.github.io',
  base,
  output: 'static',
  trailingSlash: 'never',
  build: { format: 'file' },          // /pricing -> dist/pricing.html (clean URLs on any static host)
  // Exploration routes are local review artifacts, not search landing pages.
  integrations: [sitemap({ filter: page => !new URL(page).pathname.split('/').includes('explore') })],
  markdown: { rehypePlugins: [rehypeBasePath], shikiConfig: { theme: 'github-dark' } },
});
