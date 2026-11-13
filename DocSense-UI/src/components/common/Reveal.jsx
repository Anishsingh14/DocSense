import { useEffect, useRef, useState } from 'react';

/**
 * Fades/slides its content in the first time it scrolls into view.
 * Does nothing when the visitor prefers reduced motion or IntersectionObserver is missing.
 */
export default function Reveal({ as: Tag = 'div', className = '', children, ...rest }) {
  const ref = useRef(null);
  const [armed, setArmed] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!node || reduce || !('IntersectionObserver' in window)) return undefined;

    setArmed(true);
    const observer = new IntersectionObserver((entries, instance) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        setVisible(true);
        instance.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const cls = [className, armed && 'reveal-init', visible && 'is-visible'].filter(Boolean).join(' ');
  return (
    <Tag ref={ref} className={cls} {...rest}>
      {children}
    </Tag>
  );
}
