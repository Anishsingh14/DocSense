/** Decorative corner waves shared by the Get Started, Chat and Terms pages. `p` is the page's CSS prefix (gs, ch, tc). */
export default function Waves({ p }) {
  return (
    <div aria-hidden="true" className={`${p}-bg`}>
      <svg className={`${p}-wave ${p}-wave--tl`} viewBox="0 0 420 300" preserveAspectRatio="xMinYMin slice">
        <path className={`${p}-wave-soft`} d="M0 0H330C300 40 250 70 210 110C170 150 120 210 40 215C20 216 8 214 0 212Z" />
        <path className={`${p}-wave-main`} d="M0 0H300C265 28 235 55 195 85C150 118 90 150 40 140C20 136 8 128 0 120Z" />
        <path className={`${p}-stroke`} d="M300 20C250 70 225 110 160 150C110 180 60 205 0 232" />
      </svg>
      <svg className={`${p}-wave ${p}-wave--br`} viewBox="0 0 420 300" preserveAspectRatio="xMaxYMax slice">
        <path className={`${p}-stroke`} d="M420 70C340 80 300 130 260 180C225 222 160 255 90 300" />
        <path className={`${p}-wave-soft`} d="M420 120C360 130 330 170 300 215C275 250 230 280 190 300H420Z" />
        <path className={`${p}-wave-main`} d="M420 175C375 178 345 205 322 240C305 265 285 285 262 300H420Z" />
      </svg>
    </div>
  );
}
