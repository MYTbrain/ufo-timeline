(function (root, factory) {
  "use strict";
  let visuals = root && root.UfoAnalysisOverviewVisuals;
  if (typeof module === "object" && module.exports) { try { visuals = require("./analysis_overview_visuals.js"); } catch (_) {} }
  const api = factory(visuals);
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoAnalysisOverviewView = api;
})(typeof self !== "undefined" ? self : globalThis, function (visuals) {
  "use strict";
  const number = value => (typeof value === "number" || typeof value === "string" && value.trim() !== "") && Number.isFinite(Number(value)) ? Number(value).toLocaleString() : "Not available";
  const percent = value => Number.isFinite(value) ? (100 * value).toFixed(value > 0 && value < .01 ? 2 : 1) + "%" : "Not available";
  const UNKNOWN = /^(?:__|unknown|not_indexed|unavailable)/;
  const PALETTE = ["#70c3bd", "#d3af79", "#86a9d9", "#c89cc7", "#9bbd7f", "#d49e8b", "#9caeb7", "#aaa3d1"];
  const DIMENSION_LABELS = { craft: "Craft", being: "Being description", country: "Country", decade: "Decade", month: "Month", source: "Source" };
  const CRAFT_LABELS = { chevron_boomerang: "Chevron / boomerang", cigar_cylinder: "Cigar / cylinder", disc_saucer: "Disc / saucer", dumbbell_barbell: "Dumbbell / barbell", formation: "Formation", oval_egg: "Oval / egg", rectangle_box: "Rectangle / box", sphere_orb: "Sphere / orb", cone: "Cone", diamond: "Diamond", fireball_meteor_like: "Fireball / meteor-like", light: "Light", teardrop: "Teardrop", triangle: "Triangle" };
  const differenceReady = typeof visuals?.cellMetrics === "function";
  const signedPp = value => {
    if (!Number.isFinite(value)) return "Not available";
    const magnitude = Math.abs(value);
    if (magnitude <= 1e-10) return "0.0 pp";
    return (value > 0 ? "+" : "−") + (magnitude < .1 ? magnitude.toPrecision(1) : magnitude.toFixed(1)) + " pp";
  };
  const craftColor = key => (typeof visuals?.craftColor === "function" ? visuals.craftColor(key) : null) || "#8ca9b4";
  let nextId = 0;
  function create(target, configuration) {
    if (!target || !target.ownerDocument) throw new Error("An Analysis overview target is required.");
    const doc = target.ownerDocument, config = configuration || {}, id = "analysis-overview-" + (++nextId);
    let destroyed = false, current = null, lastInput = null, lane = "all", mode = "share", craftFocus = null;
    const openCards = new Set(), openTables = new Set();
    function node(tag, className, text) {
      const el = doc.createElement(tag);
      if (className) el.className = className;
      if (text != null) el.textContent = String(text);
      return el;
    }
    function button(text, callback, className) {
      const el = node("button", className || "", text); el.type = "button";
      el.addEventListener("click", callback); return el;
    }
    function navigate(card, focus) {
      const request = { section: card.section || "overview", card: card.key, lane, focus: focus || null, source: "overview-dashboard" };
      if (focus && typeof config.onInspect === "function") return config.onInspect(request);
      if (typeof config.onOpenSection === "function") return config.onOpenSection(request.section, request);
    }
    function setStyle(el, key, value) { if (el.style?.setProperty) el.style.setProperty(key, value); else el.style[key] = value; }
    function note(parent, text, extra) { if (text) parent.appendChild(node("p", "analysis-overview-note" + (extra ? " " + extra : ""), text)); }
    function focusedControl() {
      const active = doc.activeElement;
      if (!active || typeof active.getAttribute !== "function") return null;
      let ancestor = active;
      while (ancestor && ancestor !== target) ancestor = ancestor.parentNode;
      if (ancestor !== target) return null;
      if (active.getAttribute("aria-label") === "Overview report lens") return { type: "lens" };
      const craft = active.getAttribute("data-overview-craft-key");
      if (craft) return { type: "craft", key: craft, owner: active.getAttribute("data-overview-focus-owner") };
      if (active.getAttribute("data-overview-clear-focus") === "true") return { type: "clear-focus" };
      const key = active.getAttribute("data-overview-display");
      return ["share", "count", "difference"].includes(key) ? { type: "display", key } : null;
    }
    function commit(root, focus) {
      target.replaceChildren(root);
      const selector = focus?.type === "lens" ? ".analysis-overview-lens select" : focus?.type === "display" ? '[data-overview-display="' + focus.key + '"]' : null;
      let control = focus?.type === "craft" ? Array.from(target.querySelectorAll?.("button") || []).find(item => item.getAttribute("data-overview-craft-key") === focus.key && item.getAttribute("data-overview-focus-owner") === focus.owner)
        : focus?.type === "clear-focus" ? target.querySelector?.(".analysis-overview-lens select") : selector && target.querySelector?.(selector);
      if (!control && focus?.type === "craft") control = target.querySelector?.(".analysis-overview-lens select");
      if (control?.focus) control.focus();
    }
    function craftControl(key, label, owner, className) {
      const control = button("", () => { craftFocus = craftFocus === key ? null : key; render(lastInput); }, "analysis-overview-craft-focus " + (className || ""));
      control.setAttribute("data-overview-craft-key", key); control.setAttribute("data-overview-focus-owner", owner);
      control.setAttribute("aria-pressed", String(craftFocus === key));
      control.setAttribute("aria-label", "Highlight " + label + " across craft charts. Visual emphasis only; report populations stay unchanged.");
      control.title = "Highlight craft across these charts; no reports are filtered."; setStyle(control, "--overview-category", craftColor(key));
      if (craftFocus && craftFocus !== key) control.className += " is-craft-muted";
      control.append(node("i", "analysis-overview-craft-dot"), node("span", "", label)); return control;
    }
    function state(message, pending) {
      const box = node("div", "analysis-overview-state"); box.setAttribute("role", pending ? "status" : "note");
      box.appendChild(node("strong", "", pending ? "Building your Analysis overview" : "Analysis overview"));
      note(box, message); target.replaceChildren(box);
    }
    function dimensions(value, card) {
      const label = (item, dimension) => {
        if (item.label && item.label !== item.key) return item.label;
        if (dimension === "craft" && typeof visuals?.craftLabel === "function") return visuals.craftLabel(item.key);
        if (dimension === "craft" && CRAFT_LABELS[item.key]) return CRAFT_LABELS[item.key];
        if (dimension === "source" && /^(?:ufocat|nuforc|mufon)$/i.test(item.key)) return item.key.toUpperCase();
        return item.label || item.key;
      };
      const columns = (Array.isArray(value?.columns) ? value.columns : (value?.columnTotals || []).map(item => ({ key: item.key, label: item.label, totalN: item.count }))).map(item => ({ ...item, label: label(item, card?.columnDimension) }));
      const rows = (Array.isArray(value?.rows) ? value.rows : (value?.rowTotals || []).map(item => ({ key: item.key, label: item.label, totalN: item.count,
        counts: columns.map(column => (value?.cells || []).find(cell => cell.rowKey === item.key && cell.columnKey === column.key)?.count || 0) }))).map(item => ({ ...item, label: label(item, card?.rowDimension) }));
      return { columns, rows };
    }
    function selectedAxes(card, value) {
      const axes = dimensions(value, card), reference = dimensions(card.lanes?.all || value, card); let lensFallback = false;
      const pick = (items, totals, limit, ordered) => {
        const ranked = totals.filter(item => !UNKNOWN.test(item.key)).slice().sort((a, b) => Number(b.totalN || b.count || 0) - Number(a.totalN || a.count || 0));
        const keys = new Set(ranked.slice(0, limit).map(item => item.key));
        const chosen = items.filter(item => keys.has(item.key) || UNKNOWN.test(item.key));
        if (!chosen.some(item => !UNKNOWN.test(item.key)) && items.some(item => !UNKNOWN.test(item.key))) {
          lensFallback = true;
          const fallback = items.filter(item => !UNKNOWN.test(item.key)).slice().sort((a, b) => Number(b.totalN || b.count || 0) - Number(a.totalN || a.count || 0));
          fallback.slice(0, limit).forEach(item => chosen.push(item));
        }
        if (ordered) return chosen;
        return chosen.sort((a, b) => Number(UNKNOWN.test(a.key)) - Number(UNKNOWN.test(b.key)) || Number(b.totalN || b.count || 0) - Number(a.totalN || a.count || 0));
      };
      const columns = pick(axes.columns, reference.columns, card.columnDimension === "month" ? 12 : 7, card.columnOrder === "chronological" || card.columnDimension === "era" || card.columnDimension === "month");
      const rows = pick(axes.rows, reference.rows, card.rowDimension === "month" ? 12 : 7, card.rowOrder === "chronological" || card.rowDimension === "month");
      if (craftFocus && card.columnDimension === "craft" && !columns.some(item => item.key === craftFocus)) { const focused = axes.columns.find(item => item.key === craftFocus); if (focused) columns.push(focused); }
      if (craftFocus && card.rowDimension === "craft" && !rows.some(item => item.key === craftFocus)) { const focused = axes.rows.find(item => item.key === craftFocus); if (focused) rows.push(focused); }
      return { allColumns: axes.columns, allRows: axes.rows, columns, rows, lensFallback };
    }
    function cellCount(row, column, allColumns) {
      const index = allColumns.findIndex(value => value.key === column.key);
      const value = row.counts?.[index];
      return Number.isFinite(Number(value)) ? Math.max(0, Number(value)) : 0;
    }
    function legend(parent, maximum) {
      const box = node("div", "analysis-overview-scale");
      if (mode === "difference") { const ramp = node("i", "analysis-overview-scale-ramp"); ramp.appendChild(node("span", "analysis-overview-scale-zero", "0")); box.className += " is-difference"; box.append(node("span", "", "−50 pp"), ramp, node("span", "", "+50 pp"), node("span", "analysis-overview-missing-key", "Striped: unsigned row share")); }
      else box.append(node("span", "", mode === "share" ? "Within each row" : "Report volume"), node("i", "analysis-overview-scale-ramp"),
        node("span", "", mode === "share" ? "0–100%" : "0–" + number(maximum)), node("span", "analysis-overview-missing-key", "Striped: missing"));
      parent.appendChild(box);
    }
    function matrix(card, value, axes) {
      const wrap = node("div", "analysis-overview-matrix-wrap"), table = node("table", "analysis-overview-matrix");
      if (card.columnDimension === "month") table.className += " is-calendar-matrix";
      setStyle(table, "--overview-column-count", axes.columns.length);
      table.setAttribute("aria-label", card.title + ". " + (mode === "difference" ? "Percentage-point difference between each row and the current report lens" : mode === "share" ? "Shares of each row's reports" : "Report counts") + ". Arrow keys move between categories.");
      const head = node("thead"), header = node("tr");
      header.appendChild(node("th", "analysis-overview-row-heading", card.rowLabel || DIMENSION_LABELS[card.rowDimension] || ""));
      axes.columns.forEach(column => { const th = node("th"); th.scope = "col"; th.title = column.label || column.key;
        if (card.columnDimension === "craft" && !UNKNOWN.test(column.key)) th.appendChild(craftControl(column.key, column.label || column.key, card.key + ":header", "analysis-overview-header-craft"));
        else th.textContent = column.key === "__unknown__" ? "Unknown" : column.label || column.key;
        if (craftFocus && card.columnDimension === "craft" && column.key !== craftFocus) th.className = "is-craft-muted";
        header.appendChild(th); });
      head.appendChild(header); table.appendChild(head);
      const body = node("tbody"), buttons = [], maximum = Math.max(0, ...axes.allRows.flatMap(row => row.counts || [])), rowMaximum = Math.max(0, ...axes.allRows.map(row => Number(row.totalN) || 0));
      axes.rows.forEach((row, rowIndex) => {
        const tr = node("tr"), th = node("th", "analysis-overview-row-heading"); th.scope = "row";
        th.append(node("span", "", row.label || row.key), node("small", "", "n=" + number(row.totalN)));
        const rowVolume = node("span", "analysis-overview-row-volume"), rowFill = node("i"); rowVolume.setAttribute("aria-hidden", "true"); setStyle(rowFill, "width", rowMaximum > 0 ? (100 * row.totalN / rowMaximum) + "%" : "0%"); rowVolume.appendChild(rowFill); th.appendChild(rowVolume);
        if (craftFocus && card.rowDimension === "craft" && row.key !== craftFocus) th.className += " is-craft-muted";
        tr.appendChild(th); buttons[rowIndex] = [];
        axes.columns.forEach((column, columnIndex) => {
          const count = cellCount(row, column, axes.allColumns), share = Number(row.totalN) > 0 ? count / Number(row.totalN) : NaN;
          const td = node("td"), unknown = UNKNOWN.test(row.key) || UNKNOWN.test(column.key);
          const metrics = differenceReady ? visuals.cellMetrics({ count, rowTotalN: row.totalN, columnTotalN: column.totalN, totalN: value.totalN }) : null;
          const validDifference = mode === "difference" && !unknown && Number.isFinite(metrics?.deltaPp);
          const text = validDifference ? signedPp(metrics.deltaPp) : mode === "difference" ? unknown && Number.isFinite(share) ? percent(share) : "—" : mode === "share" ? percent(share) : number(count);
          const label = (row.label || row.key) + "; " + (column.label || column.key) + ": " + number(count) + " report representations, " + percent(share) + " of " + number(row.totalN) + " row reports. "
            + (validDifference ? signedPp(metrics.deltaPp) + " versus this report lens's " + percent(metrics.baselineShare) + " category share; baseline includes this row. " : mode === "difference" && unknown ? "Missing category; unsigned row share is displayed. " : "")
            + (count ? "Open " + card.section + " analysis." : "No reports in this category.");
          const cell = count > 0 ? button(text, () => navigate(card, { rowKey: row.key, columnKey: column.key, count, rowTotalN: Number(row.totalN) }), "analysis-overview-cell") : node("span", "analysis-overview-cell" + (validDifference ? "" : " is-zero"), mode === "difference" ? text : "0");
          cell.setAttribute("aria-label", label); cell.title = label;
          if (unknown) cell.className += " is-unknown";
          if (validDifference) { cell.className += " is-difference" + (metrics.deltaPp < 0 ? " is-below" : " is-above"); setStyle(cell, "--overview-intensity", Math.min(1, Math.abs(metrics.deltaPp) / 50)); }
          else { const strength = mode === "share" || mode === "difference" ? share : maximum > 0 ? count / maximum : 0; setStyle(cell, "--overview-intensity", count > 0 ? Math.max(.1, Math.min(1, strength)) : 0); }
          if (craftFocus && (card.columnDimension === "craft" && column.key !== craftFocus || card.rowDimension === "craft" && row.key !== craftFocus)) cell.className += " is-craft-muted";
          if (count > 0) { cell.tabIndex = -1; buttons[rowIndex][columnIndex] = cell; }
          td.appendChild(cell); tr.appendChild(td);
        }); body.appendChild(tr);
      });
      const available = buttons.flat().filter(Boolean); if (available.length) available[0].tabIndex = 0;
      buttons.forEach((row, y) => row.forEach((cell, x) => {
        if (!cell) return;
        cell.addEventListener("keydown", event => {
          let next = null;
          if (event.key === "Home") next = row.find(Boolean);
          else if (event.key === "End") next = row.slice().reverse().find(Boolean);
          else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
            const step = event.key === "ArrowLeft" ? -1 : 1;
            for (let nx = x + step; nx >= 0 && nx < row.length; nx += step) if (row[nx]) { next = row[nx]; break; }
          } else if (event.key === "ArrowUp" || event.key === "ArrowDown") {
            const step = event.key === "ArrowUp" ? -1 : 1;
            for (let ny = y + step; ny >= 0 && ny < buttons.length; ny += step) if (buttons[ny]?.[x]) { next = buttons[ny][x]; break; }
          }
          if (next) { event.preventDefault(); available.forEach(item => { item.tabIndex = -1; }); next.tabIndex = 0; next.focus(); }
        });
      }));
      table.appendChild(body); wrap.appendChild(table); legend(wrap, maximum); note(wrap, "Row volumes scaled within this chart · longest bar = " + number(rowMaximum) + " reports", "analysis-overview-volume-note"); return wrap;
    }
    function profiles(card, value, axes) {
      const box = node("div", "analysis-overview-profiles"), columns = axes.columns;
      const legendBox = node("div", "analysis-overview-profile-legend");
      const color = column => UNKNOWN.test(column.key) ? "var(--overview-unknown)" : card.columnDimension === "craft" ? craftColor(column.key) : PALETTE[columns.indexOf(column) % PALETTE.length];
      columns.forEach(column => {
        if (card.columnDimension === "craft" && !UNKNOWN.test(column.key)) legendBox.appendChild(craftControl(column.key, column.label || column.key, card.key + ":legend", "analysis-overview-profile-craft"));
        else { const key = node("span"); setStyle(key, "--overview-category", color(column)); key.append(node("i"), node("span", "", column.label || column.key)); legendBox.appendChild(key); }
      });
      if (axes.allColumns.length > columns.length) { const key = node("span"); setStyle(key, "--overview-category", "var(--overview-other)"); key.append(node("i"), node("span", "", "Other categories")); legendBox.appendChild(key); }
      axes.rows.forEach(row => {
        const item = button("", () => navigate(card, { rowKey: row.key, count: Number(row.totalN) }), "analysis-overview-profile");
        const label = node("span", "analysis-overview-profile-heading"); label.append(node("strong", "", row.label || row.key), node("span", "", number(row.totalN) + " reports"));
        const bar = node("span", "analysis-overview-profile-bar"); bar.setAttribute("aria-hidden", "true");
        let shown = 0;
        columns.forEach(column => { const n = cellCount(row, column, axes.allColumns); shown += n; if (!n || !row.totalN) return;
          const segment = node("span"); setStyle(segment, "width", (100 * n / row.totalN) + "%"); setStyle(segment, "--overview-category", color(column));
          if (craftFocus && card.columnDimension === "craft" && column.key !== craftFocus) segment.className = "is-craft-muted";
          segment.setAttribute("data-overview-craft-segment", column.key); bar.appendChild(segment); });
        const remainder = Math.max(0, Number(row.totalN) - shown);
        if (remainder && row.totalN) { const segment = node("span"); setStyle(segment, "width", (100 * remainder / row.totalN) + "%"); setStyle(segment, "--overview-category", "var(--overview-other)"); if (craftFocus) segment.className = "is-craft-muted"; bar.appendChild(segment); }
        item.append(label, bar);
        item.setAttribute("aria-label", (row.label || row.key) + ": " + number(row.totalN) + " report representations. " + columns.map(column => (column.label || column.key) + " " + percent(row.totalN > 0 ? cellCount(row, column, axes.allColumns) / row.totalN : 0)).join("; ") + ". Open geography analysis.");
        box.appendChild(item);
      });
      box.appendChild(legendBox); note(box, "Each bar is the craft mix within one region. Lengths are shares, so large catalogs do not outweigh smaller ones."); return box;
    }
    function highlights(card, value) {
      if (typeof visuals?.deriveHighlights !== "function") return null;
      const result = visuals.deriveHighlights(card, value, { limit: 2, minRowN: 20, minCount: 5 });
      if (!result.highlights?.length) return null;
      const box = node("div", "analysis-overview-contrasts"), heading = node("div", "analysis-overview-contrast-heading");
      heading.append(node("strong", "", "Descriptive contrasts"), node("span", "analysis-overview-track-key", "● This row   ◇ Report lens · 0–100%")); box.appendChild(heading);
      result.highlights.slice(0, 2).forEach(item => {
        const copy = dimensions(value, card), row = copy.rows.find(row => row.key === item.rowKey), column = copy.columns.find(column => column.key === item.columnKey);
        const rowLabel = row?.label || item.rowLabel, columnLabel = column?.label || item.columnLabel;
        const action = button("", () => navigate(card, { rowKey: item.rowKey, columnKey: item.columnKey, count: item.count, rowTotalN: item.rowTotalN }), "analysis-overview-contrast");
        const line = node("span", "analysis-overview-contrast-label"); line.append(node("strong", "", rowLabel + " · " + columnLabel), node("b", item.deltaPp < 0 ? "is-below" : "is-above", signedPp(item.deltaPp))); action.appendChild(line);
        const track = node("span", "analysis-overview-contrast-track"); track.setAttribute("aria-hidden", "true");
        const link = node("i", "analysis-overview-contrast-join"), rowMark = node("i", "analysis-overview-contrast-row"), baselineMark = node("i", "analysis-overview-contrast-baseline");
        const rowPosition = Math.max(0, Math.min(100, item.share * 100)), baselinePosition = Math.max(0, Math.min(100, item.baselineShare * 100));
        setStyle(link, "left", Math.min(rowPosition, baselinePosition) + "%"); setStyle(link, "width", Math.abs(rowPosition - baselinePosition) + "%");
        setStyle(rowMark, "left", rowPosition + "%"); setStyle(baselineMark, "left", baselinePosition + "%"); track.append(link, rowMark, baselineMark); action.appendChild(track);
        action.appendChild(node("span", "analysis-overview-contrast-count", number(item.count) + "/" + number(item.rowTotalN) + " reports · " + percent(item.share) + " in this row / " + percent(item.baselineShare) + " in this lens"));
        action.setAttribute("aria-label", rowLabel + "; " + columnLabel + ": " + number(item.count) + " of " + number(item.rowTotalN) + " reports, " + percent(item.share) + " in this row versus " + percent(item.baselineShare) + " in the current report lens; " + signedPp(item.deltaPp) + ". Descriptive contrast; no significance test. Open related " + card.section + " analysis.");
        box.appendChild(action);
      });
      return box;
    }
    function exactTable(card, value) {
      const details = node("details", "analysis-overview-details"), summary = node("summary", "", "Exact counts & coverage"); details.appendChild(summary); details.open = openTables.has(card.key);
      let built = false;
      function build() {
        if (built) return; built = true;
        const axes = dimensions(value, card), wrap = node("div", "analysis-overview-exact-wrap"), table = node("table", "analysis-overview-exact");
        table.appendChild(node("caption", "", card.title + " · " + (current.lanes?.find(item => item.key === lane)?.label || "Current reports") + " · report representations" + (mode === "difference" ? ". Pooled report-lens baseline includes each row." : "") + (card.multiLabel ? " Being-label memberships can overlap." : "")));
        const head = node("thead"), tr = node("tr");
        const headers = [card.rowLabel || DIMENSION_LABELS[card.rowDimension] || "Category", card.columnLabel || DIMENSION_LABELS[card.columnDimension] || "Compared category", "Reports", "Row reports", "Share of row"];
        if (mode === "difference") headers.push("Report-lens share", "Difference (pp)");
        headers.forEach(text => { const th = node("th", "", text); th.scope = "col"; tr.appendChild(th); }); head.appendChild(tr); table.appendChild(head);
        const body = node("tbody");
        axes.rows.forEach(row => axes.columns.forEach(column => {
          const n = cellCount(row, column, axes.columns), unknown = UNKNOWN.test(row.key) || UNKNOWN.test(column.key);
          const metrics = differenceReady ? visuals.cellMetrics({ count: n, rowTotalN: row.totalN, columnTotalN: column.totalN, totalN: value.totalN }) : null;
          if (!n && !(mode === "difference" && !unknown && Number.isFinite(metrics?.deltaPp))) return;
          const fields = [row.label || row.key, column.label || column.key, number(n), number(row.totalN), percent(row.totalN > 0 ? n / row.totalN : NaN)];
          if (mode === "difference") fields.push(percent(metrics?.baselineShare), unknown ? "—" : signedPp(metrics?.deltaPp));
          const tr = node("tr"); fields.forEach(text => tr.appendChild(node("td", "", text))); body.appendChild(tr);
        })); table.appendChild(body); wrap.appendChild(table); details.appendChild(wrap);
        note(details, number(value.eligibleN || 0) + " with both fields indexed; " + number(value.unknownN || 0) + " missing at least one field. Missing categories remain in the chart and denominator.");
        (card.notes || []).forEach(text => note(details, text));
        if (card.multiLabel) note(details, "A report can have more than one being label. Memberships can overlap; do not add rows as independent incidents.");
      }
      details.addEventListener("toggle", () => { if (details.open) { openTables.add(card.key); build(); } else openTables.delete(card.key); });
      if (details.open) build(); return details;
    }
    function renderCard(card, large) {
      const article = node("article", "analysis-overview-card" + (large ? " analysis-overview-card-lead" : "")), titleId = id + "-" + card.key;
      article.setAttribute("aria-labelledby", titleId);
      const header = node("div", "analysis-overview-card-header"), heading = node("div");
      const title = node("h3", "", card.title); title.id = titleId; heading.appendChild(title); if (card.question) heading.appendChild(node("p", "analysis-overview-question", card.question));
      header.append(heading, button("Explore →", () => navigate(card), "analysis-overview-explore")); article.appendChild(header);
      const value = card.lanes?.[lane];
      if (!value || value.available === false) { note(article, value?.reason || "This comparison needs indexed fields that are not available for this report lens.", "analysis-overview-empty"); return article; }
      note(article, number(value.totalN || 0) + " report representations · " + number(value.eligibleN || 0) + " with both fields · " + number(value.unknownN || 0) + " missing fields", "analysis-overview-coverage");
      if (!Number(value.totalN)) { note(article, "No positive indexed reports in this lens for the current filters. Missing evidence is not a negative encounter finding.", "analysis-overview-empty"); return article; }
      const axes = selectedAxes(card, value);
      if (!axes.rows.length || !axes.columns.length) { note(article, "No cross-tabulated categories are available for these reports.", "analysis-overview-empty"); article.appendChild(exactTable(card, value)); return article; }
      const profile = card.kind === "profiles" || card.key === "craft_country" || /geograph|region.*craft/.test(card.key);
      article.appendChild(profile && !card.multiLabel ? profiles(card, value, axes) : matrix(card, value, axes));
      if (axes.lensFallback) note(article, "This lens contains categories outside the all-report leading labels; its own leading labels are shown.", "analysis-overview-cap-note");
      if (axes.rows.length < axes.allRows.length || axes.columns.length < axes.allColumns.length) note(article,
        "Showing " + axes.rows.length + " of " + axes.allRows.length + " row labels and " + axes.columns.length + " of " + axes.allColumns.length + " column labels. " + (axes.lensFallback ? "Leading categories use this report lens;" : "Leading categories use the all-report lens;") + " missing labels stay visible. All nonzero cells are in the exact table.", "analysis-overview-cap-note");
      if (card.multiLabel) note(article, "Being labels may overlap within a report. These are reported descriptions, not independent encounters or proof of craft association.", "analysis-overview-multilabel");
      const contrast = highlights(card, value); if (contrast) article.appendChild(contrast);
      article.appendChild(exactTable(card, value)); return article;
    }
    function contextStrip(model, result) {
      const aside = node("aside", "analysis-overview-context"), heading = node("div");
      heading.append(node("h3", "", "Add another context"), node("p", "analysis-overview-note", "Open a topic for its own population, evidence coverage and comparison controls.")); aside.appendChild(heading);
      const items = Array.isArray(model.contexts) ? model.contexts : [
        { section: "crops", label: "Crop circles", detail: "Independent crop-circle catalog" },
        { section: "animals", label: "Animal reports", detail: "Independent animal-report catalog" },
        { section: "comparisons", label: "Moon, planets & nuclear", detail: "Additional context loads when opened" },
        { section: "facilities", label: "Facilities & spatial evidence", detail: "Reviewed locations and qualified neighbors" }
      ];
      const links = node("div", "analysis-overview-context-links");
      items.forEach(item => {
        const link = button("", () => typeof config.onOpenSection === "function" && config.onOpenSection(item.section, { source: "overview-context" }), "analysis-overview-context-link");
        link.append(node("strong", "", item.label), node("span", "", item.detail || item.reason || (item.available === false ? "Not loaded; open topic" : "Open context analysis")), node("b", "", "→")); links.appendChild(link);
      }); aside.appendChild(links); return aside;
    }
    function render(input) {
      if (destroyed) return;
      lastInput = input;
      const focus = focusedControl();
      const model = input?.model || input?.result?.overviewDashboard || input?.result?.overview?.dashboard || input?.result;
      if (!model || model.status === "loading") { state("Cross-tabulating the current report population. The map remains available.", true); return; }
      if (model.status === "error" || model.status === "unavailable") { state(model.reason || "This overview is not available. The original Analysis topics remain available in the navigation."); return; }
      current = model;
      const lanes = model.lanes || [];
      if (!lanes.some(value => value.key === lane && value.available !== false)) lane = "all";
      let clearedHighlight = null;
      if (craftFocus && !(model.cards || []).some(card => {
        const axes = dimensions(card.lanes?.[lane], card);
        return card.columnDimension === "craft" && axes.columns.some(item => item.key === craftFocus && item.totalN > 0) || card.rowDimension === "craft" && axes.rows.some(item => item.key === craftFocus && item.totalN > 0);
      })) { clearedHighlight = (typeof visuals?.craftLabel === "function" ? visuals.craftLabel(craftFocus) : CRAFT_LABELS[craftFocus]) || craftFocus; craftFocus = null; }
      const root = node("div", "analysis-overview-dashboard"); root.setAttribute("data-lane", lane);
      const header = node("div", "analysis-overview-heading"), copy = node("div");
      copy.append(node("p", "analysis-overview-eyebrow", "PATTERNS AT A GLANCE"), node("h2", "", "Explore the current reports"));
      note(copy, "See time, place, craft and encounters together. Choose a report lens, then open any pattern to investigate it."); header.appendChild(copy);
      const controls = node("div", "analysis-overview-controls"), lensLabel = node("label", "analysis-overview-lens", "Report lens"), select = node("select"); select.setAttribute("aria-label", "Overview report lens");
      lanes.forEach(value => { const option = node("option", "", value.label + " · " + (value.available === false ? "Index unavailable" : number(value.totalN))); option.value = value.key; option.disabled = value.available === false; select.appendChild(option); }); select.value = lane;
      select.addEventListener("change", () => { lane = select.value; render(input); const focus = target.querySelector?.(".analysis-overview-lens select"); if (focus?.focus) focus.focus(); }); lensLabel.appendChild(select); controls.appendChild(lensLabel);
      const display = node("div", "analysis-overview-display"); display.setAttribute("role", "group"); display.setAttribute("aria-label", "Overview heatmap colors");
      [["share", "Row share"], ["count", "Report count"], ["difference", "Difference"]].forEach(([key, label]) => {
        const el = button(label, () => { mode = key; render(input); const focus = target.querySelector?.('[data-overview-display="' + key + '"]'); if (focus?.focus) focus.focus(); }); el.setAttribute("aria-pressed", String(mode === key)); el.setAttribute("data-overview-display", key);
        if (key === "difference" && !differenceReady) { el.disabled = true; el.title = "Difference calculations are unavailable; row shares and exact counts remain available."; }
        display.appendChild(el);
      }); controls.appendChild(display); header.appendChild(controls); root.appendChild(header);
      if (mode === "difference") note(root, "Difference = row share − this report lens's category share, in percentage points (pp). The pooled baseline includes this row and all retained categories. Color clips at ±50 pp; displayed values are not clipped. Descriptive, without a significance test.", "analysis-overview-difference-note");
      if (craftFocus) {
        const focusStrip = node("div", "analysis-overview-craft-selection"); setStyle(focusStrip, "--overview-category", craftColor(craftFocus));
        const label = (typeof visuals?.craftLabel === "function" ? visuals.craftLabel(craftFocus) : CRAFT_LABELS[craftFocus]) || craftFocus;
        focusStrip.append(node("i", "analysis-overview-craft-dot"), node("span", "", "Highlighted craft: " + label + " · visual emphasis only; report populations unchanged"));
        const clear = button("Clear highlight", () => { craftFocus = null; render(input); }, "analysis-overview-clear-craft"); clear.setAttribute("data-overview-clear-focus", "true"); focusStrip.appendChild(clear); root.appendChild(focusStrip);
      }
      if (clearedHighlight) { const message = node("p", "analysis-overview-note analysis-overview-focus-cleared", "Highlight cleared: " + clearedHighlight + " is not indexed in this report lens."); message.setAttribute("role", "status"); root.appendChild(message); }
      const activeLane = lanes.find(value => value.key === lane) || { totalN: model.totalN, label: "All reports" };
      const ribbon = node("div", "analysis-overview-population"); ribbon.append(node("strong", "", number(activeLane.totalN) + " " + (activeLane.label || "reports")), node("span", "", "Descriptive report patterns · no causal inference")); root.appendChild(ribbon);
      if (model.coverage && lane === "all" && model.totalN > 0) {
        const coverage = model.coverage;
        const tracks = node("div", "analysis-overview-field-coverage"); tracks.setAttribute("aria-label", "Indexed field coverage in all current reports");
        [["Craft", coverage.knownCraftN], ["Country", coverage.knownCountryN], ["Decade", coverage.knownDecadeN]].filter(([, n]) => Number.isFinite(n)).forEach(([label, n]) => {
          const field = node("div", "analysis-overview-field"), track = node("span", "analysis-overview-field-track"), fill = node("i");
          field.title = label + ": " + number(n) + " of " + number(model.totalN) + " report representations indexed";
          field.setAttribute("aria-label", field.title + ", " + percent(n / model.totalN));
          track.setAttribute("aria-hidden", "true"); setStyle(fill, "width", Math.max(0, Math.min(100, 100 * n / model.totalN)) + "%"); track.appendChild(fill);
          field.append(node("span", "", label), track, node("b", "", percent(n / model.totalN))); tracks.appendChild(field);
        }); root.appendChild(tracks);
      }
      if (activeLane.evidenceUnavailableN > 0) note(root, number(activeLane.evidenceUnavailableN) + " reports have unavailable encounter indexing; they cannot be classified as either positive or negative.");
      if (!model.totalN) { note(root, "No reports match the current Analysis filters. Widen the dates or adjust the filters to begin exploring.", "analysis-overview-empty"); commit(root, focus); return; }
      const cards = Array.isArray(model.cards) ? model.cards : [], primaryKeys = ["craft_decade", "being_craft", "craft_country", "month_decade"];
      const primary = primaryKeys.map(key => cards.find(card => card.key === key)).filter(Boolean);
      if (!primary.length) primary.push(...cards.slice(0, 4));
      const further = cards.filter(card => !primary.includes(card));
      const grid = node("div", "analysis-overview-grid"); primary.forEach(card => grid.appendChild(renderCard(card, card.key === "craft_decade" || card.key === "month_decade"))); root.appendChild(grid);
      if (further.length) {
        const more = node("details", "analysis-overview-more"), summary = node("summary", "", "More patterns · seasonality & source mix"); more.open = openCards.has("more"); more.appendChild(summary);
        const extras = node("div", "analysis-overview-grid analysis-overview-extra-grid"); further.forEach(card => extras.appendChild(renderCard(card, false))); more.appendChild(extras);
        more.addEventListener("toggle", () => more.open ? openCards.add("more") : openCards.delete("more")); root.appendChild(more);
      }
      root.appendChild(contextStrip(model, input?.result));
      note(root, "Counts describe catalog report representations, not independent incidents. Unknown fields, overlapping being labels and uneven reporting coverage can shape these patterns.", "analysis-overview-caveat");
      commit(root, focus);
    }
    return { render, destroy() { destroyed = true; current = null; lastInput = null; target.replaceChildren(); }, getState() { return { lane, mode, craftFocus }; } };
  }
  return Object.freeze({ create });
});
