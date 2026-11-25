for (const group of document.querySelectorAll("[data-permission-group]")) {
  const toggle = group.querySelector("[data-permission-group-toggle]");
  const permissions = [...group.querySelectorAll('input[type="checkbox"][name]')];
  if (!toggle || !permissions.length) continue;

  function syncGroup() {
    const selected = permissions.filter(permission => permission.checked).length;
    toggle.checked = selected === permissions.length;
    toggle.indeterminate = selected > 0 && selected < permissions.length;
  }

  group.addEventListener("change", event => {
    if (event.target === toggle) {
      for (const permission of permissions) permission.checked = toggle.checked;
    }
    syncGroup();
  });

  syncGroup();
  toggle.hidden = false;
}
