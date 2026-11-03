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
  const afuMagazines = "https://files.afu.se/Downloads/Magazines/Australia/";
  const churchillUrl = afuMagazines + "Australian%20UFO%20Bulletin/Australian%20UFO%20Bulletin%20-%201990%2003%20-%20March.pdf";
  const portNeillUrl = "https://www.beaudeeley.com/xenodimensional/ufo/Australian%20UFO%20Bulletin%20-%201977%2005%20-%20May.pdf";
  const afsrUrl = afuMagazines + "Australian%20Flying%20Saucer%20Review/Australian%20Flying%20Saucer%20Review%20-%201966%20";
  const july1966 = afsrUrl + "07%20-%20no%205%20VFSRS.pdf";
  const november1966 = afsrUrl + "11%20-%20no%209%20UFOIC.pdf";
  const june1990 = afuMagazines + "Australian%20UFO%20Bulletin/Australian%20UFO%20Bulletin%20-%201990%2006%20-%20June.pdf";

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
    site(4, "catalog", {
      id: "eton_ridge",
      title: "Eton Ridge",
      date: "1965-05-24",
      location: "Eton Ridge, Queensland, Australia",
      summary: "James Tilse reported a flattened grass area and possible burning in treetops after a reported sighting. A contemporary account describes two bands of different flattening with an undisturbed center.",
      limits: "The published summary attributes the dimensions to local police. The police measurements and Tilse's reported ground photographs were not independently recovered. The tree marks lack positions and are outside the grass diagram.",
      sources: [source("ufoic", "UFOIC, contemporary Eton Ridge account", november1966 + "#page=14",
        "Australian Flying Saucer Review No. 9, November 1966, PDF p. 14. Reports Tilse's inspection and attributes a separate description to police.")],
      traces: [
        trace("deformation", "A 20 ft radius grass patch had an untouched center and a surrounding 3 ft 2 in band of less flattened grass. The report distinguishes the grass from the possible burning in treetops.", ["ufoic"],
          pattern("Two circular grass bands", ["ring"], "dimensions", "The reported total diameter is 46 ft 4 in (14.12 m). The unchanged center has no measured radius.", { dimensions: { longM: 14.12, shortM: 14.12 } })),
        trace("scorching", "Tilse described apparent signs of burning in treetops. No tree positions or burn dimensions were published in this account.", ["ufoic"])
      ],
      diagram: {
        title: "Eton Ridge grass band boundaries",
        viewBox: [-8.6, -8.6, 17.2, 17.2],
        basis: "Boundaries reconstructed from a contemporary report",
        note: "The circles show the stated boundaries of the two flattening bands. The untouched center and possible treetop burning lack measurements.",
        layers: [layer("deformation", "Strong and weaker grass flattening", "The two reported boundaries are approximately 12.19 and 14.12 m across.", ["ufoic"],
          [ring(6.096, "Boundary of strongly flattened grass"), ring(7.061, "Outer edge of less-flattened band")])]
      }
    }),
    site(8, "original", {
      id: "tully_january_26",
      title: "Horseshoe Lagoon follow-up, January 26",
      date: "1966-01-26",
      location: "Near Tully, Queensland, Australia",
      summary: "The contemporary account credits Lou Lardi and Van Klaphake with finding two older-looking reed formations a week after the original Tully report. It describes a scorched patch at the center of the smaller one.",
      limits: "The two formations had no reported sightings tied to their creation. The lagoon sketch does not assign the two measured sizes to distinct positions with confidence.",
      sources: [source("ufoic", "UFOIC account of the additional Tully formations", november1966 + "#page=17",
        "Australian Flying Saucer Review No. 9, November 1966, pp. 17–18. The text distinguishes the two older-looking circles from a later find.")],
      traces: [
        trace("deformation", "The two formations were about 12 ft (3.66 m) and 8 ft (2.44 m) across. The article attributes counterclockwise reed lay to these formations and a later find.", ["ufoic"],
          pattern("Two circular reed formations", ["ring", "swirl"], "dimensions", "Reported spans are separate diameters. Individual reed paths are unmeasured.", { handedness: "counterclockwise" })),
        trace("scorching", "The smaller formation reportedly had a circular scorched patch centered within it.", ["ufoic"],
          pattern("Central scorch", ["ring"], "description", "The account provides no scorch diameter or material analysis for this patch."))
      ],
      diagram: {
        title: "January 26 Tully formations, size comparison",
        viewBox: [-4.6, -2.35, 8.5, 4.7],
        basis: "Independent diameters and one reported central relation",
        note: "The outlines are placed side by side for comparison. Their real separation and relative orientation are unknown. The center symbol does not encode scorch extent.",
        layers: [
          layer("deformation", "Flattened reed outlines", "The two reported diameters are 3.66 m and 2.44 m.", ["ufoic"],
            [ellipse(-2.25, 0, 1.83, 1.83, "Larger reed formation"), ellipse(1.8, 0, 1.22, 1.22, "Smaller reed formation")]),
          layer("scorching", "Reported central scorch", "The source locates the patch at the center of the smaller formation.", ["ufoic"],
            [point(1.8, 0, "Center of reported scorch")])
        ]
      }
    }),
    site(9, "original", {
      id: "euramo_late_january",
      title: "Euramo late January reed formation",
      date: "1966-01",
      location: "Euramo, Queensland, Australia",
      summary: "The contemporary account describes a new reed formation with a scorched center among the earlier Horseshoe Lagoon formations.",
      limits: "The report gives no dimensions or survey coordinates for this later formation. Its description is distinct from the two formations found a week after the January 19 sighting.",
      sources: [source("ufoic", "UFOIC account of the later Pennisi farm formation", november1966 + "#page=18",
        "Australian Flying Saucer Review No. 9, November 1966, p. 18, opening paragraphs.")],
      traces: [
        trace("deformation", "The report groups the new formation with the two previously discovered ones and describes all three as flattened counterclockwise.", ["ufoic"],
          pattern("Counterclockwise reed lay", ["swirl"], "description", "No diameter or measured stem angles are given for this formation.", { handedness: "counterclockwise" })),
        trace("scorching", "The source describes scorching at the center of the new formation.", ["ufoic"])
      ]
    }),
    site(10, "original", {
      id: "bankstown_reeds",
      title: "Bankstown reed clearing",
      date: "1966-02-14",
      location: "Bankstown, New South Wales, Australia",
      summary: "Two students found a circular area of flattened reeds. The UFOIC report includes an on-site inspection and an oblique photograph.",
      limits: "Visitors damaged the reeds before or during follow-up. The account links no observed landing to the site, and the photo provides no calibrated stem angles.",
      controls: "The investigators reported no access tracks in the standing grass and tested whether stems would snap when flexed. No matched comparison plot is described.",
      sources: [source("ufoic", "UFOIC Bankstown inspection and photograph", november1966 + "#page=22",
        "Australian Flying Saucer Review No. 9, November 1966, p. 22.")],
      traces: [
        trace("deformation", "The reported circle measured 19 ft 6 in (5.94 m) across. Reeds lay clockwise and were bent near the base.", ["ufoic"],
          pattern("Clockwise reeds within a circle", ["ring", "swirl"], "dimensions", "The diameter establishes the approximate envelope. The source provides a direction in prose, with no mapped stem paths.", { dimensions: { longM: 5.94, shortM: 5.94 }, handedness: "clockwise" }))
      ],
      diagram: {
        title: "Bankstown reed clearing envelope",
        viewBox: [-3.65, -3.65, 7.3, 7.3],
        basis: "Reported diameter and contemporary oblique photograph",
        note: "The outline uses the reported diameter. Reed lay is recorded in the description without invented stem paths.",
        layers: [layer("deformation", "Flattened reed outline", "The circular outline is approximate.", ["ufoic"], [ring(2.97, "Reported reed clearing envelope")])]
      }
    }),
    site(11, "original", {
      id: "burkes_flat",
      title: "Burkes Flat depression",
      date: "1966-04-04",
      location: "Burkes Flat, Victoria, Australia",
      summary: "Ronald Sullivan reported finding a round depression in a ploughed and harrowed paddock after a light sighting. His published sketch places it relative to the road and his line of sight.",
      limits: "The trace measurements are approximate values from Sullivan's letter. The plot in his sketch marks the object-to-depression association as an assumption.",
      sources: [source("sullivan", "Ronald Sullivan's account and diagram", july1966 + "#page=8",
        "Australian Flying Saucer Review, Victorian edition No. 5, July 1966, printed p. 12 / PDF p. 8. Includes Sullivan's own scene drawing.")],
      traces: [
        trace("impression", "Sullivan described one circular depression approximately 4 ft (1.22 m) across and 6 in (15 cm) deep.", ["sullivan"],
          pattern("Single circular depression", ["isolated", "ring"], "dimensions", "Reported outer diameter and depth describe one mark. No measured profile or neighboring support marks were published.", { dimensions: { longM: 1.22, shortM: 1.22 } }))
      ],
      diagram: {
        title: "Burkes Flat depression envelope",
        viewBox: [-0.85, -0.85, 1.7, 1.7],
        basis: "Approximate outer diameter reported by Sullivan",
        note: "The outline depicts the one reported depression. Sullivan's source sketch records the broader scene context.",
        layers: [layer("impression", "Depression", "The profile is unmeasured beyond the reported depth.", ["sullivan"], [ring(0.61, "Reported depression envelope")])]
      }
    }),
    site(12, "original", {
      id: "westall",
      title: "Westall field grass",
      date: "1966-04-06",
      location: "Westall, Victoria, Australia",
      summary: "An anonymous pupil's 1966 account describes finding a broad patch of flattened grass beyond the school after an aerial sighting.",
      limits: "The pupil lost sight of the object behind pines before inspecting the field. The patch dimensions were an estimate, without a measured boundary, site plan, or independently verified scorching.",
      sources: [source("clayton", "Westall pupil account in The Clayton Calendar", july1966 + "#page=9",
        "Australian Flying Saucer Review, Victorian edition No. 5, July 1966, printed pp. 13–14 / PDF pp. 8–9.")],
      traces: [
        trace("deformation", "The pupil described grass crushed against the ground over an area about 25–30 ft (7.6–9.1 m) across and reported seeing no access track.", ["clayton"])
      ]
    }),
    site(133, "original", {
      id: "turriff_wheat_rings",
      title: "Turriff wheat rings near Speed",
      date: "1989-12-06",
      location: "Turriff near Speed, Victoria, Australia",
      summary: "Auchettl's field report describes twelve flattened wheat formations, commonly in pairs down a rise. All twelve reportedly had counterclockwise stem lay and four retained upright wheat at their centers.",
      limits: "The field report gives counts, diameters and qualitative arrangement, without a survey tying diameters or soil properties to all twelve positions. Its account of a May light is a separate event from the December discovery.",
      controls: "The report records negative on-site radiation tests and compares soil inside and outside several rings. Numerical magnetometer results were left to a later report. The interior of ring 4 showed no unusual surface indentations in the area checked.",
      sources: [source("auchettl", "John W. Auchettl, The Turriff Ground Ring Summary", june1990 + "#page=8",
        "Australian UFO Bulletin, June 1990, printed pp. 11–15 and 18–20, PDF pp. 7–9 and 11–12.")],
      traces: [
        trace("deformation", "Twelve circular formations ranged from 1.22 to 3.66 m in diameter. Most were reported in pairs along a J-shaped course, with pair axes trending northeast. Four formations retained upright central wheat.", ["auchettl"],
          pattern("Twelve counterclockwise wheat formations", ["ring", "swirl"], "dimensions", "Reported diameters are 3.66 m twice, 2.74, 2.59, 1.98, 1.83 m five times, 1.37 and 1.22 m. Relative positions are not measured.", { handedness: "counterclockwise" })),
        trace("surface", "Soil in the main formations was described as hard and smooth. Smaller rings near the fence lacked that reported soil hardness.", ["auchettl"])
      ]
    }),
    site(132, "original", {
      id: "churchill_park",
      title: "Churchill Park, Endeavour Hills",
      date: "1989-10-09",
      location: "Endeavour Hills, Victoria, Australia",
      summary: "Field investigator John W. Auchettl found a ring of discolored grass with four small pad-like holes, two scoops and a central cluster of indistinct marks after a reported light sighting.",
      limits: "The ground ring was found after four days of searching. The sighting did not establish contact with that patch. The bulletin describes vegetation and soil testing but supplies no calibrated exposure, complete lab data or control series for inferring a source.",
      controls: "Auchettl reported comparing soil from inside and outside, found no unusual soil elements in the tests described, and raised radon as a possible contributor to the reported alpha difference. These are the investigator's reported comparisons.",
      sources: [source("auchettl", "John W. Auchettl, Churchill Park field report and plan", churchillUrl + "#page=11",
        "Australian UFO Bulletin, March 1990, printed pp. 11–19. Measurements p. 15, testing p. 16 and field plan p. 19 (PDF p. 11).")],
      traces: [
        trace("impression", "Four 5 cm holes, each 3 cm deep with a reported 7 cm pad impression, had two adjacent 2.28 m separations and two adjacent 2.60 m separations. Two nearby scoop-like marks were mapped separately.", ["auchettl"],
          pattern("Four holes in a kite-like layout", ["four_point"], "dimensions",
            "The printed equal-side pairs suggest one approximate reflection axis. No survey uncertainty or support mechanism is recorded.", { edgesM: [2.28, 2.28, 2.6, 2.6] })),
        trace("surface", "The investigator described a brown-yellow grass band, 8–10 cm wide, around a green interior. A small central mark group was left undefined.", ["auchettl"],
          pattern("Circular vegetation discoloration", ["ring"], "dimensions",
            "The source gives a 3.65 m outer diameter. The color change is recorded separately from the depressions and its cause remains open.", { dimensions: { longM: 3.65, shortM: 3.65 } }))
      ],
      diagram: {
        title: "Churchill Park field plan",
        viewBox: [-2.25, -2.18, 4.5, 4.36],
        basis: "Positions traced from Auchettl's printed graph-paper plan",
        note: "North is right and east is down, as in the source. Coordinates are approximate, scaled to the reported outer diameter. Point symbols are enlarged and the discoloration ring stroke is illustrative.",
        layers: [
          layer("surface", "Discolored vegetation and central marks", "The plan depicts the narrow brown-yellow band and a small undefined central group.", ["auchettl"],
            [ring(1.825, "Outer extent of brown-yellow ring"), point(-0.12, 0, "Undefined central marks", "G")]),
          layer("impression", "Holes and pad marks", "Four locations from the field plan. The two near sides to A are annotated 2.28 m and the two sides to C are annotated 2.60 m.", ["auchettl"],
            [point(-0.05, -1.68, "A, hole and pad imprint", "A"), point(-1.69, -0.17, "B, hole and pad imprint", "B"),
              point(-0.05, 1.74, "C, hole and pad imprint", "C"), point(1.6, -0.17, "D, hole and pad imprint", "D")]),
          layer("impression", "Separate scoop marks", "E and F are distinct from the four holes. The illustrated scoop profile is 10 × 7 cm and 3 cm deep.", ["auchettl"],
            [point(-0.81, 1.2, "E, scoop", "E"), point(-0.05, 1.57, "F, scoop", "F")])
        ]
      }
    }),
    site(108, "original", {
      id: "port_neill",
      title: "Port Neill",
      date: "1977-03",
      location: "Port Neill, South Australia, Australia",
      summary: "Brian Bray found an annular scoop in a paddock. Contemporary accounts describe a hollow between an undisturbed center and a hard outer rim.",
      limits: "The two local newspaper accounts give different outer measurements, about 4.3 m and about 4.62 m when doubling the reported 7 ft 7 in center-to-rim distance. Neither gives a cross section or connects the mark to a witnessed event.",
      sources: [source("eyre_press", "Port Lincoln Times and Eyre Peninsula Tribune contemporary reports", portNeillUrl + "#page=4",
        "Australian UFO Bulletin, May 1977, printed p. 4. Excerpts from 3 and 17 March 1977 respectively.")],
      traces: [
        trace("impression", "The annular soil hollow reportedly held loose sand over harder soil. Its width and depth were unrecorded.", ["eyre_press"],
          pattern("Circular soil hollow", ["ring"], "dimensions",
            "Approximate outer span comes from the two press accounts. Inner edge and profile are unmeasured.", { dimensions: { longM: 4.3, shortM: 4.3 } })),
        trace("surface", "The center was described as undisturbed and the outer rim as harder than the neighboring topsoil.", ["eyre_press"])
      ],
      diagram: {
        title: "Port Neill reported outer extent",
        viewBox: [-2.9, -2.9, 5.8, 5.8],
        basis: "One reported outer diameter",
        note: "The outline uses the Tribune's approximate 4.3 m diameter. The other press estimate implies about 4.62 m. The hollow's inner edge is unmeasured.",
        layers: [layer("impression", "Outer extent of annular soil feature", "Measured envelope only. The ring stroke carries no width measurement.", ["eyre_press"],
          [ring(2.15, "Approximate outer extent")])]
      }
    }),
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
