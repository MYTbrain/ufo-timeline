(function (root, factory) {
  "use strict";

  const cases = factory();
  if (typeof module === "object" && module && module.exports) module.exports = cases;
  root.UfoLandingSiteAustralianReviewedCases = cases;
})(globalThis, function () {
  "use strict";

  const catalogUrl = "https://www.project1947.com/kbcat/kbtrace0505.htm";
  const aproUrl = "https://noufors.com/Documents/Books%2C%20Manuals%20and%20Published%20Papers/Specialty%20UFO%20Publications/A.P.R.O.%20Bulletin/";
  const sketchUrl = "https://oldcropcircles.weebly.com/uploads/6/8/2/6/6826365/";

  function source(id, label, url, locator) {
    return { id, label, url, locator };
  }

  function site(row, evidenceOrigin, record) {
    return {
      ...record,
      inventoryIds: ["basterfield:" + row],
      evidenceOrigin,
      sources: [...(record.sources || []),
        source("basterfield", "Keith Basterfield, Australian physical trace catalog", catalogUrl,
          "May 2005 edition, " + record.title + ", inventory entry " + row + ".")]
    };
  }

  function pattern(label, families, basis, details, measurements = {}) {
    return { label, families, basis, details, ...measurements };
  }

  function trace(kind, observation, sourceIds, geometry) {
    return { kind, observation, sourceIds, ...(geometry ? { pattern: geometry } : {}) };
  }

  function ellipse(x, y, rx, ry, label) {
    return { type: "ellipse", x, y, rx, ry, label, estimated: true };
  }

  function ring(radius, label) {
    return ellipse(0, 0, radius, radius, label);
  }

  function point(x, y, label, tag) {
    return { type: "point", x, y, label, ...(tag ? { tag } : {}), estimated: true };
  }

  function path(d, label) {
    return { type: "path", d, label, estimated: true };
  }

  function layer(kind, label, note, sourceIds, marks) {
    return { kind, label, note, sourceIds, marks };
  }

  return [
    site(26, "catalog", {
      id: "afterlea",
      title: "Afterlea",
      date: "1969-02-22",
      location: "Afterlea, New South Wales, Australia",
      summary: "A resident found an oval patch of flattened, entangled reeds in a swamp. Four flattened tracks reportedly led out to smaller soil depressions.",
      limits: "The compiler cites the February 27 Northern Star. The reviewed description gives the oval's dimensions but leaves the locations and lengths of its four tracks open.",
      traces: [
        trace("deformation", "The patch was roughly 9 × 3.6 m, with four tracks leading outward. The entry reports no scorching.", ["basterfield"],
          pattern("Elongated reed patch with outward tracks", ["oval", "radial"], "dimensions",
            "The two reported spans characterize the main patch. Track angles are unknown.", { dimensions: { longM: 9, shortM: 3.6 } })),
        trace("impression", "Small half-moon depressions were reported at the ends of the flattened tracks.", ["basterfield"])
      ],
      diagram: {
        title: "Afterlea outline of the flattened reed patch",
        viewBox: [-5.7, -3.2, 11.4, 6.4],
        basis: "Approximate envelope from two reported spans",
        note: "The 9 × 3.6 m oval is schematic. The four tracks and small depressions lack positions.",
        layers: [layer("deformation", "Flattened reed patch", "The outline uses the compiler's quoted dimensions.",
          ["basterfield"], [ellipse(0, 0, 4.5, 1.8, "Approximate flattened reed envelope")])]
      }
    }),
    site(27, "catalog", {
      id: "grafton_leaf_smut",
      title: "Grafton leaf smut",
      date: "1969-02-22",
      location: "Grafton, New South Wales, Australia",
      summary: "A reported burn-like circle was found the morning after a sighting. The catalog attributes a later sample identification to the Department of Agriculture.",
      limits: "The compiler gives no surveyed dimensions or detailed sample report. The diagnosis is attributed rather than independently checked.",
      controls: "The catalog records the identification of leaf smut, an ordinary cause that can give grass a burn-like appearance.",
      traces: [
        trace("surface", "The grass was described as ash-covered and burned before agricultural examination indicated leaf smut.", ["basterfield"],
          pattern("Reported burn-like circle", ["ring"], "description", "The reported appearance and later biological diagnosis refer to the same patch."))
      ]
    }),
    site(30, "catalog", {
      id: "christies_beach",
      title: "Christies Beach",
      date: "1969-03-10",
      location: "Christies Beach, South Australia, Australia",
      summary: "A resident reported a loud bang during the night. Three small circular marks were later reported in an equilateral layout.",
      limits: "The catalog attributes the measurements to UFORSA and gives no mark depths, field survey or witnessed object. The mechanism that made the marks is open.",
      traces: [
        trace("surface", "Three reported circles were 22 cm across, with 12.67 m between their centers.", ["basterfield"],
          pattern("Reported equilateral three-point layout", ["three_point"], "dimensions",
            "The catalog supplies equal side lengths but gives no uncertainty or individual bearing measurements.", { edgesM: [12.67, 12.67, 12.67] }))
      ],
      diagram: {
        title: "Christies Beach reported three-mark layout",
        viewBox: [-8, -2, 16, 15],
        basis: "Schematic from reported equal spacing",
        note: "The triangle represents the reported relation between centers. It does not establish exact symmetry at survey precision.",
        layers: [layer("surface", "Three circular marks", "Symbols show reported positions relative to each other and exaggerate mark size for legibility.",
          ["basterfield"], [path("M -6.335 0 H 6.335 L 0 10.973 Z", "Reported triangular layout"),
            point(-6.335, 0, "Reported mark 1"), point(6.335, 0, "Reported mark 2"), point(0, 10.973, "Reported mark 3")])]
      }
    }),
    site(50, "original", {
      id: "tooligie_hill",
      title: "Tooligie Hill",
      date: "1971-12",
      location: "Tooligie Hill, South Australia, Australia",
      summary: "The Habners found a layered wheat and soil formation in their field. A field sketch records concentric bands and counterclockwise wheat lay.",
      limits: "The police commissioner reported no witnessed object at the site and noted new growth from dislodged wheat. A local family's reported light was a separate account. The geometry of a smaller nearby area was not established.",
      controls: "The police and visiting investigators could not connect the mark to a specific event. Germination indicated some delay before discovery.",
      sources: [
        source("sketch", "Tooligie Hill field sketch", sketchUrl + "6114106_orig.jpg",
          "Reproduced investigator drawing with center diameter and adjacent band widths."),
        source("correspondence", "Habner letter and police response reproduced in workshop proceedings",
          "https://www.nicap.org/reports2/Proceedings-of-SHG-UFO-History-Workshop.pdf",
          "Printed pp. 106–107, family description, site chronology and police commissioner’s reply.")
      ],
      traces: [
        trace("impression", "The field sketch labels exposed soil around the central wheat. The catalog describes a pressed band in hard clay, about 45 cm wide.", ["sketch", "correspondence", "basterfield"],
          pattern("Soil band around a wheat center", ["ring"], "dimensions",
            "The sketch records an 18 in band and a 45 in central span. The band is continuous in the sketch, without mapped discrete support marks.")),
        trace("deformation", "The outer wheat lay counterclockwise in a band about 60 cm wide. The central wheat was affected differently and the letter describes it as shortened.", ["sketch", "correspondence"],
          pattern("Counterclockwise outer band", ["ring", "swirl"], "dimensions",
            "The sketch gives a 24 in band width and draws curved stalks around the annulus.", { handedness: "counterclockwise" }))
      ],
      diagram: {
        title: "Tooligie Hill exposed soil and vegetation bands",
        viewBox: [-2.05, -2.05, 4.1, 4.1],
        basis: "Schematic from the field sketch's annotated dimensions",
        note: "The 45 in center, 18 in soil band and 24 in wheat band are drawn concentrically. The small adjacent crescent and other reported mark lack a recoverable outline.",
        layers: [
          layer("deformation", "Wheat center and outer lay", "The inner outline marks the wheat center. Selected curves show the separate swirled outer wheat.",
            ["sketch", "correspondence"], [ring(0.572, "Central wheat area"), ring(1.638, "Outer wheat band extent"),
              path("M -0.1 -1.46 Q -0.9 -1.47 -1.24 -0.77 M 1.46 -0.1 Q 1.47 -0.9 0.77 -1.24 M 0.1 1.46 Q 0.9 1.47 1.24 0.77 M -1.46 0.1 Q -1.47 0.9 -0.77 1.24", "Representative counterclockwise curves")]),
          layer("impression", "Exposed clay band", "The two boundaries represent the band labeled soil in the field sketch.",
            ["sketch", "basterfield"], [ring(0.572, "Inner edge of soil band"), ring(1.029, "Outer edge of soil band")])
        ]
      }
    }),
    site(81, "original", {
      id: "bordertown",
      title: "Bordertown",
      date: "1973-12",
      location: "Bordertown, South Australia, Australia",
      summary: "A farmer found seven flattened formations in an oat paddock. Keith Basterfield investigated, photographed the site and drew the approximate positions.",
      limits: "The formations varied in apparent age. The rough site plan gives relative positions, but the reviewed records do not establish an individual diameter for each plotted center or a sighting at formation time.",
      controls: "Basterfield described his field inspection and a later comparison with a man-made reconstruction in an ABC interview.",
      sources: [
        source("plan", "Keith Basterfield, Bordertown field plan", sketchUrl + "4393345_orig.jpg",
          "Reproduced site plan, numbered positions 1–7."),
        source("interview", "Keith Basterfield interview and field photography",
          "https://www.abc.net.au/news/2016-04-22/ufos-crop-circles-and-strange-happenings/7347580",
          "ABC interview with the investigator and the seven-formation report.")
      ],
      traces: [
        trace("deformation", "Seven flattened oat circles, roughly 2–4.6 m across, were reported with counterclockwise stem lay.", ["plan", "interview", "basterfield"],
          pattern("Seven dispersed circles with counterclockwise lay", ["ring", "swirl"], "description",
            "The plan shows one run of four centers, a nearby pair and a separate center. It gives the group layout rather than survey-grade measurements.", { handedness: "counterclockwise" }))
      ],
      diagram: {
        title: "Bordertown approximate field plan of seven flattened formations",
        viewBox: [173, 132, 157, 151],
        basis: "Centers digitized from the investigator's rough plan",
        note: "Markers indicate relative positions as drawn. Their size does not encode the individual circle diameters.",
        layers: [layer("deformation", "Seven oat formations", "The positions were plotted over a field area. The stem direction was described for the circles, with no measured local orientation field.",
          ["plan", "interview"], [[246, 267], [210, 172], [202, 187], [230, 155], [199, 206], [296, 231], [305, 238]]
            .map(([x, y], index) => point(x, y, "Formation " + (index + 1), String(index + 1))))]
      }
    }),
    site(107, "catalog", {
      id: "mount_garnet",
      title: "Mount Garnet",
      date: "1977-02",
      location: "Mount Garnet, Queensland, Australia",
      summary: "The catalog records a grass ring after a report of a silvery object in a paddock. Four smaller oval formations reportedly touched the ring.",
      limits: "The catalog credits UFORFNQ. It provides approximate directions and dimensions without a plan, individual oval bearings or surveyed axes.",
      traces: [
        trace("surface", "The dead grass band was about 80 cm wide, the complete ring about 6.7–6.8 m across, and the center vegetation was described as healthy.", ["basterfield"],
          pattern("Dead grass ring with a healthy center", ["ring"], "dimensions", "The dimensions describe the ring as a whole.")),
        trace("surface", "The catalog describes four adjoining oval formations around the main ring at about 3, 6, 9 and 12 o'clock, each roughly 2–3 m in size.", ["basterfield"],
          pattern("Four reported lobes at quarter-turn intervals", ["radial", "opposed", "oval"], "description",
            "The clock-face description suggests fourfold placement. The oval shapes and actual deviations from quarter turns remain unmeasured."))
      ],
      diagram: {
        title: "Mount Garnet schematic of ring and four reported oval formations",
        viewBox: [-7, -7, 14, 14],
        basis: "Schematic from approximate dimensions and clock-face positions",
        note: "The oval outlines show the reported arrangement. They use representative sizes and orientations.",
        layers: [layer("surface", "Grass ring and adjoining formations", "The central band and four adjoining features are vegetation observations. Their cause is undetermined.",
          ["basterfield"], [ring(3.38, "Outer edge of dead grass ring"), ring(2.58, "Inner edge of dead grass ring"),
            ellipse(4.58, 0, 1.20, 0.80, "Reported oval near 3 o'clock"), ellipse(0, 4.58, 0.80, 1.20, "Reported oval near 6 o'clock"),
            ellipse(-4.58, 0, 1.20, 0.80, "Reported oval near 9 o'clock"), ellipse(0, -4.58, 0.80, 1.20, "Reported oval near 12 o'clock")])]
      }
    }),
    site(109, "original", {
      id: "orange_nsw",
      title: "Orange",
      date: "1977-05-26",
      location: "Near Orange, New South Wales, Australia",
      summary: "A mother and son reported bright lights near their property. A field investigator confirmed four small ground impressions on sloping grassland.",
      limits: "Rain and snow intervened before field inspection. The investigators reported four distances but did not publish surveyed diagonals or a horizontal slope correction.",
      controls: "The team compared imprint and control soil. Spectroscopy did not reveal an unusual result. Thermoluminescence gave conditional upper estimates for heating and ionizing exposure.",
      sources: [source("apro", "UFO Research NSW, Orange field investigation", aproUrl + "apro_apr_1978.pdf#page=4",
        "APRO Bulletin, April 1978, printed pp. 4–5, field survey and soil analyses.")],
      traces: [
        trace("impression", "Four impressions roughly 5 cm across were found, with sides of 5.3, 10.1, 4.3 and 5.8 m. The report describes the outline as trapezoidal.", ["apro"],
          pattern("Uneven four-point layout on a slope", ["four_point"], "dimensions",
            "All four sides differ. The lowest mark was reportedly deeper, and how the slope affected the surveyed geometry is uncertain.",
            { edgesM: [5.3, 10.1, 4.3, 5.8] }))
      ],
      diagram: {
        title: "Orange approximate four-mark layout",
        viewBox: [-1.2, -1.2, 12.5, 6.6],
        basis: "Schematic using four reported sides and the described trapezoid",
        note: "The diagram assumes the two longer sides are parallel. It shows one possible reconstruction in the absence of diagonals or measured angles.",
        layers: [layer("impression", "Four soil impressions", "The perimeter is a visual guide. Marker size is exaggerated.",
          ["apro"], [path("M 0 0 H 10.1 L 9.066 4.174 H 3.266 Z", "One possible four-side reconstruction"),
            point(0, 0, "Impression 1"), point(10.1, 0, "Impression 2"),
            point(9.066, 4.174, "Impression 3"), point(3.266, 4.174, "Impression 4")])]
      }
    }),
    site(126, "original", {
      id: "rosedale_victoria",
      title: "Rosedale",
      date: "1980-09-30",
      location: "Rosedale, Victoria, Australia",
      summary: "A caretaker reported a light on the ground and later examined a dark ring of flattened grass. Field investigators subsequently interviewed him and visited the site.",
      limits: "The ring size and six-spoke description come from the initial witness account in the investigators’ report. The compiler gives a larger diameter estimate than that original account.",
      controls: "Investigators collected soil and rock samples in December. This report gives no analytical results or calibrated positions for discoloration apart from the flattened ring.",
      sources: [source("apro", "Bill Chalker and Keith Basterfield, Rosedale field investigation",
        aproUrl + "1981_APRO_Bulletin_v29_n12.pdf#page=4",
        "APRO Bulletin, December 1981, printed pp. 4–5, witness account and field follow-up.")],
      traces: [
        trace("deformation", "The witness described a counterclockwise band of flattened grass about 28 ft (8.5 m) across and 18 in (46 cm) wide, with six relatively undamaged spokes.", ["apro"],
          pattern("Counterclockwise ring with six reported spokes", ["ring", "swirl", "radial"], "dimensions",
            "The spoke spacing was described as even. The actual angles and spoke lengths were not recorded.", { handedness: "counterclockwise" })),
        trace("surface", "The flattened band was described as black or brown. The center remained green, with yellow flowers absent.", ["apro", "basterfield"],
          pattern("Darkening coincident with the grass band", ["ring"], "description", "The reported darkening lies on the flattened band. The cause of the color remains uncertain."))
      ],
      diagram: {
        title: "Rosedale ring, vegetation lay and reported spoke arrangement",
        viewBox: [-5.1, -5.1, 10.2, 10.2],
        basis: "Schematic from the reported band dimensions and spoke count",
        note: "This diagram shows the reported ring and six regularly spaced spoke positions as a schematic. It does not assign measured bearings or independently mapped sources of darkening.",
        layers: [
          layer("surface", "Reported dark band", "The color description applies to the same band as the flattened grass.",
            ["apro"], [ring(4.27, "Approximate outer edge of dark band"), ring(3.81, "Approximate inner edge of dark band")]),
          layer("deformation", "Flattened grass and six less affected spokes", "The radial segments mark schematic spokes. The recorded grass lay was counterclockwise.",
            ["apro"], Array.from({ length: 6 }, (_, index) => {
              const angle = index * Math.PI / 3;
              const coordinates = [3.15, 4.22].map((radius) =>
                [Math.cos(angle) * radius, Math.sin(angle) * radius].map((value) => value.toFixed(2)).join(" "));
              return path("M " + coordinates[0] + " L " + coordinates[1], "Reported spoke " + (index + 1));
            }))
        ]
      }
    })
  ];
});
