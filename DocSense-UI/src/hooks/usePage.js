import { useEffect } from 'react';

/**
 * Per-page document settings. `page` selects the page-scoped CSS (html[data-page="..."]),
 * and optional `bodyClass` is added to <body> while the page is mounted.
 */
export function usePage({ page, title, themeColor, bodyClass }) {
  useEffect(() => {
    const root = document.documentElement;
    const meta = document.querySelector('meta[name="theme-color"]');
    const prevTitle = document.title;
    const prevTheme = meta ? meta.getAttribute('content') : null;

    root.dataset.page = page;
    if (title) document.title = title;
    if (meta && themeColor) meta.setAttribute('content', themeColor);
    const classes = bodyClass ? bodyClass.split(' ') : [];
    classes.forEach((c) => document.body.classList.add(c));

    return () => {
      delete root.dataset.page;
      document.title = prevTitle;
      if (meta && prevTheme) meta.setAttribute('content', prevTheme);
      classes.forEach((c) => document.body.classList.remove(c));
    };
  }, [page, title, themeColor, bodyClass]);
}
