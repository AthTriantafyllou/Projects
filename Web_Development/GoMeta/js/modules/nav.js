// Mobile menu toggle and "current page" highlight in the header.

export function initNav() {
  const toggle = document.querySelector('.nav-toggle');
  const nav = document.getElementById('site-nav');
  if (!toggle || !nav) return;

  const setOpen = (open) => {
    nav.dataset.open = String(open);
    toggle.setAttribute('aria-expanded', String(open));
  };

  toggle.addEventListener('click', () => setOpen(nav.dataset.open !== 'true'));
  nav.addEventListener('click', (event) => {
    if (event.target.closest('a')) setOpen(false);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') setOpen(false);
  });

  // Mark the link for the page we are on, e.g. /web/ or /work/ (works in a subfolder too)
  const path = location.pathname.replace(/index\.html$/, '');
  nav.querySelectorAll('a[href]').forEach((link) => {
    if (path.startsWith(link.pathname)) link.setAttribute('aria-current', 'page');
  });
}
