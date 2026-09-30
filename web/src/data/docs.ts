// The docs section's shape: sidebar order, the version stamp on every page, and where
// "edit this page" points. The version is read from the core at build time so the docs
// can never claim a version the package does not have.
import { readFileSync } from 'node:fs';
import { getCollection } from 'astro:content';

export const SECTIONS = ['Start', 'Guide', 'Reference', 'Develop'] as const;
export type Section = (typeof SECTIONS)[number];

export const REPO = 'https://github.com/hantswilliams/querysolo';
export const EDIT_BASE = `${REPO}/edit/main/web/src/content/docs`;

export function coreVersion(): string {
  try {
    const src = readFileSync(new URL('../../../core/querysolo/__init__.py', import.meta.url), 'utf8');
    return src.match(/__version__\s*=\s*"([^"]+)"/)?.[1] ?? 'unknown';
  } catch {
    return 'unknown';
  }
}

export type DocLink = { id: string; href: string; title: string; description: string; section: Section; order: number };

export async function docLinks(): Promise<DocLink[]> {
  const entries = await getCollection('docs');
  return entries
    .map(e => ({
      id: e.id,
      href: e.id === 'index' ? '/docs' : `/docs/${e.id}`,
      title: e.data.title,
      description: e.data.description,
      section: e.data.section,
      order: e.data.order,
    }))
    .sort((a, b) => SECTIONS.indexOf(a.section) - SECTIONS.indexOf(b.section) || a.order - b.order);
}
