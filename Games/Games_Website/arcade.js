// Marquee content (duplicated for seamless loop)
const items = [
  "★ INSERT COIN ★",
  "WAVELENGTH — 2P MIND READ",
  "MEGA TIC-TAC-TOE — BOARDS WITHIN BOARDS",
  "NEW CABINET COMING SOON",
  "HIGH SCORE: 013370 — A.T.",
  "FREE PLAY · ALL DAY · ALL NIGHT",
  "GRAB A FRIEND. SHARE THE KEYBOARD.",
];
const track = document.getElementById('marquee');
const html = items.map(t => `<span>${t}<span class="dot">●</span></span>`).join('');
track.innerHTML = html + html; // duplicate for seamless loop

// Build mega tic-tac-toe mini grid for the screen preview
const ttGrid = document.getElementById('ttGrid');
const moves = [
  "..X......",
  "....O....",
  "X........",
  ".....X...",
  "O........",
  "...X.....",
  "........O",
  "..X......",
  ".....O...",
];
for (let c = 0; c < 9; c++) {
  const cell = document.createElement('div');
  cell.className = 'tt-cell';
  const seq = moves[c];
  for (let m = 0; m < 9; m++) {
    const mini = document.createElement('div');
    mini.className = 'tt-mini';
    const ch = seq[m];
    if (ch === 'X') { mini.classList.add('x'); mini.textContent = 'X'; }
    else if (ch === 'O') { mini.classList.add('o'); mini.textContent = 'O'; }
    cell.appendChild(mini);
  }
  ttGrid.appendChild(cell);
}

// Live clock in HUD
function tick() {
  const d = new Date();
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const el = document.getElementById('clock');
  if (el) el.textContent = `${hh}:${mm}`;
}
tick();
setInterval(tick, 1000 * 30);

// About panel open / close
const about = document.getElementById('about');
const scrim = document.getElementById('scrim');

function openAbout() {
  about.classList.add('open');
  scrim.classList.add('show');
  about.setAttribute('aria-hidden', 'false');
}
function closeAbout() {
  about.classList.remove('open');
  scrim.classList.remove('show');
  about.setAttribute('aria-hidden', 'true');
}

document.getElementById('aboutOpen').addEventListener('click', openAbout);
document.getElementById('aboutClose').addEventListener('click', closeAbout);
scrim.addEventListener('click', closeAbout);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeAbout(); });

// Subtle random screen flicker on cabinets
const screens = document.querySelectorAll('.screen');
setInterval(() => {
  const s = screens[Math.floor(Math.random() * screens.length)];
  if (!s) return;
  s.animate(
    [{ filter: 'brightness(1)' }, { filter: 'brightness(1.4) contrast(1.1)' }, { filter: 'brightness(1)' }],
    { duration: 140 }
  );
}, 2200);
