/* =========================
   LAYER BUTTONS
========================= */
const buttons = document.querySelectorAll(".hero-btn");
const layers = document.querySelectorAll(".layer");

buttons.forEach(button => {
  button.addEventListener("click", () => {
    const targetLayer = button.dataset.layer;

    // buttons
    buttons.forEach(btn => btn.classList.remove("active"));
    button.classList.add("active");

    // layers
    layers.forEach(layer => layer.classList.remove("active"));
    document
      .getElementById(`layer-${targetLayer}`)
      .classList.add("active");
  });
});


/* =========================
   FAQ ACCORDION
========================= */
const faqItems = document.querySelectorAll(".faq-item");

faqItems.forEach(item => {
  const question = item.querySelector(".faq-question");
  const icon = item.querySelector(".faq-icon");

  question.addEventListener("click", () => {
    const isOpen = item.classList.contains("active");

    if (isOpen) {
      item.classList.remove("active");
      icon.textContent = "+";
    } else {
      item.classList.add("active");
      icon.textContent = "−";
    }
  });
});


/* =========================
   PORTFOLIO CAROUSELS
   (SCOPED PER LAYER)
========================= */
document.querySelectorAll(".portfolio").forEach(portfolio => {
  const items = portfolio.querySelectorAll(".portfolio-item");
  const dots = portfolio.querySelectorAll(".dot");

  let currentIndex = 0;
  let interval;

  function showItem(index) {
    items.forEach(item => item.classList.remove("active"));
    dots.forEach(dot => dot.classList.remove("active"));

    items[index].classList.add("active");
    dots[index].classList.add("active");

    currentIndex = index;
  }

  dots.forEach((dot, index) => {
    dot.addEventListener("click", () => {
      clearInterval(interval);
      showItem(index);
      startAutoSlide();
    });
  });

  function startAutoSlide() {
    interval = setInterval(() => {
      const nextIndex = (currentIndex + 1) % items.length;
      showItem(nextIndex);
    }, 3000);
  }

  startAutoSlide();
});








/* =========================
   POP UP CONTACT FORM
========================= */

  const modal = document.getElementById("contactModal");
  const modalClose = document.getElementById("modalClose");

  const openButtons = [
    document.querySelector(".nav-cta"),
    document.querySelector(".cta-btn")
  ];

  openButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      modal.classList.add("active");
    });
  });

  modalClose.addEventListener("click", () => {
    modal.classList.remove("active");
  });

  modal.addEventListener("click", (e) => {
    if (e.target === modal) {
      modal.classList.remove("active");
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      modal.classList.remove("active");
    }
  });




  const form = document.querySelector(".contact-form");
  const successBox = document.querySelector(".form-success");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const formData = new FormData(form);

    const response = await fetch("send.php", {
      method: "POST",
      body: formData
    });

    const result = await response.text();

    if (result.trim() === "success") {
      form.style.display = "none";
      successBox.hidden = false;

      // Optional: auto-close after 3 seconds
      setTimeout(() => {
        document.getElementById("contactModal").classList.remove("active");
        form.reset();
        form.style.display = "flex";
        successBox.hidden = true;
      }, 3000);
    }
  });






(() => {
  const trigger = document.getElementById("servicesTrigger");
  const menu = document.getElementById("servicesMenu");

  let closeTimer = null;

  const openMenu = () => {
    if (closeTimer) clearTimeout(closeTimer);

    const r = trigger.getBoundingClientRect();
    const top = r.bottom + 10;               // spacing under trigger
    const left = r.left + r.width / 2;

    menu.style.top = `${top}px`;
    menu.style.left = `${left}px`;
    menu.style.transform = "translate(-50%, 0)";

    menu.classList.add("open");
    menu.setAttribute("aria-hidden", "false");
  };

  const closeMenu = () => {
    menu.classList.remove("open");
    menu.setAttribute("aria-hidden", "true");
  };

  const closeMenuDelayed = () => {
    closeTimer = setTimeout(closeMenu, 120); // small delay = no flicker
  };

  // Hover behavior (robust)
  trigger.addEventListener("mouseenter", openMenu);
  trigger.addEventListener("mouseleave", closeMenuDelayed);
  menu.addEventListener("mouseenter", openMenu);
  menu.addEventListener("mouseleave", closeMenuDelayed);

  // Click toggle (nice for mobile)
  trigger.addEventListener("click", (e) => {
    e.preventDefault();
    if (menu.classList.contains("open")) closeMenu();
    else openMenu();
  });

  // Close on outside click
  document.addEventListener("click", (e) => {
    if (!menu.classList.contains("open")) return;
    if (e.target === trigger || trigger.contains(e.target)) return;
    if (menu.contains(e.target)) return;
    closeMenu();
  });

  // Reposition on scroll/resize if open
  window.addEventListener("scroll", () => {
    if (menu.classList.contains("open")) openMenu();
  }, { passive: true });

  window.addEventListener("resize", () => {
    if (menu.classList.contains("open")) openMenu();
  });
})();
