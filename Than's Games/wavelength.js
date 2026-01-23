// ---------------- BASIC UI SETUP ----------------

const blocker = document.getElementById('blocker');   // blue “curtain” overlay
const zone = document.getElementById('zone');         // 5-bar scoring zone
const guessRange = document.getElementById('guessRange');
const guessValue = document.getElementById('guessValue');

const btnToggle  = document.getElementById('btnToggle');
const btnRandom  = document.getElementById('btnRandom');
const btnNewCat  = document.getElementById('btnNewCat');
const btnSubmit  = document.getElementById('btnSubmit');
const btnReset   = document.getElementById('btnReset');

// --- Display the slider value in real time ---
/*
guessValue.textContent = guessRange.value;
guessRange.addEventListener('input', () => {
  guessValue.textContent = guessRange.value;
});*/

// --- SHOW/HIDE: toggle the blue blocker visibility ---
let isHidden = true; // starts with the zone hidden
applyBlocker();

btnToggle.addEventListener('click', () => {
  isHidden = !isHidden;
  applyBlocker();
});

function applyBlocker() {
  // If hidden, the blocker fully covers the zone (the guesser cannot see)
  blocker.style.opacity = isHidden ? '1' : '0';
  // Optional: disable clicks when covered
  blocker.style.pointerEvents = isHidden ? 'auto' : 'none';
}

// --- RANDOM GOAL ---
const zoneBars = document.getElementById('zoneBars');
// Move the 5 bars within the white container
btnRandom.addEventListener('click', () => {
  // Determine how far the bars can move (relative to the container width)
  const container = document.querySelector('.zone-bg');
  const containerWidth = container.offsetWidth;

  // The 5 bars together are about 250px wide; leave some margin
  const maxShift = (containerWidth - 250) / 2;
  const randomOffset = Math.floor(Math.random() * (maxShift * 2)) - maxShift;

  zoneBars.style.transform = `translateX(${randomOffset}px)`;
});


// --- NEW CATEGORY ---
// Keep track of which category we’re currently on
let currentCategoryIndex = 0;

// --- NEW CATEGORY ---
btnNewCat.addEventListener('click', () => {
  // Pick the next category (and loop around if at the end)
  const chosenCategory = categories[currentCategoryIndex];

  // Update labels
  document.getElementById('catLeft').textContent = chosenCategory[0];
  document.getElementById('catRight').textContent = chosenCategory[1];

  // Move to next index (loop if needed)
  currentCategoryIndex = (currentCategoryIndex + 1) % categories.length;

  // Hide zone automatically
  isHidden = true;
  applyBlocker();
});



// --- SUBMIT: calculate score and animate it ---
btnSubmit.addEventListener('click', () => {
  // Reveal the zone so players can see where the target was
  isHidden = false;
  applyBlocker();

  const container = document.querySelector('.zone-bg');
  const containerWidth = container.offsetWidth;
  const bars = document.querySelectorAll('.zone-bars .bar');

  // Slider (guess) position in pixels
  const guessPercent = parseFloat(guessRange.value) / 100;
  const guessPixel = guessPercent * containerWidth;

  // Get how far the colored zone is shifted
  const transform = getComputedStyle(zoneBars).transform;
  let offsetX = 0;
  if (transform !== "none") {
    const matrixValues = transform.match(/matrix.*\((.+)\)/)[1].split(", ");
    offsetX = parseFloat(matrixValues[4]);
  }

  // Calculate center of red "4" bar
  const zoneWidth = zoneBars.offsetWidth;
  const zoneLeft = (containerWidth / 2) - (zoneWidth / 2) + offsetX;
  const barWidth = bars[0].offsetWidth + 4;
  const zoneCenter = zoneLeft + barWidth * 2 + barWidth / 2;

  const distance = Math.abs(guessPixel - zoneCenter);

  // Determine score based on distance
  let score = 0;
  if (distance <= barWidth / 2) score = 4;
  else if (distance <= barWidth * 1.5) score = 3;
  else if (distance <= barWidth * 2.5) score = 2;
  else score = 0;

  // Update score visually
  const scoreDisplay = document.querySelector('.score');
  const currentScore = parseInt(scoreDisplay.textContent) || 0;
  const newScore = currentScore + score;
  scoreDisplay.textContent = newScore;

  // Trigger animation
  scoreDisplay.classList.add('score-animate');
  setTimeout(() => {
    scoreDisplay.classList.remove('score-animate');
  }, 600); // duration must match CSS animation time
});




// --- RESET: reset the basic elements ---
btnReset.addEventListener('click', () => {
  guessRange.value = 50;
  isHidden = true;
  applyBlocker();
  document.querySelector('.score').textContent = '0';
});




// ---------------- DATA ----------------
const categories = [
  ["Not harmful", "Harmful"],
  ["Cold", "Hot"],
  ["Cheap", "Expensive"],
  ["Take in a fight", "Can't take in a fight"],
  ["Bad movie snack", "Good movie snack"],
  ["Bad to sit on", "Good to sit on"],
  ["Bad nickname", "Good nickname"],
  ["Not huggable", "Huggable"],
  ["Waste of Time", "Good use of Time"],
  ["Game", "Sport"],
  ["Wierd thing to Own", "Normal thing to own"],
  ["Cat Name", "Dog Name"],
  ["Smells good", "Smells bad"],
  ["Messy Food", "Clean Food"],
  ["Soft", "Hard"],
  ["Happened Suddenly", "Happened Slowly"],
  ["Useless", "Useful"],
  ["Unhealthy", "Healthy"],
  ["Safe", "Dangerous"],
  ["Unpopular", "Popular"],
  ["Unlucky", "Lucky"],
  ["Underrated", "Overrated"]
];

