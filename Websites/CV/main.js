/* ========= PROJECTS CANVAS ========= */
(() => {
  const world = document.getElementById('world');
  const scene = document.getElementById('scene');
  const intro = document.getElementById('intro');
  const minimap = document.getElementById('mmSurface');
  const detail = document.getElementById('detail');
  const detailContent = document.getElementById('detailContent');
  const detailClose = document.getElementById('detailClose');

  // ───── Project data ─────
  // Circular layout: intro at center, projects arranged clockwise around it
  const PROJECTS = [
    {
      id: 'intro',
      kind: 'intro',
      x: -260, y: -130, w: 520, h: 260,
      rot: 1.5,
      step: 0,
    },
    {
      id: 'streaks',
      kind: 'streaks',
      title: 'Streaks',
      eyebrow: 'PWA · Live',
      x: 530, y: -250, w: 340, h: 500,
      rot: -4,
      step: 2,
      status: 'Live',
      year: '2024',
      stack: 'PWA · Vanilla JS · IndexedDB',
      lede: 'A habit tracker that turns daily reminders into a game.',
      about: `Streaks is a PWA that helps you build habits that actually stick. Install it on your phone like a native app, set your daily goals, and let the automatic reset keep you honest.
      <br><br>Every completed day grows your streak. Every missed day resets it. That small tension is what makes habits stick — and what makes the app fun.`,
      features: [
        'Daily reminders that you can\'t ignore',
        'Auto-resets at midnight so your streak reflects the truth',
        'Stats to see exactly how consistent you\'ve been',
        'Works offline — installs as a home-screen app',
      ],
      stats: [
        ['Type', 'PWA'],
        ['Status', 'Live'],
        ['Stack', 'Vanilla'],
      ],
      link: 'https://thanfyllou.eu/streaks/',
    },
    {
      id: 'pure',
      kind: 'pure',
      title: '<em>Pure</em> Life',
      eyebrow: 'Adventures · Active',
      x: 160, y: 426, w: 380, h: 360,
      rot: 3,
      step: 3,
      lede: 'A VIP adventure group that creates experiences — not just trips.',
      about: `Pure Life is a travel collective for people who'd rather have a story to tell than another photo on a beach. We design trips that border on ridiculous — remote, raw, unforgettable.
      <br><br>Each adventure is hand-curated. Small groups. Real places. Experiences you couldn't book if you tried.`,
      features: [
        'Curated micro-groups of travelers',
        'Destinations you won\'t find on a listicle',
        'Full logistics handled end-to-end',
        'Memories over itineraries',
      ],
      stats: [
        ['Type', 'Experiences'],
        ['Group', 'Small'],
        ['Vibe', 'VIP'],
      ],
      link: 'https://thanfyllou.eu/travel2/',
    },
    {
      id: 'games',
      kind: 'games',
      title: 'Games',
      eyebrow: 'Mini web games · Playground',
      x: -510, y: 416, w: 320, h: 380,
      rot: -3,
      step: 4,
      lede: 'A small arcade of browser toys I\'ve built on weekends.',
      about: `A growing playground of tiny browser games — each one born from an itch to try a mechanic, a visual, or a weird idea. No installs, no accounts. Just click and play.
      <br><br>Come back now and then. New ones land here when inspiration strikes.`,
      features: [
        'Tiny web games playable in a single click',
        'Built for fun — each one is a weekend experiment',
        'New titles added whenever a new idea sticks',
      ],
      stats: [
        ['Type', 'Arcade'],
        ['Games', 'A few'],
        ['Install', 'Never'],
      ],
      link: 'https://thanfyllou.eu/games/',
    },
    {
      id: 'github',
      kind: 'github',
      title: 'Code Vault',
      eyebrow: 'GitHub · Open Source',
      x: -490, y: -776, w: 280, h: 340,
      rot: 5,
      step: 0.5,
      lede: 'Every line I\'ve ever written lives here — finished or not.',
      about: `From shipped products to 2am experiments — this is where all the code ends up. Browse the repos, fork what you like, or just trace how things got built.<br><br>Some projects are polished. Some are very much not. All of them taught me something.`,
      features: [
        'Source code for every project on this canvas',
        'Personal experiments and half-finished ideas',
        'Open to questions, forks, and pull requests',
      ],
      stats: [
        ['Platform', 'GitHub'],
        ['Profile', '@athtriantafyllou'],
        ['Mood', 'Open source'],
      ],
      link: 'https://github.com/athtriantafyllou',
    },
    {
      id: 'ai',
      kind: 'ai',
      title: 'Short Break.',
      eyebrow: 'Temporarily Paused · Back Soon',
      x: 200, y: -793, w: 300, h: 375,
      rot: -6,
      step: 1,
      lede: 'This was live — we\'re just refreshing a few things behind the scenes.',
      about: `Good projects deserve good foundations. This one was live and running well — we\'re just taking a moment to make it a little better before bringing it back.<br><br>In the meantime, take a look around the rest of this canvas. There\'s plenty more to explore.`,
      features: [
        'Was live — and will be again, very soon',
        'A quiet refresh, nothing dramatic',
        'Explore the rest of the canvas while you wait',
      ],
      stats: [
        ['Status', 'Paused'],
        ['ETA', 'Soon'],
        ['Was', 'Live'],
      ],
      link: null,
    },
    {
      id: 'weekend',
      kind: 'ghost',
      title: 'Loose Ends',
      subtitle: 'Experiments that didn\'t need a name.',
      x: -820, y: -130, w: 240, h: 260,
      rot: -3,
      shape: 'square',
      step: 5,
    },
  ];

  // ───── Card rendering ─────
  function render() {
    scene.innerHTML = '';
    PROJECTS.forEach(p => {
      const el = document.createElement('div');
      el.className = `card card--${p.kind}`;
      el.dataset.id = p.id;
      el.style.width = p.w + 'px';
      el.style.left = p.x + 'px';
      el.style.top = p.y + 'px';
      el.style.transform = `rotate(${p.rot}deg)`;

      if (p.kind === 'intro') {
        el.innerHTML = `
          <div class="tiny">Portfolio · since 2020</div>
          <h1>Little <em>experiments.</em><br/>Big ideas.</h1>
          <p>Hey, I'm Thanasis. This is a corner for all the things I've made, broken, and learned from over the years. Drag around — some of them are still wet paint.</p>
        `;
      } else if (p.kind === 'streaks') {
        el.innerHTML = `
          <div class="meta">
            <span class="label">${p.eyebrow}</span>
            <span class="label">${p.year}</span>
          </div>
          <div class="frame">
            <img src="assets/images/streaks.webp" alt="Streaks app screenshot"
                 style="width:100%;height:100%;object-fit:cover;border-radius:10px;display:block;">
          </div>
          <h3>${p.title}</h3>
          <p>${p.lede}</p>
        `;
      } else if (p.kind === 'pure') {
        el.innerHTML = `
          <div class="postcard-img">
            <img src="assets/images/purelife.webp" alt="Pure Life adventures"
                 style="width:100%;height:100%;object-fit:cover;display:block;">
            <div class="stamp">Pure · 01</div>
          </div>
          <div class="body">
            <span class="label">${p.eyebrow}</span>
            <h3 style="margin-top:8px;">${p.title}</h3>
            <p>${p.lede}</p>
          </div>
        `;
      } else if (p.kind === 'ai') {
        el.innerHTML = `
          <div class="tag-row">
            <span class="tag">● Paused</span>
            <span class="tag">Back soon</span>
          </div>
          <div class="orb"><div class="orb-inner"></div></div>
          <div class="bottom">
            <h3>Short Break.</h3>
            <p style="margin-top:8px; font-size:13px;">We'll be live again shortly.</p>
          </div>
        `;
      } else if (p.kind === 'games') {
        el.innerHTML = `
          <div class="games-screen">
            <div class="scan"></div>
            <div class="pixels">
              <span style="--c:var(--accent)"></span>
              <span style="--c:oklch(0.7 0.18 30)"></span>
              <span style="--c:oklch(0.8 0.15 200)"></span>
              <span style="--c:var(--accent)"></span>
              <span style="--c:oklch(0.75 0.18 330)"></span>
              <span style="--c:oklch(0.82 0.15 90)"></span>
              <span style="--c:var(--accent)"></span>
            </div>
            <div class="games-title">PLAY</div>
          </div>
          <div class="games-body">
            <span class="label">${p.eyebrow}</span>
            <h3 style="margin-top:6px;">${p.title}</h3>
            <p>${p.lede}</p>
          </div>
        `;
      } else if (p.kind === 'github') {
        el.innerHTML = `
          <div style="display:flex; justify-content:space-between; align-items:flex-start;">
            <span class="label" style="color:rgba(244,239,227,0.45);">${p.eyebrow}</span>
            <svg width="26" height="26" viewBox="0 0 24 24" fill="rgba(244,239,227,0.85)" style="flex-shrink:0;"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
          </div>
          <div style="margin-top:auto;">
            <h3 style="font-size:40px; color:var(--paper); line-height:0.9;">GitHub</h3>
            <p style="font-size:13px; color:rgba(244,239,227,0.55); margin-top:10px;">Code Vault — every project, every experiment.</p>
          </div>
        `;
      } else if (p.kind === 'ghost') {
        const shapeCls = p.shape === 'square' ? 'sq' : p.shape === 'triangle' ? 'tr' : '';
        el.style.height = p.h + 'px';
        el.innerHTML = `
          <div class="shape ${shapeCls}"></div>
          <div>
            <span class="label">Coming soon</span>
            <h3 style="margin-top:6px;">${p.title}</h3>
            ${p.subtitle ? `<p style="font-size:12px; margin-top:6px; color:var(--muted);">${p.subtitle}</p>` : ''}
          </div>
        `;
      }

      if (p.kind !== 'ghost') {
        el.addEventListener('click', (e) => {
          if (!isDragging && !justDragged) {
            openDetail(p);
          }
        });
      }

      scene.appendChild(el);
    });

    // floating decorative arrows / squiggles between items
    addDecos();
    renderMinimap();
  }

  function addDecos() {
    // ─── Curved journey path through projects ───
    const steps = PROJECTS.filter(p => typeof p.step === 'number').sort((a,b) => a.step - b.step);
    const anchors = steps.map(p => ({
      x: p.x + p.w / 2,
      y: p.y + (p.h || 260) / 2,
      id: p.id,
    }));

    // Compute SVG bounds
    const xs = anchors.map(a => a.x), ys = anchors.map(a => a.y);
    const pad = 200;
    const minX = Math.min(...xs) - pad, minY = Math.min(...ys) - pad;
    const maxX = Math.max(...xs) + pad, maxY = Math.max(...ys) + pad;
    const w = maxX - minX, h = maxY - minY;

    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'journey');
    svg.setAttribute('viewBox', `${minX} ${minY} ${w} ${h}`);
    svg.style.left = minX + 'px';
    svg.style.top = minY + 'px';
    svg.style.width = w + 'px';
    svg.style.height = h + 'px';

    // Build curved path segment-by-segment, with arrowheads between steps
    for (let i = 0; i < anchors.length - 1; i++) {
      const a = anchors[i], b = anchors[i + 1];
      const mx = (a.x + b.x) / 2;
      const my = (a.y + b.y) / 2;
      // alternating curve direction
      const curveDir = i % 2 === 0 ? 1 : -1;
      const cx = mx + curveDir * 120;
      const cy = my - 90;

      // dashed curve
      const pathEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      pathEl.setAttribute('d', `M ${a.x} ${a.y} Q ${cx} ${cy}, ${b.x} ${b.y}`);
      svg.appendChild(pathEl);

      // arrowhead near endpoint (stop short of card)
      const dx = b.x - cx, dy = b.y - cy;
      const ang = Math.atan2(dy, dx);
      // step back 90px from b toward control
      const backX = b.x - Math.cos(ang) * 110;
      const backY = b.y - Math.sin(ang) * 110;
      const head = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
      const size = 10;
      const p1 = `${backX + Math.cos(ang)*size},${backY + Math.sin(ang)*size}`;
      const p2 = `${backX + Math.cos(ang+2.6)*size},${backY + Math.sin(ang+2.6)*size}`;
      const p3 = `${backX + Math.cos(ang-2.6)*size},${backY + Math.sin(ang-2.6)*size}`;
      head.setAttribute('points', `${p1} ${p2} ${p3}`);
      head.setAttribute('class', 'arrowhead');
      svg.appendChild(head);
    }
    scene.prepend(svg);

    // ─── Floating labels along the path ───
    const labels = [
      { x: -560, y: -500, rot: 10, html: 'the code →' },
      { x: 80, y: -620, rot: -6, html: 'start here →' },
      { x: 500, y: -480, rot: 4, html: 'first build' },
      { x: 460, y: 200, rot: -4, html: 'then adventures' },
      { x: -120, y: 500, rot: 5, html: '… some fun' },
    ];
    labels.forEach(d => {
      const el = document.createElement('div');
      el.className = 'journey-label';
      el.style.left = d.x + 'px';
      el.style.top = d.y + 'px';
      el.style.transform = `rotate(${d.rot}deg)`;
      el.innerHTML = d.html;
      scene.appendChild(el);
    });
  }

  // ───── Pan + zoom ─────
  // Initial pan positions the intro card roughly center-screen
  let panX = 0, panY = 0, zoom = 1;
  let targetX = 0, targetY = 0, targetZoom = 1;
  let isDragging = false;
  let justDragged = false;
  let lastDragEnd = 0;
  let dragStart = { x: 0, y: 0, panX: 0, panY: 0 };
  let breathing = true;
  let motionLevel = 9;

  function updateTransform() {
    scene.style.transform = `translate(${panX}px, ${panY}px) scale(${zoom})`;
    updateMinimapView();
  }

  world.addEventListener('pointerdown', (e) => {
    if (e.target.closest('.card')) return;
    isDragging = true;
    world.classList.add('grabbing');
    dragStart = { x: e.clientX, y: e.clientY, panX, panY };
    world.setPointerCapture(e.pointerId);
  });

  world.addEventListener('pointermove', (e) => {
    if (!isDragging) return;
    targetX = dragStart.panX + (e.clientX - dragStart.x);
    targetY = dragStart.panY + (e.clientY - dragStart.y);
  });

  world.addEventListener('pointerup', (e) => {
    if (!isDragging) return;
    isDragging = false;
    justDragged = Math.abs(targetX - dragStart.panX) > 3 || Math.abs(targetY - dragStart.panY) > 3;
    lastDragEnd = Date.now();
    world.classList.remove('grabbing');
    setTimeout(() => justDragged = false, 50);
  });

  // Card drag-detection - if user started drag on a card background
  scene.addEventListener('pointerdown', (e) => {
    const card = e.target.closest('.card');
    if (!card) return;
    isDragging = true;
    world.classList.add('grabbing');
    dragStart = { x: e.clientX, y: e.clientY, panX, panY };
    // NOTE: no setPointerCapture here — it would redirect click events to world,
    // preventing card click listeners from firing on desktop.
  });

  world.addEventListener('wheel', (e) => {
    e.preventDefault();
    const rect = world.getBoundingClientRect();
    const cx = e.clientX - rect.left - rect.width / 2;
    const cy = e.clientY - rect.top - rect.height / 2;
    const delta = -e.deltaY * 0.0015;
    const newZoom = Math.max(0.35, Math.min(1.6, targetZoom * (1 + delta)));
    const zoomRatio = newZoom / targetZoom;
    targetX = cx - (cx - targetX) * zoomRatio;
    targetY = cy - (cy - targetY) * zoomRatio;
    targetZoom = newZoom;
  }, { passive: false });

  // Pinch-to-zoom on touch devices
  let lastPinchDist = null;
  world.addEventListener('touchstart', (e) => {
    if (e.touches.length === 2) lastPinchDist = null;
  }, { passive: true });
  world.addEventListener('touchmove', (e) => {
    if (e.touches.length !== 2) return;
    e.preventDefault();
    const dx = e.touches[0].clientX - e.touches[1].clientX;
    const dy = e.touches[0].clientY - e.touches[1].clientY;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (lastPinchDist !== null) {
      const ratio = dist / lastPinchDist;
      const rect = world.getBoundingClientRect();
      const cx = (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left - rect.width / 2;
      const cy = (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top - rect.height / 2;
      const newZoom = Math.max(0.35, Math.min(1.6, targetZoom * ratio));
      const zoomRatio = newZoom / targetZoom;
      targetX = cx - (cx - targetX) * zoomRatio;
      targetY = cy - (cy - targetY) * zoomRatio;
      targetZoom = newZoom;
    }
    lastPinchDist = dist;
  }, { passive: false });
  world.addEventListener('touchend', () => { lastPinchDist = null; }, { passive: true });

  // Zoom buttons
  document.getElementById('zoomIn').onclick = () => {
    targetZoom = Math.min(1.6, targetZoom * 1.2);
  };
  document.getElementById('zoomOut').onclick = () => {
    targetZoom = Math.max(0.35, targetZoom / 1.2);
  };
  document.getElementById('zoomReset').onclick = () => {
    targetX = 0; targetY = 0; targetZoom = 1;
  };

  // Keyboard pan
  window.addEventListener('keydown', (e) => {
    if (detail.classList.contains('open')) return;
    const step = 80;
    if (e.key === 'ArrowLeft') targetX += step;
    if (e.key === 'ArrowRight') targetX -= step;
    if (e.key === 'ArrowUp') targetY += step;
    if (e.key === 'ArrowDown') targetY -= step;
    if (e.key === 'Escape') closeDetail();
  });

  // ───── Breathing animation ─────
  let t0 = performance.now();
  function tick(now) {
    const dt = (now - t0) / 1000;

    // Smooth interpolate pan/zoom
    const k = 0.18;
    panX += (targetX - panX) * k;
    panY += (targetY - panY) * k;
    zoom += (targetZoom - zoom) * k;
    updateTransform();

    // Gentle "breathing" drift on cards — only when not dragging and motion > 0
    if (breathing && motionLevel > 0 && !isDragging) {
      const amp = motionLevel * 0.4; // max ~4px
      const rotAmp = motionLevel * 0.05; // max ~0.5deg
      document.querySelectorAll('.card').forEach((el, i) => {
        const p = PROJECTS[i];
        if (!p || p.kind === 'intro') return;
        const phase = i * 1.3;
        const dx = Math.sin(dt * 0.6 + phase) * amp;
        const dy = Math.cos(dt * 0.5 + phase * 0.7) * amp * 1.2;
        const dr = Math.sin(dt * 0.4 + phase) * rotAmp;
        el.style.transform = `translate(${dx}px, ${dy}px) rotate(${p.rot + dr}deg)`;
      });
    }

    requestAnimationFrame(tick);
  }

  // ───── Minimap ─────
  function renderMinimap() {
    minimap.innerHTML = '';
    const bounds = getBounds();
    PROJECTS.forEach(p => {
      const d = document.createElement('div');
      d.className = 'mm-dot';
      const nx = (p.x - bounds.minX) / bounds.w;
      const ny = (p.y - bounds.minY) / bounds.h;
      const nw = p.w / bounds.w;
      const nh = (p.h || 260) / bounds.h;
      d.style.left = (nx * 100) + '%';
      d.style.top = (ny * 100) + '%';
      d.style.width = Math.max(4, nw * 100) + '%';
      d.style.height = Math.max(4, nh * 100) + '%';
      if (p.kind === 'ghost') d.style.opacity = '0.2';
      if (p.kind === 'intro') d.style.background = 'var(--accent)';
      minimap.appendChild(d);
    });
    const view = document.createElement('div');
    view.className = 'mm-view';
    view.id = 'mmView';
    minimap.appendChild(view);
    updateMinimapView();
  }

  function getBounds() {
    const pad = 200;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    PROJECTS.forEach(p => {
      minX = Math.min(minX, p.x);
      minY = Math.min(minY, p.y);
      maxX = Math.max(maxX, p.x + p.w);
      maxY = Math.max(maxY, p.y + (p.h || 260));
    });
    return {
      minX: minX - pad,
      minY: minY - pad,
      w: (maxX - minX) + pad * 2,
      h: (maxY - minY) + pad * 2,
    };
  }

  function updateMinimapView() {
    const view = document.getElementById('mmView');
    if (!view) return;
    const bounds = getBounds();
    const vw = window.innerWidth / zoom;
    const vh = window.innerHeight / zoom;
    // scene origin is at center of screen; visible world rect in scene coords:
    const cx = -panX / zoom;
    const cy = -panY / zoom;
    const nx = (cx - vw/2 - bounds.minX) / bounds.w;
    const ny = (cy - vh/2 - bounds.minY) / bounds.h;
    const nw = vw / bounds.w;
    const nh = vh / bounds.h;
    view.style.left = Math.max(0, nx * 100) + '%';
    view.style.top = Math.max(0, ny * 100) + '%';
    view.style.width = Math.min(100, nw * 100) + '%';
    view.style.height = Math.min(100, nh * 100) + '%';
  }

  // ───── Detail overlay ─────
  function openDetail(p) {
    if (p.kind === 'intro') return;
    if (p.kind === 'ghost') {
      detailContent.innerHTML = `
        <div class="eyebrow"><span class="dot"></span>In the lab</div>
        <h2>${p.title}</h2>
        <p class="lede">This is a placeholder. An idea is forming — soon it'll have a name, a shape, and something to show for itself.</p>
        <p>Thanasis is always cooking on something. If you're here early, bookmark the page and come back — this card will have filled out with real work.</p>
        <div class="actions">
          <a class="btn-ghost" href="mailto:hello@thanasis.me">Nudge me about it →</a>
        </div>
      `;
    } else {
      const statsHTML = (p.stats || []).map(([k,v]) => `
        <div class="stat"><div class="k">${k}</div><div class="v">${v}</div></div>
      `).join('');
      const featuresHTML = (p.features || []).map(f => `<li>${f}</li>`).join('');
      detailContent.innerHTML = `
        <div class="eyebrow"><span class="dot"></span>${p.eyebrow}</div>
        <h2>${p.title}</h2>
        <p class="lede">${p.lede}</p>
        ${statsHTML ? `<div class="stat-grid">${statsHTML}</div>` : ''}
        <p>${p.about}</p>
        ${featuresHTML ? `<ul>${featuresHTML}</ul>` : ''}
        <div class="actions">
          ${p.link ? `<a class="btn-primary" href="${p.link}" target="_blank" rel="noopener">Visit project →</a>` : ''}
          <button class="btn-ghost" onclick="document.getElementById('detailClose').click()">Back to canvas</button>
        </div>
      `;
    }
    detail.classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  function closeDetail() {
    detail.classList.remove('open');
  }

  detailClose.addEventListener('click', closeDetail);
  detail.addEventListener('click', (e) => {
    if (e.target === detail) closeDetail();
  });

  // ───── Intro (click-to-enter) ─────
  function dismissIntro() {
    intro.classList.add('done');
    setTimeout(() => { intro.style.display = 'none'; }, 900);
  }
  intro.addEventListener('click', dismissIntro);
  window.addEventListener('keydown', (e) => {
    if (!intro.classList.contains('done') && (e.key === ' ' || e.key === 'Enter' || e.key === 'Escape')) {
      dismissIntro();
    }
  });

  // ───── Home button ─────
  function goHome() {
    if (intro.style.display !== 'none' && !intro.classList.contains('done')) {
      dismissIntro();
    } else {
      intro.style.display = 'flex';
      intro.classList.remove('done');
    }
    // reset pan to origin so intro card is centered-ish on screen
    targetX = 0; targetY = 0; targetZoom = 1;
  }
  document.getElementById('homeBtn').onclick = goHome;

  // ───── Resize ─────
  window.addEventListener('resize', updateMinimapView);

  // ───── Init ─────
  render();
  requestAnimationFrame(tick);
})();
