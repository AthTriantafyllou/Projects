// --- Get buttons ---
const localBtn = document.getElementById('localBtn');
const multiplayerBtn = document.getElementById('multiplayerBtn');
const howToPlayBtn = document.getElementById('howToPlayBtn');
const exitBtn = document.getElementById('exitBtn');

// --- Popup elements ---
const popup = document.getElementById('popup');
const closePopup = document.querySelector('.popup .close');

// --- Button actions ---
localBtn.addEventListener('click', () => {
  window.location.href = '../games/mega-tictactoe-local.html';
});

multiplayerBtn.addEventListener('click', () => {
  popup.classList.remove('hidden');
});

closePopup.addEventListener('click', () => {
  popup.classList.add('hidden');
});

howToPlayBtn.addEventListener('click', () => {
  window.location.href = '../pages/tictactoe-how-to.html';
});

exitBtn.addEventListener('click', () => {
  window.location.href = '../index.html';
});
