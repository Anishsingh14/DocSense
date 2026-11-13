import { useEffect, useState } from 'react';

/**
 * Scroll state for the home page header.
 *  - scrolled:  page has moved past the very top
 *  - navHidden: the visitor is still in the first half of the hero
 *  - activeId:  id of the section at the reading position (scroll spy)
 */
export function useHomeScroll(sectionIds) {
  const [state, setState] = useState({ scrolled: false, navHidden: true, activeId: sectionIds[0] });
  const key = sectionIds.join('|');

  useEffect(() => {
    let queued = false;

    const compute = () => {
      const y = window.scrollY;
      const hero = document.getElementById('home');
      const threshold = hero ? hero.offsetHeight / 2 : 0;

      const targets = sectionIds
        .map((id) => ({ id, el: document.getElementById(id) }))
        .filter((t) => t.el);
      let activeId = targets.length ? targets[0].id : sectionIds[0];
      if (targets.length) {
        const readingLine = y + 140;
        let closest = -Infinity;
        targets.forEach(({ id, el }) => {
          const top = el.getBoundingClientRect().top + y;
          if (top <= readingLine && top > closest) {
            closest = top;
            activeId = id;
          }
        });
        if (window.innerHeight + y >= document.documentElement.scrollHeight - 4) {
          activeId = targets[targets.length - 1].id;
        }
      }

      setState((prev) => {
        const next = { scrolled: y > 8, navHidden: y < threshold, activeId };
        return prev.scrolled === next.scrolled && prev.navHidden === next.navHidden && prev.activeId === next.activeId
          ? prev
          : next;
      });
    };

    const onScroll = () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => {
        compute();
        queued = false;
      });
    };

    compute();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', compute);
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', compute);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return state;
}
