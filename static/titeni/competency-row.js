(() => {
  const trigger = document.querySelector("[data-add-item]");
  const row = document.getElementById("kompetensi-baru");
  const form = document.getElementById("competency-add-form");
  const cancel = row.querySelector("[data-cancel-item]");

  trigger.addEventListener("click", (event) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    row.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    form.elements.namedItem("code").focus();
  });

  cancel.addEventListener("click", (event) => {
    if (row.querySelector(".errorlist")) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    form.reset();
    row.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    trigger.focus();
  });
})();
