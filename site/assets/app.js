(() => {
  const DCCA_SEARCH_URL = 'https://hbe.dcca.hawaii.gov/search-and-buy';

  // Use the tightly cropped transparent logo in the header. CSS controls
  // sizing so the logo always keeps its native aspect ratio.
  const headerLogo = document.querySelector('.brand img');
  if (headerLogo) {
    headerLogo.src = 'assets/logo-transparent-cropped.png?v=20260913-2';
    headerLogo.removeAttribute('width');
    headerLogo.removeAttribute('height');
  }

  document.querySelectorAll('[data-dcca-search]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const input = form.querySelector('input[name="searchTerm"]');
      const term = input ? input.value.trim() : '';
      if (!term) {
        input?.focus();
        return;
      }

      const url = new URL(DCCA_SEARCH_URL);
      url.searchParams.set('searchTerm', term);

      if (typeof window.gtag === 'function') {
        window.gtag('event', 'business_search_submit');
      }

      const newWindow = window.open(url.toString(), '_blank', 'noopener,noreferrer');
      if (newWindow) newWindow.opener = null;
    });
  });

  const navToggle = document.querySelector('[data-nav-toggle]');
  const nav = document.querySelector('[data-nav]');
  if (navToggle && nav) {
    navToggle.addEventListener('click', () => {
      const expanded = navToggle.getAttribute('aria-expanded') === 'true';
      navToggle.setAttribute('aria-expanded', String(!expanded));
      nav.classList.toggle('is-open', !expanded);
    });

    nav.querySelectorAll('a').forEach((link) => {
      link.addEventListener('click', () => {
        nav.classList.remove('is-open');
        navToggle.setAttribute('aria-expanded', 'false');
      });
    });
  }

  document.querySelectorAll('[data-current-year]').forEach((node) => {
    node.textContent = String(new Date().getFullYear());
  });
})();
