// The GoMeta cursor: finds hiding places, peeks out, waves, watches you, and pops out when clicked.
//
// Any element with data-mascot-spot is a hiding place (it must have a solid background, and the
// mascot sits behind its top edge). Optional attributes on a spot:
//   data-mascot-spot="shrug"   shrug instead of waving
//   data-mascot-say="..."      replaces the second line in the speech bubble
//
// States (data-state on .mascot): hidden -> peek -> open

import { CONFIG } from './config.js';
import { TITLE, LINES } from './lines.js';
import { createEyes } from './eyes.js';
import { createBubble } from './bubble.js';

const random = (min, max) => min + Math.random() * (max - min);
const pickOne = (list) => list[Math.floor(Math.random() * list.length)];
const clamp = (value, min, max) => Math.min(Math.max(value, min), Math.max(min, max));

export function initMascot() {
  const root = document.querySelector('[data-mascot]');
  if (!root || !document.querySelector('[data-mascot-spot]')) return;

  const mascot = root.querySelector('.mascot');
  const button = root.querySelector('.mascot__btn');
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const eyes = createEyes(root.querySelector('.mascot__svg'), { enabled: !reduceMotion });
  const bubble = createBubble(root.querySelector('.mascot-bubble'), { onClose: () => close() });

  let state = 'hidden';
  let spot = null; // the element it is currently hiding behind
  let side = 'left';
  let timers = [];
  let anchorScroll = 0; // scroll position when it last peeked out

  root.hidden = false;
  mascot.dataset.pose = CONFIG.pose;

  // ---------- small helpers ----------

  function later(fn, ms) {
    const id = setTimeout(() => {
      timers = timers.filter((t) => t !== id);
      fn();
    }, ms);
    timers.push(id);
  }

  function clearTimers() {
    timers.forEach(clearTimeout);
    timers = [];
  }

  function setState(next) {
    state = next;
    mascot.dataset.state = next;
    button.setAttribute('aria-expanded', String(next === 'open'));
    eyes.refresh();
  }

  function act(name, duration) {
    if (reduceMotion) return;
    mascot.dataset.act = name;
    later(() => delete mascot.dataset.act, duration);
  }

  // ---------- hiding places ----------

  function measure(element) {
    const box = element.getBoundingClientRect();
    if (box.width < CONFIG.spotMinWidth || box.height < CONFIG.spotMinHeight) return null;
    const reveal = element.closest('.reveal');
    if (reveal && !reveal.classList.contains('is-visible')) return null; // not faded in yet
    return box;
  }

  // Is there free space above the spot's top edge, so the head is not tucked under a neighbouring card?
  function hasRoomAbove(box) {
    return [box.left + 40, box.left + box.width / 2, box.right - 40].every((x) => {
      const found = document.elementFromPoint(x, box.top - 30);
      return !found || !found.closest('[data-mascot-spot], .site-header, a, button');
    });
  }

  function chooseSpot() {
    const visible = [...document.querySelectorAll('[data-mascot-spot]')]
      .map((element) => ({ element, box: measure(element) }))
      .filter(
        ({ box }) =>
          box &&
          box.top > CONFIG.viewportTopMargin &&
          box.top < innerHeight - CONFIG.viewportBottomMargin &&
          hasRoomAbove(box),
      );
    if (!visible.length) return null;

    const others = visible.filter(({ element }) => element !== spot);
    const pool = (others.length ? others : visible)
      .sort((a, b) => Math.abs(a.box.top - innerHeight * 0.45) - Math.abs(b.box.top - innerHeight * 0.45))
      .slice(0, 3);
    return pickOne(pool).element;
  }

  // Puts the mascot on the top edge of a spot (while it is hidden, so nothing visibly jumps)
  function moveTo(element) {
    spot = element;
    side = side === 'left' ? 'right' : 'left';

    const box = element.getBoundingClientRect();
    const width = mascot.offsetWidth;
    const wanted = side === 'right' ? box.right - width - 28 : box.left + 28;
    const x = clamp(wanted, box.left + 12, box.right - width - 12);

    mascot.style.left = `${clamp(x, 8, document.documentElement.clientWidth - width - 8) + scrollX}px`;
    mascot.style.top = `${box.top + scrollY}px`;
    eyes.refresh();
  }

  // ---------- behaviour ----------

  function peek() {
    anchorScroll = scrollY;
    setState('peek');
    later(() => act(spot?.dataset.mascotSpot === 'shrug' ? 'shrug' : 'wave', 2300), CONFIG.waveDelay);
    scheduleMove();
  }

  function scheduleMove() {
    if (reduceMotion) return;
    later(relocate, random(CONFIG.idleMoveMin, CONFIG.idleMoveMax));
  }

  // Duck behind the current spot, hop to another visible one, peek out again
  function relocate() {
    if (state === 'open') return;
    clearTimers();
    if (document.hidden) return later(relocate, 3000);

    const next = chooseSpot();
    if (!next) return scheduleMove();
    if (next === spot && state === 'peek') {
      act('wave', 2300);
      return scheduleMove();
    }

    const go = () => {
      moveTo(next);
      later(peek, 420);
    };

    if (state === 'peek') {
      setState('hidden');
      later(go, 420);
    } else {
      go();
    }
  }

  function open() {
    if (state === 'open' || !spot) return;
    clearTimers();

    const box = spot.getBoundingClientRect();
    if (box.top < 300) scrollBy({ top: box.top - 340, behavior: reduceMotion ? 'auto' : 'smooth' });

    setState('open');
    later(() => act('wave', 1900), 450);
    later(() => {
      const standingTop = box.top + scrollY - mascot.offsetHeight * (CONFIG.pose === 'hover' ? 1.16 : 0.967);
      bubble.show({
        mascot: { x: parseFloat(mascot.style.left), top: standingTop, width: mascot.offsetWidth, height: mascot.offsetHeight },
        titleText: TITLE,
        lineText: spot.dataset.mascotSay || pickOne(LINES),
      });
      bubble.focusAction();
    }, 400);
  }

  function close({ returnFocus = true } = {}) {
    if (state !== 'open') return;
    const hadFocus = root.contains(document.activeElement);
    bubble.hide();
    setState('peek');
    if (hadFocus && returnFocus) button.focus({ preventScroll: true });
    scheduleMove();
  }

  // ---------- events ----------

  button.addEventListener('click', () => (state === 'open' ? close() : open()));

  // Keyboard users: tabbing to the mascot makes it peek out
  button.addEventListener('focus', () => {
    if (state !== 'hidden') return;
    if (spot) peek();
    else relocate();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') close();
  });

  document.addEventListener('pointerdown', (event) => {
    if (state !== 'open') return;
    if (mascot.contains(event.target) || bubble.contains(event.target)) return;
    close({ returnFocus: false });
  });

  // Moving on: duck while the page scrolls, then hop to a spot that is on screen
  let scrolling = 0;
  addEventListener(
    'scroll',
    () => {
      eyes.refresh();
      if (state === 'open') {
        const box = spot.getBoundingClientRect();
        if (box.bottom < 0 || box.top > innerHeight) close({ returnFocus: false });
        return;
      }
      // tiny nudges (a phone's address bar, a trackpad twitch) do not scare it
      if (state === 'peek' && Math.abs(scrollY - anchorScroll) < 60) return;
      clearTimeout(scrolling);
      if (state === 'peek') {
        clearTimers();
        setState('hidden');
      }
      scrolling = setTimeout(relocate, CONFIG.settleAfterScroll);
    },
    { passive: true },
  );

  addEventListener('resize', () => {
    if (spot) moveTo(spot);
  });

  // It likes to watch what you are typing
  document.addEventListener('focusin', (event) => {
    if (event.target.matches?.('input, textarea, select')) eyes.lookAtElement(event.target);
  });

  // First appearance
  addEventListener('load', () => later(relocate, CONFIG.firstPeekDelay), { once: true });
  if (document.readyState === 'complete') later(relocate, CONFIG.firstPeekDelay);
}
