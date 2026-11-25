// Entry point loaded on every page. Each feature lives in its own module.
import { initNav } from './modules/nav.js';
import { initReveal } from './modules/reveal.js';
import { initPageTransitions } from './modules/page-transitions.js';
import { initMascot } from './modules/mascot/index.js';

initNav();
initReveal();
initPageTransitions();
initMascot();
