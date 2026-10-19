(function (root, factory) {
  "use strict";
  let model = root && root.UfoAnalysisReadinessModel;
  if (typeof module === "object" && module.exports) { try { model = require("./analysis_readiness_model.js"); } catch (_) {} }
  const api = factory(model);
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoAnalysisReadinessView = api;
})(typeof self !== "undefined" ? self : globalThis, function (Model) {
  "use strict";
  const number = value => typeof value === "number" && Number.isFinite(value) ? value.toLocaleString() : "Not available";
  const text = value => value == null || value === "" ? "Not available" : String(value);
  const labels = { ready_inferential: "Qualified inputs", ready_sensitivity: "Sensitivity use", ready_descriptive: "Descriptive use", limited: "Limited", blocked: "Blocked", not_applicable: "Not applicable", not_evaluated: "Not assessed", data_unavailable: "Unavailable" };
  const icons = { ready_inferential: "✓", ready_sensitivity: "≈", ready_descriptive: "◇", limited: "!", blocked: "×", not_applicable: "—", not_evaluated: "?", data_unavailable: "…" };
  const meanings = { ready_inferential: "Qualified evidence inputs are available under the stated policy. This does not establish an association or imply every statistical test can run.", ready_sensitivity: "This lane supports sensitivity checks within its stated limits.", ready_descriptive: "Descriptive inventory use is available. This status does not permit an inferential claim.", limited: "Use is limited by the stated evidence requirements.", blocked: "The defined evidence requirements or policy do not support this output.", not_applicable: "This requirement does not apply to this lane.", not_evaluated: "No evaluated result is supplied. This is different from a failed test.", data_unavailable: "A result is not available in this release; missing is not zero." };
  let nextId = 0;
  function create(target, configuration) {
    if (!target?.ownerDocument) throw new Error("An evidence readiness target is required.");
    const doc = target.ownerDocument, config = configuration || {}, id = "analysis-readiness-" + (++nextId);
    let destroyed = false, lastInput = null, currentModel = null, groupKey = null, laneKey = null;
    const openDetails = new Set();
    function node(tag, cls, value) { const el = doc.createElement(tag); if (cls) el.className = cls; if (value != null) el.textContent = String(value); return el; }
    function setStyle(el, key, value) { if (el.style?.setProperty) el.style.setProperty(key, value); else el.style[key] = value; }
    function note(parent, value, cls) { if (value) parent.appendChild(node("p", "analysis-readiness-note" + (cls ? " " + cls : ""), value)); }
    function button(label, callback, cls) { const el = node("button", cls, label); el.type = "button"; el.addEventListener("click", callback); return el; }
    function badge(status, custom) { const mark = node("span", "analysis-readiness-badge is-" + (status || "data_unavailable")); mark.append(node("b", "", icons[status] || "?"), node("span", "", custom || labels[status] || "Unavailable")); mark.title = meanings[status] || meanings.data_unavailable; return mark; }
    function allLanes(model) { return (model?.groups || []).flatMap(group => group.lanes || []); }
    function focusedControl() {
      const active = doc.activeElement; let ancestor = active;
      while (ancestor && ancestor !== target) ancestor = ancestor.parentNode;
      if (ancestor !== target || !active?.getAttribute) return null;
      for (const attribute of ["data-readiness-control", "data-readiness-family", "data-readiness-lane"]) { const key = active.getAttribute(attribute); if (key) return { attribute, key }; }
      return null;
    }
    function commit(root, focus) {
      target.replaceChildren(root);
      const control = focus && Array.from(target.querySelectorAll?.("button, select") || []).find(el => el.getAttribute(focus.attribute) === focus.key);
      if (control?.focus) control.focus();
    }
    function select(group, lane) { groupKey = group.key; laneKey = lane.key; render(lastInput); }
    function disclosure(key, label, build, cls) {
      const details = node("details", "analysis-readiness-disclosure" + (cls ? " " + cls : "")); details.open = openDetails.has(key); details.appendChild(node("summary", "", label)); let built = false;
      function ensure() { if (!built) { built = true; build(details); } }
      details.addEventListener("toggle", () => { if (details.open) { openDetails.add(key); ensure(); } else openDetails.delete(key); });
      if (details.open) ensure(); return details;
    }
    function countsLine(gate) {
      const counts = gate?.cell?.counts || gate?.counts || {};
      const fields = [["Recorded passed", counts.passed, gate.numeratorUnit], ["Input", counts.input, gate.denominatorUnit], ["Failed", counts.failed], ["Unknown", counts.unknown]].filter(([, n]) => typeof n === "number" && Number.isFinite(n));
      return fields.length ? fields.map(([label, n, unit]) => label + " " + number(n) + (unit ? " " + unit : "")).join(" · ") : "Counts not supplied";
    }
    function gateStatus(gate) { return gate?.status || gate?.cell?.status || "data_unavailable"; }
    function gateLabel(gate) { return gate?.label || (gate?.key ? String(gate.key).replace(/_/g, " ").replace(/^./, value => value.toUpperCase()) : "Evidence check"); }
    function gateReason(gate) { return gate?.action?.reason || gate?.cell?.reason || gate?.reason || (typeof gate?.action === "string" ? gate.action : "") || "The release supplies no further explanation for this check."; }
    function drawRetention(parent, retention, status, label) {
      if (retention?.status !== "ready" || !Number.isFinite(retention.share) || retention.share < 0 || retention.share > 1) return false;
      const bar = node("div", "analysis-readiness-retention is-" + status), track = node("span", "analysis-readiness-retention-track"), fill = node("i");
      setStyle(fill, "width", (100 * retention.share) + "%"); track.appendChild(fill); track.setAttribute("aria-hidden", "true");
      bar.setAttribute("aria-label", label + ": " + number(retention.numerator) + " recorded passed of " + number(retention.denominator) + " gate inputs. Status: " + (labels[status] || status) + ". This ratio is not a readiness score.");
      bar.append(track, node("span", "analysis-readiness-retention-count", number(retention.numerator) + " / " + number(retention.denominator))); parent.appendChild(bar); return true;
    }
    function scopeHeader(root, model, input) {
      const scope = model.scope || input.scope || {}, panel = node("div", "analysis-readiness-scope");
      panel.appendChild(node("strong", "", scope.label || "Evidence inventory scope"));
      note(panel, scope.kind === "release_inventory" ? "These counts describe the released evidence inventory. They do not change with the date controls above." : scope.description || "Each analysis lane keeps its own stated inventory and eligibility counts.");
      if (scope.kind === "release_inventory") {
        const active = [];
        if (Number.isFinite(scope.activeQueryReports)) active.push(number(scope.activeQueryReports) + " reports in the current filters");
        if (Number.isFinite(scope.activeQualifiedEndpoints)) active.push(number(scope.activeQualifiedEndpoints) + " qualified endpoints in that query");
        if (active.length) note(panel, "Separate active-query support: " + active.join(" · ") + ". These are different denominators.", "analysis-readiness-active-support");
      } root.appendChild(panel);
    }
    function summary(root, model) {
      const header = node("div", "analysis-readiness-heading"); header.append(node("h3", "", "What can this evidence support?"), node("p", "analysis-readiness-note", "Choose a lane to see its usable output, failed checks and missing tests.")); root.appendChild(header);
      const row = node("div", "analysis-readiness-status-summary"); row.setAttribute("aria-label", "Output status counts by analysis lane");
      Object.keys(labels).forEach(status => {
        const n = model.statusCounts?.[status]; if (!Number.isFinite(n) || n <= 0) return;
        const noun = n === 1 ? "lane" : "lanes", descriptions = { ready_inferential: noun + " with qualified inputs", ready_sensitivity: "sensitivity " + noun,
          ready_descriptive: "descriptive " + noun, limited: "limited " + noun, blocked: "blocked " + noun, not_applicable: noun + " marked not applicable", not_evaluated: "unassessed " + noun, data_unavailable: noun + " with unavailable results" };
        row.appendChild(badge(status, number(n) + " " + descriptions[status]));
      });
      root.appendChild(row); note(root, number(model.laneN) + " analysis lanes · counts summarize permitted uses, not a quality score or number of independent incidents.", "analysis-readiness-lane-count");
    }
    function picker(model, group, lane) {
      const nav = node("div", "analysis-readiness-navigation"), mobile = node("div", "analysis-readiness-mobile-pickers");
      [["family", "Evidence family", model.groups, group.key], ["lane", "Analysis lane", group.lanes, lane.key]].forEach(([kind, label, values, selected]) => {
        const wrapper = node("label", "", label), control = node("select"); control.setAttribute("aria-label", label); control.setAttribute("data-readiness-control", kind);
        values.forEach(value => { const option = node("option", "", value.label); option.value = value.key; control.appendChild(option); }); control.value = selected;
        control.addEventListener("change", () => { if (kind === "family") { const next = model.groups.find(value => value.key === control.value); if (next?.lanes?.length) select(next, next.lanes[0]); } else { const next = group.lanes.find(value => value.key === control.value); if (next) select(group, next); } });
        wrapper.appendChild(control); mobile.appendChild(wrapper);
      }); nav.appendChild(mobile);
      const desktop = node("div", "analysis-readiness-desktop-pickers"), families = node("div", "analysis-readiness-families");
      families.setAttribute("role", "group"); families.setAttribute("aria-label", "Evidence family");
      model.groups.forEach(value => { const item = button("", () => select(value, value.lanes[0]), "analysis-readiness-family"); item.setAttribute("aria-pressed", String(value.key === group.key)); item.setAttribute("data-readiness-family", value.key);
        item.append(node("strong", "", value.label), node("span", "", number(value.lanes.length) + (value.lanes.length === 1 ? " lane" : " lanes"))); families.appendChild(item); }); desktop.appendChild(families);
      const lanePicker = node("div", "analysis-readiness-lanes"); lanePicker.setAttribute("role", "tablist"); lanePicker.setAttribute("aria-label", group.label + " analysis lanes"); lanePicker.setAttribute("aria-orientation", "vertical");
      const laneButtons = group.lanes.map(value => {
        const item = button("", () => select(group, value), "analysis-readiness-lane"); item.setAttribute("role", "tab"); item.setAttribute("aria-selected", String(value.key === lane.key)); item.setAttribute("aria-controls", id + "-detail"); item.setAttribute("data-readiness-lane", value.key); item.tabIndex = value.key === lane.key ? 0 : -1;
        item.append(node("strong", "", value.label), badge(value.status)); lanePicker.appendChild(item); return item;
      });
      laneButtons.forEach((item, index) => item.addEventListener("keydown", event => { let next;
        if (event.key === "ArrowDown") next = (index + 1) % laneButtons.length;
        else if (event.key === "ArrowUp") next = (index - 1 + laneButtons.length) % laneButtons.length;
        else if (event.key === "Home") next = 0; else if (event.key === "End") next = laneButtons.length - 1;
        if (next != null) { event.preventDefault(); groupKey = group.key; laneKey = group.lanes[next].key; render(lastInput); const control = Array.from(target.querySelectorAll?.("button") || []).find(el => el.getAttribute("data-readiness-lane") === laneKey); control?.focus?.(); }
      })); desktop.appendChild(lanePicker); nav.appendChild(desktop); return nav;
    }
    function issueList(parent, title, gates, kind, empty) {
      const section = node("section", "analysis-readiness-issues is-" + kind); section.appendChild(node("h5", "", title + (gates.length ? " · " + number(gates.length) : "")));
      if (!gates.length) { note(section, empty); parent.appendChild(section); return; }
      const list = node("ul"); gates.slice(0, 3).forEach(gate => { const item = node("li"), heading = node("div", "analysis-readiness-issue-heading"); heading.append(node("strong", "", gateLabel(gate)), badge(gateStatus(gate), kind === "undefined" ? "No separate result" : null)); item.append(heading, node("p", "", gateReason(gate))); list.appendChild(item); }); section.appendChild(list);
      if (kind === "undefined") note(section, "Some requirements may be evaluated together in the joint checks; an absent separate result is not a failed check.");
      if (gates.length > 3) note(section, number(gates.length - 3) + " more are preserved in the full gate details below."); parent.appendChild(section);
    }
    function detailedGates(parent, lane) {
      const gates = lane.detailedGates || [];
      if (!gates.length) note(parent, lane.aggregateSummary ? "This row is an aggregate catalog summary, not an additional typed test." : "No typed detailed tests are supplied for this lane.");
      const list = node("div", "analysis-readiness-gate-details");
      gates.forEach(gate => {
        const item = node("section", "analysis-readiness-gate-detail"), heading = node("div", "analysis-readiness-gate-detail-heading"); heading.append(node("h5", "", gateLabel(gate)), badge(gateStatus(gate))); item.appendChild(heading);
        if (gate.applicableToLane === false) note(item, "Retained context-only check: it does not determine this lane's output status.", "analysis-readiness-context-only");
        note(item, countsLine(gate)); note(item, gate?.cell?.reason || gate.reason || "No reason supplied.");
        const metadata = node("dl", "analysis-readiness-metadata");
        [["Gate", gate.key], ["Applicability", gate.applicability || gate.gate?.applicability], ["Policy", gate.policyId || gate.gate?.policyId || gate.gate?.policy_id], ["Evidence hash", gate.evidenceHash || gate.gate?.evidenceHash || gate.gate?.evidence_hash]].forEach(([label, value]) => { metadata.append(node("dt", "", label), node("dd", "", text(value))); }); item.appendChild(metadata); list.appendChild(item);
        item.appendChild(disclosure(lane.key + ":source:" + gate.key, "Original typed fields", parent => { const source = node("pre", "analysis-readiness-source-fields"); try { source.textContent = JSON.stringify(gate.gate || gate.cell?.gate || {}, null, 2); } catch (_) { source.textContent = "Original fields are unavailable in a serializable form."; } parent.appendChild(source); }));
      }); parent.appendChild(list);
      if (lane.missingDefinitionGates?.length) {
        const missing = node("section", "analysis-readiness-definition-details"); missing.appendChild(node("h5", "", "Dimensions without a separate gate result"));
        lane.missingDefinitionGates.forEach(gate => { const line = node("p", "analysis-readiness-note"); line.append(node("strong", "", gateLabel(gate) + ": "), node("span", "", gateReason(gate))); missing.appendChild(line); }); parent.appendChild(missing);
      }
      const policy = lane.item || {}, metadata = node("dl", "analysis-readiness-metadata");
      [["Lane policy", policy.policyId || policy.policy_id], ["Lane evidence hash", policy.evidenceHash || policy.evidence_hash || policy.releaseHash || policy.release_hash || policy.artifactHash || policy.artifact_hash]].forEach(([label, value]) => { metadata.append(node("dt", "", label), node("dd", "", text(value))); }); parent.appendChild(metadata);
      parent.appendChild(disclosure(lane.key + ":lane-source", "Original lane fields", root => { const source = node("pre", "analysis-readiness-source-fields"); try { source.textContent = JSON.stringify(policy, null, 2); } catch (_) { source.textContent = "Original lane fields are unavailable in a serializable form."; } root.appendChild(source); }));
    }
    function strictMilestones(lane) {
      if (!["cropStrict", "crop_strict", "animalStrict", "animal_strict"].includes(lane.key)) return null;
      const validCount = value => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
      const validShare = value => typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
      const balance = lane.cohortBalance || {}, policy = balance.policy || {}, section = node("section", "analysis-readiness-milestones");
      section.appendChild(node("h5", "", "Strict cluster milestones"));
      let supplied = false;
      [["Strict cluster minimum", lane.eligible, lane.minimumStrictClusters], ["Balanced cohort size", balance.strictUniqueClusters, policy.minimumStrictUniqueClusters]].forEach(([label, observed, required]) => {
        if (!validCount(required) || required === 0) return; supplied = true;
        observed = validCount(observed) ? observed : null;
        const item = node("div", "analysis-readiness-milestone"), heading = node("div", "analysis-readiness-milestone-heading");
        heading.append(node("span", "", label), node("strong", "", number(observed) + " / " + number(required))); item.appendChild(heading);
        if (validCount(observed)) {
          const track = node("span", "analysis-readiness-milestone-track"), fill = node("i"); track.setAttribute("aria-hidden", "true"); setStyle(fill, "width", (100 * Math.min(1, observed / required)) + "%"); track.appendChild(fill); item.appendChild(track);
        }
        item.setAttribute("aria-label", label + ": " + number(observed) + " unique clusters against a typed target of " + number(required) + ". This is a count milestone, not an evidence-readiness score."); section.appendChild(item);
      });
      const facts = node("dl", "analysis-readiness-balance-facts");
      function fact(label, observed, target, targetLabel) {
        if (observed == null) return; supplied = true;
        const item = node("div"); item.append(node("dt", "", label), node("dd", "", observed + (target == null ? "" : " · " + targetLabel + " " + target))); facts.appendChild(item);
      }
      if (balance.sourceFamilyClusterCounts && typeof balance.sourceFamilyClusterCounts === "object" && !Array.isArray(balance.sourceFamilyClusterCounts)) {
        const counts = Object.values(balance.sourceFamilyClusterCounts);
        const actual = counts.every(validCount) ? counts.filter(value => value > 0).length : null;
        fact("Recorded source families", actual == null ? "Not available" : number(actual), validCount(policy.minimumSourceFamilies) ? number(policy.minimumSourceFamilies) : null, "minimum");
      }
      if (Array.isArray(balance.qualifyingMacroregionsAtLeast25)) {
        const matchingPolicy = policy.minimumClustersPerMacroregion === 25;
        fact("Macroregions with ≥25 clusters", number(balance.qualifyingMacroregionsAtLeast25.length), matchingPolicy && validCount(policy.minimumMacroregions) ? number(policy.minimumMacroregions) : null, "minimum");
      }
      const limit = validShare(policy.maximumSourceFamilyOrMacroregionShare) ? (100 * policy.maximumSourceFamilyOrMacroregionShare).toFixed(0) + "%" : null;
      [["Largest source-family share", balance.maximumSourceFamilyShare], ["Largest macroregion share", balance.maximumMacroregionShare]].forEach(([label, share]) => {
        if (!validShare(share)) return;
        fact(label, balance.strictUniqueClusters === 0 ? "Not measurable: 0 clusters" : validCount(balance.strictUniqueClusters) ? (100 * share).toFixed(1) + "%" : "Not available: cluster count missing", limit, "maximum");
      });
      if (facts.children.length) section.appendChild(facts);
      note(section, "Bars show counts against stated policy targets, not overall readiness. Source-family labels can overlap; meeting one count target does not satisfy the other evidence requirements.", "analysis-readiness-milestone-note");
      return supplied ? section : null;
    }
    function inspector(lane) {
      const panel = node("section", "analysis-readiness-inspector"); panel.id = id + "-detail"; panel.setAttribute("role", "tabpanel"); panel.setAttribute("aria-labelledby", id + "-detail-title");
      const header = node("div", "analysis-readiness-inspector-header"), title = node("h4", "", lane.label); title.id = id + "-detail-title"; header.append(title, badge(lane.status)); panel.appendChild(header);
      note(panel, meanings[lane.status] || meanings.data_unavailable, "analysis-readiness-output-meaning");
      const counts = node("div", "analysis-readiness-lane-numbers");
      const metrics = [[lane.aggregateSummary ? "Included in summary" : lane.eligibleLabel || "Eligible for this lane", lane.eligible], [lane.totalLabel || "Source inventory", lane.total]];
      if (Number.isSafeInteger(lane.reconciledRecords) && lane.reconciledRecords >= 0) metrics.push(["Reconciled relationship records", lane.reconciledRecords]);
      metrics.forEach(([label, n]) => { const item = node("div"); item.append(node("span", "", label), node("strong", "", number(n))); counts.appendChild(item); }); panel.appendChild(counts);
      if (lane.retention?.status === "ready") drawRetention(panel, lane.retention, lane.status, "Lane eligibility recorded in the release");
      (lane.notes || []).forEach(value => note(panel, value, "analysis-readiness-lane-policy"));
      const milestones = strictMilestones(lane); if (milestones) panel.appendChild(milestones);
      const reasons = Array.from(new Set(lane.reasons || []));
      if (reasons.length) {
        if (lane.actualBlockedGates?.length) panel.appendChild(disclosure(lane.key + ":release-notes", "Additional release notes · " + number(reasons.length), parent => note(parent, reasons.join(" · "), "analysis-readiness-lane-reasons"), "analysis-readiness-release-notes"));
        else note(panel, reasons.join(" · "), "analysis-readiness-lane-reasons");
      }
      const blockers = lane.actualBlockedGates || [], unassessed = [...(lane.unassessedGates || []), ...(lane.unavailableGates || [])], missing = lane.missingDefinitionGates || [];
      if (blockers.length || lane.status === "blocked") issueList(panel, "Failed defined checks", blockers, "blocked", "The output is blocked, but this matrix supplies no failing typed test to diagnose.");
      else { const clear = node("p", "analysis-readiness-no-blockers"); clear.append(node("b", "", "✓"), node("span", "", "No recorded blocking checks for this lane")); panel.appendChild(clear); }
      if (unassessed.length || missing.length) {
        panel.appendChild(disclosure(lane.key + ":assessments", "Other assessment details · " + number(unassessed.length + missing.length), parent => {
          const gaps = node("div", "analysis-readiness-gaps");
          if (unassessed.length) issueList(gaps, "Checks without an available result", unassessed, "unassessed", "");
          if (missing.length && !lane.aggregateSummary) issueList(gaps, "No separate gate result", missing, "undefined", "");
          parent.appendChild(gaps);
        }, "analysis-readiness-assessment-disclosure"));
      }
      const counted = (lane.applicableGates || lane.detailedGates || []).filter(gate => gate.retention?.status === "ready" && gate.applicableToLane !== false);
      if (counted.length) {
        const visual = node("section", "analysis-readiness-gate-retentions"); visual.appendChild(node("h5", "", "What each recorded check retains"));
        note(visual, "Separate gate counts, each with its own input denominator. These are not a sequential funnel or a readiness percentage.");
        const ordered = counted.slice().sort((a, b) => Number(gateStatus(b) === "blocked") - Number(gateStatus(a) === "blocked"));
        ordered.slice(0, 4).forEach(gate => { const row = node("div", "analysis-readiness-gate-retention"); row.append(node("span", "", gateLabel(gate)), badge(gateStatus(gate))); drawRetention(row, gate.retention, gateStatus(gate), gateLabel(gate)); visual.appendChild(row); }); panel.appendChild(visual);
      }
      const gateN = (lane.detailedGates || []).length;
      panel.appendChild(disclosure(lane.key + ":gates", "All typed checks, policies & hashes" + (gateN ? " · " + number(gateN) : ""), parent => detailedGates(parent, lane), "analysis-readiness-all-gates"));
      if (typeof config.onOpenSection === "function" && lane.section) { const open = button("Open related analysis →", () => config.onOpenSection(lane.section, { source: "readiness-inspector", lane: lane.key }), "analysis-readiness-open-section"); panel.appendChild(open); }
      return panel;
    }
    function rawMatrix(parent, matrix) {
      const scroll = node("div", "analysis-readiness-original-scroll"), table = node("table", "analysis-readiness-original");
      table.appendChild(node("caption", "", "Gate matrix by analysis lane · joint checks can appear in several columns; those cells are not independent coverage counts"));
      const head = node("thead"), top = node("tr"); top.appendChild(node("th", "", "Domain / lane")); (matrix.columns || []).forEach(column => top.appendChild(node("th", "", column.label || column.key))); head.appendChild(top); table.appendChild(head);
      const body = node("tbody"); (matrix.rows || []).forEach(row => { const tr = node("tr"), heading = node("th", "", row.label); heading.scope = "row";
        heading.appendChild(node("small", "", "Eligible " + number(row.eligible) + " · inventory " + number(row.total))); tr.appendChild(heading);
        (row.cells || []).forEach(cell => { const td = node("td"); td.append(badge(cell.status, cell.value || labels[cell.status]), node("small", "", cell.reason || "")); tr.appendChild(td); }); body.appendChild(tr);
      }); table.appendChild(body); scroll.appendChild(table); parent.appendChild(scroll);
      note(parent, "The matrix shows representative checks under each lane's applicability rules. Some requirements may be evaluated together in the joint checks; an absent separate result is not a failed check. All source gate fields are retained in each lane's details.");
    }
    function render(input) {
      if (destroyed) return;
      lastInput = input; const focus = focusedControl(), matrix = input?.matrix;
      if (!matrix || matrix.status === "loading") { const status = node("div", "analysis-readiness-loading", "Loading evidence requirements…"); status.setAttribute("role", "status"); commit(status, focus); return; }
      if (!matrix.rows?.length) { const empty = node("div", "analysis-readiness-empty"); empty.appendChild(node("strong", "", "Evidence requirements are not available for this view.")); note(empty, "No missing requirement is counted as a failed test or zero observations."); commit(empty, focus); return; }
      const root = node("div", "analysis-readiness-workspace");
      if (!Model?.compute) { note(root, "The evidence summary is unavailable. The full gate matrix remains available below."); root.appendChild(disclosure("original", "Full gate matrix", parent => rawMatrix(parent, matrix))); commit(root, focus); return; }
      currentModel = Model.compute(matrix, { scope: input.scope });
      const groups = (currentModel.groups || []).filter(group => group.lanes?.length);
      if (!groups.length) { note(root, "No analysis lanes are supplied in this release."); commit(root, focus); return; }
      const group = groups.find(group => group.key === groupKey) || groups[0], lane = group.lanes.find(lane => lane.key === laneKey) || group.lanes[0];
      groupKey = group.key; laneKey = lane.key;
      summary(root, currentModel); scopeHeader(root, currentModel, input);
      const work = node("div", "analysis-readiness-body"); work.append(picker(currentModel, group, lane), inspector(lane)); root.appendChild(work);
      root.appendChild(disclosure("original", "Full gate matrix · " + number(currentModel.laneN) + " lanes", parent => rawMatrix(parent, matrix), "analysis-readiness-original-disclosure"));
      note(root, "A defined check can fail; an absent separate gate result is not a failed check. Qualified inputs and large counts do not establish an association, independence or causation.", "analysis-readiness-footer"); commit(root, focus);
    }
    return { render, destroy() { destroyed = true; lastInput = null; currentModel = null; target.replaceChildren(); }, getState() { return { groupKey, laneKey }; } };
  }
  return Object.freeze({ create });
});
