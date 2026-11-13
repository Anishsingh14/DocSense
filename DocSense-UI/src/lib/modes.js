/**
 * The three Q&A modes and the two answer styles. The labels here are the single source of truth for both the
 * Get Started and Chat pages. `api` is the backend's name for the mode (POST /query), `defaultStyle` is the
 * answer style a mode starts with, and `styleLocked` keeps a mode on its default style.
 */
export const MODES = [
  { key: 'general', label: 'General Q&A', multiFile: false, api: 'single_doc', defaultStyle: 'summary' },
  { key: 'multi', label: 'Multi-Doc', multiFile: true, api: 'multi_doc', defaultStyle: 'summary' },
  // The legal prompt always asks for the exact clause text, so a summary request would contradict it.
  { key: 'legal', label: 'Legal Precision', multiFile: true, api: 'legal', defaultStyle: 'full', styleLocked: true },
];

/** `key` is the backend's answer_style value. */
export const ANSWER_STYLES = [
  { key: 'summary', label: 'Summary', hint: 'A short answer in plain words, with citations.' },
  { key: 'full', label: 'Exact quotes', hint: 'The relevant text quoted word for word, with citations.' },
];

export const DEFAULT_MODE = 'general';
export const modeByKey = (key) => MODES.find((m) => m.key === key);
export const isMultiFile = (key) => !!(modeByKey(key) && modeByKey(key).multiFile);
export const styleByKey = (key) => ANSWER_STYLES.find((s) => s.key === key);

/** The style to use: a locked mode's own style, else the requested style if it exists, else the mode's default. */
export function resolveStyle(modeKey, requested) {
  const m = modeByKey(modeKey) || modeByKey(DEFAULT_MODE);
  if (m.styleLocked) return m.defaultStyle;
  return styleByKey(requested) ? requested : m.defaultStyle;
}
