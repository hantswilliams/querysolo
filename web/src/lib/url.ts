// Prefix a root-relative path with the site's base path, so the same source
// works at "/" (custom domain, Cloudflare Pages) and at "/querysolo/" (GitHub
// Pages project site). Use for every internal href: url('/pricing#compare').
const base = import.meta.env.BASE_URL.replace(/\/$/, '');
export const url = (path: string) => (path.startsWith('/') ? base + path : path);
export const isCurrent = (path: string, pathname: string) => {
  const p = pathname.startsWith(base) ? pathname.slice(base.length) : pathname;
  return (p.replace(/\.html$/, '').replace(/\/$/, '') || '/') === path;
};
