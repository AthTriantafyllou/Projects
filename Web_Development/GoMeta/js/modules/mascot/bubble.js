// The speech bubble that appears next to the mascot when it is clicked.
// Later this is the place where the AI chat will open.

export function createBubble(element, { onClose }) {
  const title = element.querySelector('[data-bubble-title]');
  const line = element.querySelector('[data-bubble-line]');
  const action = element.querySelector('.btn');
  let hideTimer = 0;

  element.querySelector('[data-bubble-close]').addEventListener('click', onClose);

  // mascot: { x, top, width, height } = where the standing mascot is, in page coordinates
  function show({ mascot, titleText, lineText }) {
    clearTimeout(hideTimer);
    title.textContent = titleText;
    line.textContent = lineText;
    element.hidden = false;

    const gap = 14;
    const pageWidth = document.documentElement.clientWidth;
    const width = element.offsetWidth;
    const height = element.offsetHeight;

    const side = mascot.x + mascot.width + gap + width <= pageWidth - 12 ? 'right' : 'left';
    element.dataset.side = side;
    element.style.left = `${side === 'right' ? mascot.x + mascot.width + gap : Math.max(12, mascot.x - width - gap)}px`;
    // The bubble sits beside the mascot with its bottom at the mascot's middle, so it normally stays
    // above the card. Near the top of the page it is pushed down so the sticky header never covers it.
    const headerSpace = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--header-h')) || 72;
    const lowestTop = scrollY + headerSpace + 12;
    element.style.top = `${Math.max(lowestTop, mascot.top + mascot.height * 0.5 - height)}px`;

    requestAnimationFrame(() => element.classList.add('is-in'));
  }

  function hide() {
    element.classList.remove('is-in');
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
      element.hidden = true;
    }, 220);
  }

  return {
    show,
    hide,
    contains: (node) => element.contains(node),
    focusAction: () => action.focus({ preventScroll: true }),
    get isOpen() {
      return !element.hidden;
    },
  };
}
