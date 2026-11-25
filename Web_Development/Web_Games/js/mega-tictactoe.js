// --- Initialize elements ---
const megaGrid = document.querySelector('.mega-grid');
const turnIndicator = document.getElementById('turnIndicator');
const resetBtn = document.getElementById('resetBtn');
const exitBtn = document.getElementById('exitBtn');

const scoreX = document.getElementById('scoreX');
const scoreO = document.getElementById('scoreO');
const scoreTie = document.getElementById('scoreTie');

// Player X starts first
let currentPlayer = 'X';

// Game state
let boards = []; // Holds the state of each small 3x3 board
let boardWinners = Array(9).fill(null); // Records who won each sub-board
let activeBoard = null; // The board where the next move must be played
let totalScores = { X: 0, O: 0, Tie: 0 };

// --- Initialize game ---
function initGame() {
  // Reset state variables
  boards = [];
  boardWinners = Array(9).fill(null);
  activeBoard = null;
  currentPlayer = 'X';
  turnIndicator.textContent = `Turn: Player 1 (${currentPlayer})`;

  // Remove any previous sub-boards (so reset works properly)
  document.querySelectorAll('.sub-board').forEach(sb => sb.remove());

  // Create 9 sub-boards inside each of the 9 main .board divs
  for (let b = 0; b < 9; b++) {
    const board = document.createElement('div');
    board.classList.add('sub-board');
    board.dataset.index = b;

    // Create 9 cells inside this sub-board
    const cells = [];
    for (let c = 0; c < 9; c++) {
      const cell = document.createElement('div');
      cell.classList.add('cell');
      cell.dataset.cell = c;
      cell.addEventListener('click', () => handleCellClick(b, c));
      board.appendChild(cell);
      cells.push('');
    }

    boards.push(cells);
    megaGrid.children[b].appendChild(board);
  }

  updateBoardHighlights();
}


// --- Handle cell click ---
function handleCellClick(boardIndex, cellIndex) {
  // Check if move is allowed
  if (activeBoard !== null && activeBoard !== boardIndex) return;
  if (boardWinners[boardIndex]) return;
  if (boards[boardIndex][cellIndex] !== '') return;

  boards[boardIndex][cellIndex] = currentPlayer;
  const board = megaGrid.children[boardIndex].querySelector('.sub-board');
  const cell = board.children[cellIndex];
  cell.textContent = currentPlayer;

  // Check win or tie for the small board
  const winner = checkSmallBoard(boards[boardIndex]);
  if (winner) {
    boardWinners[boardIndex] = winner;
    markBoardWinner(board, winner);
  } else if (boards[boardIndex].every(v => v !== '')) {
    boardWinners[boardIndex] = 'Tie';
    board.classList.add('tied');
  }

 // --- Check if someone won the entire game ---
const megaWinner = checkMegaBoard();
if (megaWinner) {
  totalScores[megaWinner]++;
  updateScores();
  showWinnerPopup(`Player ${megaWinner} wins the game!`);
  return;
} else if (boardWinners.every(b => b !== null)) {
  totalScores.Tie++;
  updateScores();
  showWinnerPopup(`It's a tie!`);
  return;
}

  // Set next active board
  activeBoard = boardWinners[cellIndex] ? null : cellIndex;

  // Switch player
  currentPlayer = currentPlayer === 'X' ? 'O' : 'X';
  turnIndicator.textContent = `Turn: Player ${currentPlayer === 'X' ? '1' : '2'} (${currentPlayer})`;

  updateBoardHighlights();
}

// --- Check for a win in a small 3x3 board ---
function checkSmallBoard(board) {
  const wins = [
    [0, 1, 2], [3, 4, 5], [6, 7, 8],
    [0, 3, 6], [1, 4, 7], [2, 5, 8],
    [0, 4, 8], [2, 4, 6],
  ];
  for (const [a, b, c] of wins) {
    if (board[a] && board[a] === board[b] && board[a] === board[c]) return board[a];
  }
  return null;
}

// --- Check for a win in the overall 3x3 mega board ---
function checkMegaBoard() {
  return checkSmallBoard(boardWinners);
}

// --- Visually mark a board as won ---
function markBoardWinner(board, winner) {
  board.classList.add('won');
  const overlay = document.createElement('div');
  overlay.classList.add('winner-overlay');
  overlay.textContent = winner;
  board.appendChild(overlay);
}

// --- Highlight the active board (red outline) ---
function updateBoardHighlights() {
  for (let i = 0; i < 9; i++) {
    const boardEl = megaGrid.children[i].querySelector('.sub-board');
    boardEl.classList.remove('active');
    if (!boardWinners[i]) boardEl.classList.remove('disabled');
    if (boardWinners[i]) boardEl.classList.add('disabled');
  }

  if (activeBoard === null) return;

  const activeEl = megaGrid.children[activeBoard].querySelector('.sub-board');
  activeEl.classList.add('active');
}

// --- Update the scoreboard ---
function updateScores() {
  scoreX.textContent = totalScores.X;
  scoreO.textContent = totalScores.O;
  scoreTie.textContent = totalScores.Tie;
}

// --- Reset and Exit buttons ---
resetBtn.addEventListener('click', initGame);
exitBtn.addEventListener('click', () => {
  window.location.href = '../games/game2.html';
});



// --- Show popup message instead of alert ---
function showWinnerPopup(message) {
  const popup = document.getElementById('winnerPopup');
  const msg = document.getElementById('winnerMessage');
  const closeBtn = document.getElementById('closeWinnerPopup');
  const okBtn = document.getElementById('winnerOkBtn');

  msg.textContent = message;
  popup.classList.remove('hidden');

  const closePopup = () => {
    popup.classList.add('hidden');
    initGame();
  };

  closeBtn.onclick = closePopup;
  okBtn.onclick = closePopup;
}



// --- Start the game ---
initGame();
