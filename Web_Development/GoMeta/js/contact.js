// Contact page: sends the form without a page reload.
// Without JavaScript the form still works: it posts normally and PHP redirects back to /contact/?sent=1

const form = document.querySelector('[data-contact-form]');

if (form) {
  const status = form.querySelector('[data-form-status]');
  const button = form.querySelector('button[type="submit"]');
  const fallback = `Something went wrong. Please email us at ${form.dataset.email}.`;

  const setStatus = (state, text) => {
    status.dataset.state = state;
    status.textContent = text;
  };

  // Result of a normal (no-JavaScript) submit
  const params = new URLSearchParams(location.search);
  if (params.has('sent')) setStatus('success', 'Thank you! Your message is on its way. We reply within a working day.');
  if (params.has('error')) setStatus('error', fallback);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;

    button.disabled = true;
    setStatus('pending', 'Sending…');

    let message = fallback;
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: { 'X-Requested-With': 'fetch', Accept: 'application/json' },
      });
      const data = await response.json();
      message = data.message || fallback;
      if (!response.ok || !data.ok) throw new Error(message);

      form.reset();
      setStatus('success', message);
    } catch {
      setStatus('error', message);
    } finally {
      button.disabled = false;
    }
  });
}
