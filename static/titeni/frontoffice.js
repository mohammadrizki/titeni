(() => {
  const themeToggle = document.querySelector("[data-front-theme-toggle]");
  if (themeToggle) themeToggle.hidden = false;

  const workspace = document.querySelector("[data-workspace]");
  const toggle = document.querySelector("[data-sidebar-toggle]");
  if (!workspace || !toggle) return;

  const wideViewport = matchMedia("(min-width: 64rem)");
  const preferenceKey = "titeni.frontoffice.sidebar";
  let desktopOpen = true;

  try {
    desktopOpen = localStorage.getItem(preferenceKey) !== "closed";
  } catch {
    // Leave the desktop sidebar open when browser storage is unavailable.
  }

  function setOpen(open) {
    workspace.dataset.sidebarOpen = String(open);
    toggle.setAttribute("aria-expanded", String(open));
    toggle.title = open ? "Sembunyikan sidebar" : "Tampilkan sidebar";
    toggle.setAttribute("aria-label", toggle.title);
  }

  const resetForViewport = () => setOpen(wideViewport.matches && desktopOpen);
  resetForViewport();
  toggle.hidden = false;
  wideViewport.addEventListener("change", resetForViewport);
  toggle.addEventListener("click", () => {
    const open = workspace.dataset.sidebarOpen !== "true";
    setOpen(open);
    if (wideViewport.matches) {
      desktopOpen = open;
      try {
        localStorage.setItem(preferenceKey, open ? "open" : "closed");
      } catch {
        // Keep the current choice without persisting it.
      }
    }
  });
})();

document.querySelectorAll("[data-academic-tabs]").forEach((nav) => {
  const scroller = nav.querySelector("[data-academic-tabs-scroll]");
  const links = Array.from(scroller.querySelectorAll("a"));

  function updateEdges() {
    nav.toggleAttribute("data-more-left", scroller.scrollLeft > 1);
    nav.toggleAttribute(
      "data-more-right",
      scroller.scrollWidth - scroller.clientWidth - scroller.scrollLeft > 1,
    );
  }

  function reveal(link) {
    const frame = scroller.getBoundingClientRect();
    const tab = link.getBoundingClientRect();
    if (tab.left < frame.left) scroller.scrollLeft += tab.left - frame.left;
    if (tab.right > frame.right) scroller.scrollLeft += tab.right - frame.right;
  }

  scroller.addEventListener("scroll", updateEdges, { passive: true });
  new ResizeObserver(updateEdges).observe(scroller);
  links.forEach((link, index) => {
    link.addEventListener("focus", () => reveal(link));
    link.addEventListener("keydown", (event) => {
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      const destinations = {
        ArrowLeft: (index - 1 + links.length) % links.length,
        ArrowRight: (index + 1) % links.length,
        Home: 0,
        End: links.length - 1,
      };
      if (!Object.hasOwn(destinations, event.key)) return;
      event.preventDefault();
      links[destinations[event.key]].focus({ preventScroll: true });
    });
  });
  const current = nav.querySelector("[aria-current]");
  if (current) reveal(current);
  updateEdges();
});
