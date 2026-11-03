(function (root) {
  "use strict";

  const svgNamespace = "http://www.w3.org/2000/svg";

  function render(document, diagram, sourceLink) {
    function html(tag, className, text) {
      const node = document.createElement(tag);
      if (className) node.className = className;
      if (text) node.textContent = text;
      return node;
    }

    function svg(tag, attributes) {
      const node = document.createElementNS(svgNamespace, tag);
      for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
      return node;
    }

    const panel = html("section", "landing-diagram");
    panel.append(html("h5", "", "Site diagram"));
    if (!diagram) {
      panel.append(html("p", "landing-trace-context", "The reviewed records give too little spatial detail for a site diagram."));
      return panel;
    }

    const controls = html("fieldset", "landing-diagram-controls");
    controls.append(html("legend", "", "Trace layers"));
    const graphic = svg("svg", { viewBox: diagram.viewBox.join(" "), role: "img", "aria-label": diagram.title });
    const description = svg("desc", {});
    graphic.append(description);
    const notes = html("ul", "landing-diagram-notes");
    const empty = html("p", "landing-diagram-empty", "Select a trace layer to see its marks.");
    empty.hidden = true;
    const markerSize = Math.min(diagram.viewBox[2], diagram.viewBox[3]) * 0.025;
    const layers = [];

    for (const layer of diagram.layers) {
      const control = html("label", "landing-diagram-layer");
      const toggle = html("input");
      toggle.type = "checkbox";
      toggle.checked = true;
      const symbol = html("span", "landing-diagram-swatch");
      symbol.setAttribute("aria-hidden", "true");
      control.dataset.traceKind = layer.kind;
      if (layer.channel) control.dataset.traceChannel = layer.channel;
      control.append(toggle, symbol, document.createTextNode(layer.label));
      controls.append(control);

      const group = svg("g", { "data-trace-kind": layer.kind });
      if (layer.channel) group.setAttribute("data-trace-channel", layer.channel);
      for (const mark of layer.marks) {
        let shape;
        if (mark.type === "ellipse") {
          shape = svg("ellipse", { cx: mark.x, cy: mark.y, rx: mark.rx, ry: mark.ry });
        } else if (mark.type === "path") {
          shape = svg("path", { d: mark.d });
        } else {
          const { x, y } = mark;
          const size = markerSize;
          if (layer.kind === "impression") {
            shape = svg("rect", { x: x - size, y: y - size, width: 2 * size, height: 2 * size });
          } else if (layer.kind === "scorching") {
            shape = svg("path", { d: "M " + x + " " + (y - size) + " l " + size + " " + size +
              " l " + (-size) + " " + size + " l " + (-size) + " " + (-size) + " Z" });
          } else {
            shape = svg("circle", { cx: x, cy: y, r: size });
          }
        }
        shape.classList.add(mark.type === "point" ? "landing-diagram-point" : "landing-diagram-outline");
        if (mark.estimated) shape.classList.add("landing-diagram-estimated");
        const title = svg("title", {});
        title.textContent = mark.label;
        shape.append(title);
        group.append(shape);
        if (mark.type === "point" && mark.tag) {
          const tag = svg("text", { x: mark.x + markerSize * 1.45, y: mark.y + markerSize / 2,
            "font-size": markerSize * 1.9, class: "landing-diagram-tag", "aria-hidden": "true" });
          tag.textContent = mark.tag;
          group.append(tag);
        }
      }
      graphic.append(group);

      const note = html("li", "landing-diagram-layer-note");
      note.dataset.traceKind = layer.kind;
      if (layer.channel) note.dataset.traceChannel = layer.channel;
      note.append(html("strong", "", layer.label), html("p", "", layer.note));
      const refs = html("div", "landing-diagram-references");
      for (const id of layer.sourceIds) {
        const link = sourceLink(id);
        if (link) refs.append(link);
      }
      note.append(refs);
      notes.append(note);
      layers.push({ layer, toggle, group, note });
      toggle.addEventListener("change", sync);
    }

    function sync() {
      const descriptions = [];
      for (const { layer, toggle, group, note } of layers) {
        group.setAttribute("display", toggle.checked ? "inline" : "none");
        note.hidden = !toggle.checked;
        if (toggle.checked) descriptions.push(layer.label + ". " +
          layer.marks.map((mark) => mark.label).join(". ") + ". " + layer.note);
      }
      const anyVisible = descriptions.length > 0;
      empty.hidden = anyVisible;
      graphic.setAttribute("aria-hidden", String(!anyVisible));
      description.textContent = descriptions.join(" ");
    }

    const figure = html("figure", "landing-diagram-figure");
    const plot = html("div", "landing-diagram-plot");
    plot.append(graphic, empty);
    const caption = html("figcaption", "landing-diagram-caption");
    caption.append(html("strong", "", diagram.basis), html("p", "", diagram.note));
    figure.append(plot, caption);
    panel.append(controls, figure, notes);
    sync();
    return panel;
  }

  root.UfoLandingSiteDiagrams = { render };
})(globalThis);
