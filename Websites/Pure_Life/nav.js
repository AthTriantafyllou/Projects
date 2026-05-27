const nav = document.getElementById('pageNav');
const navToggle = document.getElementById('navToggle');
const mobileMenu = document.getElementById('mobileMenu');
const mobileMenuOverlay = document.getElementById('mobileMenuOverlay');
const mobileMenuClose = document.getElementById('mobileMenuClose');

if (nav) {
    window.addEventListener('scroll', () => {
        nav.classList.toggle('scrolled', window.scrollY > 40);
    }, { passive: true });
}

function openMenu() {
    if (mobileMenu && mobileMenuOverlay && navToggle) {
        mobileMenu.classList.add('active');
        mobileMenuOverlay.classList.add('active');
        document.body.classList.add('menu-open');
        navToggle.setAttribute('aria-expanded', 'true');
    }
}

function closeMenu() {
    if (mobileMenu && mobileMenuOverlay && navToggle) {
        mobileMenu.classList.remove('active');
        mobileMenuOverlay.classList.remove('active');
        document.body.classList.remove('menu-open');
        navToggle.setAttribute('aria-expanded', 'false');
    }
}

if (navToggle) {
    navToggle.addEventListener('click', openMenu);
}

if (mobileMenuClose) {
    mobileMenuClose.addEventListener('click', closeMenu);
}

if (mobileMenuOverlay) {
    mobileMenuOverlay.addEventListener('click', closeMenu);
}

window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeMenu();
    }
});

const currentPage = window.location.pathname.split('/').pop() || 'index.html';

document
    .querySelectorAll('.nav-link, .mobile-menu-link, .nav-contact-btn, .mobile-menu-btn')
    .forEach(link => {
        const href = link.getAttribute('href');
        if (!href) return;

        const linkPage = href.split('/').pop();

        if (linkPage === currentPage) {
            link.classList.add('active');
        }
    });