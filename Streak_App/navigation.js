document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("nav button[data-nav]").forEach(btn => {
    btn.addEventListener("click", () => {
      const page = btn.dataset.nav;

      switch (page) {
        case "home":
          window.location.href = "/streaks/pages/home.html";
          break;
        case "presets":
          window.location.href = "/streaks/pages/presets.html";
          break;
        case "items":
          window.location.href = "/streaks/pages/items.html";
          break;
        case "settings":
          window.location.href = "/streaks/pages/settings.html";
          break;
      }
    });
  });
});
