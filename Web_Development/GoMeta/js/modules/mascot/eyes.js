// The mascot's pupils follow the pointer (or the element you are typing in).
// Pupil position is written to the CSS variables --lx / --ly on the SVG (see css/components/mascot.css).

const MAX_OFFSET = 1.8; // how far a pupil may move, in SVG units
const EYE_CENTER = { x: 22.5 / 60, y: 29 / 72 }; // between the eyes, as a share of the SVG box

export function createEyes(svg, { enabled = true } = {}) {
  let target = { x: innerWidth / 2, y: innerHeight * 0.7 }; // looks slightly down until the pointer moves
  let frame = 0;

  function update() {
    frame = 0;
    const box = svg.getBoundingClientRect();
    const dx = target.x - (box.left + box.width * EYE_CENTER.x);
    const dy = target.y - (box.top + box.height * EYE_CENTER.y);
    const distance = Math.hypot(dx, dy) || 1;
    const strength = Math.min(1, distance / 160); // eyes settle in the middle when you are very close
    svg.style.setProperty('--lx', ((dx / distance) * MAX_OFFSET * strength).toFixed(2));
    svg.style.setProperty('--ly', ((dy / distance) * MAX_OFFSET * strength).toFixed(2));
  }

  const queue = () => {
    if (!frame) frame = requestAnimationFrame(update);
  };

  function lookAt(x, y) {
    if (!enabled) return;
    target = { x, y };
    queue();
  }

  function lookAtElement(element) {
    const box = element.getBoundingClientRect();
    lookAt(box.left + box.width / 2, box.top + box.height / 2);
  }

  document.addEventListener('pointermove', (event) => lookAt(event.clientX, event.clientY), { passive: true });

  return { lookAt, lookAtElement, refresh: queue };
}
