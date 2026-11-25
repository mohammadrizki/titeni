(() => {
  const key = "titeni.theme";
  const modes = ["auto", "light", "dark"];
  const root = document.documentElement;

  try {
    const savedTheme = localStorage.getItem(key);
    if (modes.includes(savedTheme)) root.dataset.theme = savedTheme;
  } catch {
    // Browser storage is optional.
  }

  document.addEventListener("DOMContentLoaded", () => {
    for (const button of document.querySelectorAll("[data-front-theme-toggle]")) {
      button.addEventListener("click", () => {
        const mode = modes[(modes.indexOf(root.dataset.theme) + 1) % modes.length];
        root.dataset.theme = mode;
        try {
          localStorage.setItem(key, mode);
        } catch {
          // Keep the selected theme for this page.
        }
      });
    }
  });
})();
