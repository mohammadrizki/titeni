for (const trigger of document.querySelectorAll("[data-inline-add]")) {
  const row = document.getElementById(trigger.getAttribute("aria-controls"));
  if (!row) continue;

  if (trigger.hasAttribute("data-inline-add-enhance")) {
    row.hidden = !row.hasAttribute("data-inline-add-open");
    trigger.hidden = false;
    trigger.setAttribute("aria-expanded", String(!row.hidden));
  }

  trigger.addEventListener("click", (event) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    row.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    row.querySelector('input:not([type="hidden"]), select, textarea')?.focus();
  });
}
