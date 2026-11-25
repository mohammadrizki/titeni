(() => {
  const form = document.getElementById("competency-order-form");
  const feedback = document.getElementById("competency-order-feedback");
  const entryRow = document.getElementById("kompetensi-baru");
  const body = entryRow.parentElement;
  let pending = false;
  let drag = null;

  const rows = () => [...body.querySelectorAll("[data-competency-id]")];
  const ids = (items) => items.map((item) => item.dataset.competencyId);
  const restore = (items) => items.forEach((row) => body.insertBefore(row, entryRow));

  async function saveOrder(previous) {
    const before = ids(previous);
    const after = ids(rows());
    if (before.every((id, index) => id === after[index])) return;

    const data = new FormData(form);
    before.forEach((id) => data.append("previous", id));
    after.forEach((id) => data.append("item", id));
    pending = true;
    feedback.textContent = "Menyimpan urutan…";
    try {
      const response = await fetch(form.action, { method: "POST", body: data });
      const result = await response.json();
      if (!response.ok || !result.saved) {
        throw new Error(result.error || "Urutan gagal disimpan. Muat ulang tabel.");
      }
      feedback.textContent = "Urutan tersimpan.";
    } catch (error) {
      restore(previous);
      feedback.textContent = error instanceof SyntaxError
        ? "Urutan gagal disimpan. Muat ulang tabel."
        : error.message;
    } finally {
      pending = false;
    }
  }

  body.addEventListener("pointerdown", (event) => {
    const handle = event.target.closest("[data-order-handle]");
    if (!handle || pending || drag || event.button !== 0 || !event.isPrimary) return;
    const row = handle.closest("tr");
    drag = { id: event.pointerId, row, previous: rows() };
    row.dataset.reordering = "";
    handle.focus({ preventScroll: true });
    event.preventDefault();
  });

  document.addEventListener("pointermove", (event) => {
    if (!drag || drag.id !== event.pointerId) return;
    const target = rows().find((row) => {
      if (row === drag.row) return false;
      const bounds = row.getBoundingClientRect();
      return event.clientY < bounds.top + bounds.height / 2;
    });
    if (drag.row.nextElementSibling !== (target || entryRow)) {
      body.insertBefore(drag.row, target || entryRow);
    }
  });

  function finishDrag(event) {
    if (!drag || (event.type !== "blur" && event.pointerId !== drag.id)) return;
    const { row, previous } = drag;
    drag = null;
    delete row.dataset.reordering;
    if (event.type === "pointerup") {
      row.querySelector("[data-order-handle]").focus({ preventScroll: true });
      void saveOrder(previous);
    } else {
      restore(previous);
    }
  }

  document.addEventListener("pointerup", finishDrag);
  document.addEventListener("pointercancel", finishDrag);
  window.addEventListener("blur", finishDrag);

  body.addEventListener("keydown", (event) => {
    const handle = event.target.closest("[data-order-handle]");
    if (!handle || pending || drag || !["ArrowUp", "ArrowDown"].includes(event.key)) return;
    event.preventDefault();
    const previous = rows();
    const row = handle.closest("tr");
    const index = previous.indexOf(row);
    if (event.key === "ArrowUp" && index > 0) {
      body.insertBefore(row, previous[index - 1]);
    } else if (event.key === "ArrowDown" && index < previous.length - 1) {
      body.insertBefore(row, previous[index + 2] || entryRow);
    } else {
      return;
    }
    handle.focus({ preventScroll: true });
    void saveOrder(previous);
  });
})();
