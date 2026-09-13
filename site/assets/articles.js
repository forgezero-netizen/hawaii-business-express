(() => {
  const categories = [
    'Starting a Business',
    'Managing a Business',
    'Compliance',
    'Taxes',
    'Financing',
    'Marketing',
    'Business Strategy'
  ];

  const normalize = (value = '') => String(value).toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();
  const formatDate = (value) => {
    if (!value) return '';
    const date = new Date(`${value}T12:00:00`);
    return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(date);
  };

  const navToggle = document.querySelector('[data-nav-toggle]');
  const nav = document.querySelector('[data-nav]');
  if (navToggle && nav) {
    navToggle.addEventListener('click', () => {
      const expanded = navToggle.getAttribute('aria-expanded') === 'true';
      navToggle.setAttribute('aria-expanded', String(!expanded));
      nav.classList.toggle('is-open', !expanded);
    });
    nav.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => {
      nav.classList.remove('is-open');
      navToggle.setAttribute('aria-expanded', 'false');
    }));
  }

  document.querySelectorAll('[data-current-year]').forEach((node) => {
    node.textContent = String(new Date().getFullYear());
  });

  const resultsEl = document.querySelector('[data-article-results]');
  const emptyEl = document.querySelector('[data-empty-state]');
  const resultCountEl = document.querySelector('[data-result-count]');
  const searchForm = document.querySelector('[data-article-search]');
  const searchInput = document.querySelector('[data-article-search-input]');
  const filterButtons = [...document.querySelectorAll('[data-topic-filter]')];
  const topicList = document.querySelector('[data-topic-list]');
  const featuredEl = document.querySelector('[data-featured]');

  let articles = [];
  let activeTopic = 'All Topics';
  let query = '';

  const scoreArticle = (article, rawQuery) => {
    const q = normalize(rawQuery);
    if (!q) return 1;
    const terms = q.split(' ').filter(Boolean);
    const title = normalize(article.title);
    const keywords = normalize((article.keywords || []).join(' '));
    const category = normalize(article.category);
    const description = normalize(article.description);
    let score = 0;
    for (const term of terms) {
      if (title.includes(term)) score += title.startsWith(term) ? 120 : 100;
      if (keywords.includes(term)) score += 75;
      if (category.includes(term)) score += 50;
      if (description.includes(term)) score += 30;
    }
    return score;
  };

  const articleCard = (article) => {
    const card = document.createElement('article');
    card.className = 'article-card';
    const image = article.image ? `<img src="${article.image}" alt="">` : '';
    const readTime = article.readTime ? ` <span aria-hidden="true">•</span> ${article.readTime}` : '';
    card.innerHTML = `
      <div class="article-card-media">${image}</div>
      <div class="article-card-body">
        <p class="article-category">${article.category || 'Business Articles'}</p>
        <h3><a href="${article.url}">${article.title}</a></h3>
        <p class="article-description">${article.description || ''}</p>
        <div class="article-meta"><span>${formatDate(article.date)}</span>${readTime}</div>
      </div>`;
    return card;
  };

  const renderFeatured = () => {
    if (!featuredEl) return;
    const featured = articles.find((article) => article.featured) || articles[0];
    if (!featured) {
      featuredEl.innerHTML = `
        <div class="featured-placeholder">
          <p class="small">Featured Article</p>
          <p class="title">Featured articles will appear here as the library grows.</p>
        </div>`;
      return;
    }
    featuredEl.innerHTML = `
      <a href="${featured.url}" style="text-decoration:none">
        <div class="featured-placeholder"${featured.image ? ` style="background:linear-gradient(135deg,rgba(15,92,111,.78),rgba(20,127,134,.45)),url('${featured.image}') center/cover"` : ''}>
          <p class="small">${featured.category || 'Featured Article'}</p>
          <p class="title">${featured.title}</p>
        </div>
      </a>`;
  };

  const renderTopics = () => {
    if (!topicList) return;
    const counts = new Map(categories.map((category) => [category, 0]));
    articles.forEach((article) => {
      if (counts.has(article.category)) counts.set(article.category, counts.get(article.category) + 1);
    });
    topicList.innerHTML = '';
    categories.forEach((category) => {
      const li = document.createElement('li');
      const count = counts.get(category) || 0;
      li.innerHTML = `<button type="button" data-sidebar-topic="${category}"><span>${category}</span><span>${count || 'Soon'}</span></button>`;
      topicList.appendChild(li);
    });
    topicList.querySelectorAll('[data-sidebar-topic]').forEach((button) => {
      button.addEventListener('click', () => {
        activeTopic = button.dataset.sidebarTopic;
        filterButtons.forEach((pill) => pill.classList.toggle('is-active', pill.dataset.topicFilter === activeTopic));
        render();
        document.querySelector('.article-tools')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  };

  const render = () => {
    if (!resultsEl || !emptyEl) return;
    let filtered = articles.filter((article) => activeTopic === 'All Topics' || article.category === activeTopic);
    if (query.trim()) {
      filtered = filtered
        .map((article) => ({ article, score: scoreArticle(article, query) }))
        .filter((item) => item.score > 0)
        .sort((a, b) => b.score - a.score || String(b.article.date).localeCompare(String(a.article.date)))
        .map((item) => item.article);
    } else {
      filtered.sort((a, b) => String(b.date).localeCompare(String(a.date)));
    }

    resultsEl.innerHTML = '';
    filtered.forEach((article) => resultsEl.appendChild(articleCard(article)));
    const hasResults = filtered.length > 0;
    resultsEl.hidden = !hasResults;
    emptyEl.hidden = hasResults;

    if (resultCountEl) {
      if (!articles.length) resultCountEl.textContent = 'Articles will appear here as they are published.';
      else if (query.trim() || activeTopic !== 'All Topics') resultCountEl.textContent = `${filtered.length} article${filtered.length === 1 ? '' : 's'} found`;
      else resultCountEl.textContent = `${articles.length} article${articles.length === 1 ? '' : 's'}`;
    }

    const emptyTitle = emptyEl.querySelector('h3');
    const emptyText = emptyEl.querySelector('p');
    if (!articles.length) {
      if (emptyTitle) emptyTitle.textContent = 'Business articles are coming soon';
      if (emptyText) emptyText.textContent = 'This library is ready for publication. New Hawaiʻi business articles will appear here and will be searchable by title, keyword, and topic.';
    } else {
      if (emptyTitle) emptyTitle.textContent = 'No matching articles';
      if (emptyText) emptyText.textContent = 'Try a broader keyword, a different title phrase, or select All Topics.';
    }
  };

  filterButtons.forEach((button) => {
    button.addEventListener('click', () => {
      activeTopic = button.dataset.topicFilter;
      filterButtons.forEach((pill) => pill.classList.toggle('is-active', pill === button));
      render();
    });
  });

  searchForm?.addEventListener('submit', (event) => {
    event.preventDefault();
    query = searchInput?.value || '';
    render();
  });
  searchInput?.addEventListener('input', () => {
    query = searchInput.value;
    render();
  });

  fetch('../assets/articles-index.json?v=20260913-1', { cache: 'no-store' })
    .then((response) => {
      if (!response.ok) throw new Error(`Article index returned ${response.status}`);
      return response.json();
    })
    .then((data) => {
      articles = Array.isArray(data) ? data : [];
      articles.sort((a, b) => String(b.date).localeCompare(String(a.date)));
      renderFeatured();
      renderTopics();
      render();
    })
    .catch(() => {
      articles = [];
      renderFeatured();
      renderTopics();
      render();
    });
})();
