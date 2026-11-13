import { useEffect } from 'react';

/**
 * Plays the hero video exactly once (muted, no loop). If the browser blocks autoplay it starts on
 * the first interaction. A refresh can interrupt the first play() call, so it retries when data is
 * ready, the tab becomes visible, or the page is restored. If the file can't load, the layer gets
 * `is-fallback` and shows its solid navy background instead of a broken video.
 */
export function useHeroVideo(layerRef, videoRef) {
  useEffect(() => {
    const layer = layerRef.current;
    const video = videoRef.current;
    if (!layer || !video) return undefined;

    let started = false;
    const fallback = () => layer.classList.add('is-fallback');
    const interactionEvents = ['pointerdown', 'keydown'];

    const cleanupInteraction = () => {
      interactionEvents.forEach((name) => document.removeEventListener(name, onInteract, true));
    };
    function onInteract() {
      if (started || video.ended) { cleanupInteraction(); return; }
      video.muted = true;
      video.play().then(() => { started = true; cleanupInteraction(); }).catch(() => {});
    }
    const armInteractionStart = () => {
      if (started) return;
      interactionEvents.forEach((name) => document.addEventListener(name, onInteract, { capture: true, passive: true }));
    };

    const onPlaying = () => { started = true; cleanupInteraction(); };
    const kick = () => {
      if (started || video.ended || !video.paused) return;
      video.muted = true;
      const p = video.play();
      if (p && typeof p.catch === 'function') p.catch(() => {});
    };
    const onVisible = () => { if (!document.hidden) kick(); };

    video.muted = true; // required for programmatic autoplay in most browsers
    video.addEventListener('error', fallback, { once: true });
    const source = video.querySelector('source');
    if (source) source.addEventListener('error', fallback, { once: true });
    video.addEventListener('playing', onPlaying, { once: true });
    ['loadeddata', 'canplay'].forEach((name) => video.addEventListener(name, kick));
    window.addEventListener('pageshow', kick);
    document.addEventListener('visibilitychange', onVisible);

    const played = video.play();
    if (played && typeof played.then === 'function') {
      played.then(() => { started = true; cleanupInteraction(); }).catch((error) => {
        if (!error || error.name === 'AbortError' || error.name === 'NotAllowedError') {
          armInteractionStart(); // autoplay policy: start on the first interaction
          return;
        }
        fallback();
      });
    } else {
      started = true;
    }

    return () => {
      cleanupInteraction();
      video.removeEventListener('error', fallback);
      video.removeEventListener('playing', onPlaying);
      ['loadeddata', 'canplay'].forEach((name) => video.removeEventListener(name, kick));
      window.removeEventListener('pageshow', kick);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [layerRef, videoRef]);
}
