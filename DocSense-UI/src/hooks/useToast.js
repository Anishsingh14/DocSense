import { useCallback, useEffect, useRef, useState } from 'react';

/** Small transient notification. `show(message, isError)` displays it for `ms` milliseconds. */
export function useToast(ms = 3000) {
  const [toast, setToast] = useState({ message: '', isError: false, visible: false });
  const timer = useRef(0);

  const show = useCallback((message, isError = false) => {
    setToast({ message, isError, visible: true });
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setToast((t) => ({ ...t, visible: false })), ms);
  }, [ms]);

  useEffect(() => () => clearTimeout(timer.current), []);
  return [toast, show];
}
