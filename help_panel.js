/* Help stays above the workspace instead of changing its layout. */
(function () {
  "use strict";
  function install() {
    const body = document.getElementById("user-guide-body");
    const trigger = document.getElementById("toggle-user-guide");
    if (!body || !trigger || window.UfoHelpPanel) return;
    document.documentElement.classList.add("floating-help-enabled");
    // Keep original shortcut nodes and their native handlers intact.
    document.body.appendChild(body);
    body.classList.add("floating-help-panel");
    body.setAttribute("role", "dialog");
    body.setAttribute("aria-modal", "false");
    body.setAttribute("aria-labelledby", "help-panel-title");
    body.setAttribute("aria-describedby", "help-panel-intro");
    body.setAttribute("tabindex", "-1");
    const heading = document.createElement("div");
    heading.className = "floating-help-heading";
    heading.innerHTML = '<h2 id="help-panel-title">Help & guided tours</h2><button class="secondary-button" type="button" aria-label="Close help panel">×</button>';
    const intro = document.createElement("p");
    intro.id = "help-panel-intro";
    intro.textContent = "Start with a guided tour, or jump straight to a control.";
    body.prepend(heading, intro);
    trigger.setAttribute("aria-haspopup", "dialog");
    trigger.setAttribute("aria-controls", body.id);
    let open = !body.hidden;
    let frame = null;
    function position() {
      frame = null;
      if (body.hidden) return;
      const margin = 12, viewportWidth = document.documentElement.clientWidth;
      const anchor = trigger.getBoundingClientRect();
      const width = Math.min(420, viewportWidth - margin * 2);
      body.style.width = width + "px";
      const below = anchor.bottom + 10;
      const space = innerHeight - below - margin;
      // Near the bottom of a scrolled page, use a stable viewport position.
      const top = anchor.bottom > 0 && below < innerHeight && space >= Math.min(320, innerHeight - margin * 2)
        ? Math.max(margin, below) : margin;
      body.style.maxHeight = Math.min(580, innerHeight - top - margin) + "px";
      body.style.top = top + "px";
      body.style.left = Math.max(margin, Math.min(anchor.right - width, viewportWidth - width - margin)) + "px";
    }
    function queuePosition() {
      if (!body.hidden && frame === null) frame = requestAnimationFrame(position);
    }
    function sync() {
      const nextOpen = !body.hidden;
      if (trigger.textContent !== "Help") trigger.textContent = "Help";
      trigger.setAttribute("aria-label", nextOpen ? "Close help" : "Open help");
      trigger.title = nextOpen ? "Close help" : "Open help";
      if (nextOpen) {
        position();
        if (!open) {
          body.scrollTop = 0;
          body.focus({preventScroll:true});
        }
      }
      open = nextOpen;
    }
    function close(options) {
      if (body.hidden) return false;
      trigger.click();
      if (!options || options.returnFocus !== false) trigger.focus({preventScroll:true});
      return true;
    }
    heading.querySelector("button").addEventListener("click", () => close());
    // Direct workflow shortcut handlers navigate first. Dismiss the panel
    // before their scheduled focus/scroll or the tour's document handler.
    body.addEventListener("click", (event) => {
      if (event.target.closest("[data-guided-tour], .workflow-help-shortcuts button")) close({returnFocus:false});
    });
    document.addEventListener("pointerdown", (event) => {
      if (!body.hidden && !body.contains(event.target) && !trigger.contains(event.target)) close({returnFocus:false});
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !body.hidden) {
        event.preventDefault(); event.stopPropagation(); close();
      }
    }, true);
    new MutationObserver(sync).observe(body, {attributes:true, attributeFilter:["hidden"]});
    window.addEventListener("resize", queuePosition);
    document.addEventListener("scroll", queuePosition, true);
    window.UfoHelpPanel = Object.freeze({close, isOpen:() => !body.hidden});
    sync();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install, {once:true});
  else install();
})();
