// Fallback page transition for browsers without cross-page View Transitions.
// Those browsers get the "no-vt" class from the small script in partials/layout.html.
// Browsers that support View Transitions never run this code path (see css/components/transitions.css).

export function initPageTransitions() {
  const root = document.documentElement;
  if (!root.classList.contains('no-vt')) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  document.addEventListener('click', (event) => {
    if (event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

    const link = event.target.closest('a[href]');
    if (!link || (link.target && link.target !== '_self') || link.hasAttribute('download')) return;

    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin) return;
    if (url.pathname === location.pathname && url.search === location.search) return; // same page / #anchor

    event.preventDefault();
    root.classList.add('is-leaving');
    setTimeout(() => {
      location.href = url.href;
    }, 240);
  });

  // Coming back with the browser's back button: undo the fade-out
  window.addEventListener('pageshow', (event) => {
    if (event.persisted) root.classList.remove('is-leaving');
  });
}
