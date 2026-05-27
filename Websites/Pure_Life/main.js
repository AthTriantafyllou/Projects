/* =============================================
   Pure Life – main.js
   Handles: Socials popup, Boring Stuff popup
   ============================================= */

(function () {
    'use strict';

    /* ── helpers ── */
    const $  = (sel) => document.querySelector(sel);
    const on = (el, ev, fn) => el && el.addEventListener(ev, fn);

    /* ── elements ── */
    const socialsBtn     = $('#socialsBtn');
    const socialsPopup   = $('#socialsPopup');
    const boringBtn      = $('#boringBtn');
    const boringOverlay  = $('#boringOverlay');
    const boringClose    = $('#boringClose');
    const backdrop       = $('#popupBackdrop');

    /* ── state ── */
    let socialsOpen = false;
    let boringOpen  = false;

    /* ──────────────────────────────────────────
       SOCIALS POPUP
    ────────────────────────────────────────── */

    function openSocials() {
        socialsOpen = true;
        socialsPopup.classList.add('open');
        socialsBtn.classList.add('active');
        socialsBtn.setAttribute('aria-expanded', 'true');
        socialsPopup.setAttribute('aria-hidden', 'false');
        showBackdrop();
    }

    function closeSocials() {
        socialsOpen = false;
        socialsPopup.classList.remove('open');
        socialsBtn.classList.remove('active');
        socialsBtn.setAttribute('aria-expanded', 'false');
        socialsPopup.setAttribute('aria-hidden', 'true');
        if (!boringOpen) hideBackdrop();
    }

    on(socialsBtn, 'click', (e) => {
        e.stopPropagation();
        socialsOpen ? closeSocials() : openSocials();
    });

    /* ──────────────────────────────────────────
       BORING STUFF POPUP
    ────────────────────────────────────────── */

    function openBoring() {
        boringOpen = true;
        boringOverlay.classList.add('open');
        boringOverlay.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
        showBackdrop();
        // close socials if open
        if (socialsOpen) closeSocials();
    }

    function closeBoring() {
        boringOpen = false;
        boringOverlay.classList.remove('open');
        boringOverlay.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
        if (!socialsOpen) hideBackdrop();
    }

    on(boringBtn,   'click', openBoring);
    on(boringClose, 'click', closeBoring);

    /* ──────────────────────────────────────────
       BACKDROP  (click to close everything)
    ────────────────────────────────────────── */

    function showBackdrop() { backdrop.classList.add('show'); }
    function hideBackdrop()  { backdrop.classList.remove('show'); }

    on(backdrop, 'click', () => {
        if (socialsOpen) closeSocials();
        if (boringOpen)  closeBoring();
    });

    /* ──────────────────────────────────────────
       KEYBOARD: Escape closes anything open
    ────────────────────────────────────────── */

    on(document, 'keydown', (e) => {
        if (e.key === 'Escape') {
            if (socialsOpen) closeSocials();
            if (boringOpen)  closeBoring();
        }
    });

    /* ──────────────────────────────────────────
       Click outside socials popup (not backdrop)
    ────────────────────────────────────────── */

    on(document, 'click', (e) => {
        if (socialsOpen && !socialsPopup.contains(e.target) && e.target !== socialsBtn) {
            closeSocials();
        }
    });

})();





/* ===================== OUR STORY ANIMATIONS ===================== */

const timelineItems = document.querySelectorAll('.timeline-item');

if (timelineItems.length) {
    const timelineObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.15 });

    timelineItems.forEach(item => timelineObserver.observe(item));
}

const fadeEls = document.querySelectorAll('.value-card, .story-intro-photos, .story-intro-text, .team-photo');

if (fadeEls.length) {
    const fadeObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach((entry, i) => {
            if (entry.isIntersecting) {
                setTimeout(() => entry.target.classList.add('visible'), i * 80);
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1 });

    fadeEls.forEach(el => fadeObserver.observe(el));
}