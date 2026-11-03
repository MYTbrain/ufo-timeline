(function (root, factory) {
  "use strict";

  const cases = factory();
  if (typeof module === "object" && module && module.exports) {
    module.exports = cases;
  }
  if (root) {
    root.UfoLandingSiteExpandedCases = cases;
  }
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";

  // Approximate positions digitized from Campbell's Figure 3, with SVG y increasing downwards.
  const dechmontHoles = [
    [-2.67, -1.88], [-2.40, -1.88], [-2.55, -1.59], [-2.29, -1.44], [-1.61, -1.85],
    [-1.06, -2.26], [-2.43, -0.50], [-2.35, 0.48], [-2.28, 1.40], [-2.12, 2.24],
    [-1.22, 2.40], [-0.31, 2.23], [0.79, 2.04], [1.70, 2.16], [2.59, 1.92],
    [0.17, -3.15], [-0.26, -2.79], [0.17, -2.53], [-0.38, -2.36], [-0.19, -1.99],
    [0.21, -1.93], [-0.26, -1.40], [0.22, -1.35], [-0.24, -0.75], [0.24, -0.77],
    [-0.22, -0.09], [0.26, -0.17], [-0.22, 0.65], [0.27, 0.60], [-0.21, 1.44],
    [0.29, 1.40], [2.28, -3.05], [2.65, -2.76], [2.95, -2.43], [3.08, -1.97],
    [3.27, -1.51], [3.27, -0.89], [3.27, -0.29], [3.25, 0.31], [3.20, 1.25]
  ];
  const dechmontTracks = [
    [[-1.28, -1.18], [-1.25, -0.89], [-1.25, -0.58], [-1.23, -0.27], [-1.23, 0.03],
      [-1.23, 0.33], [-1.22, 0.65], [-1.22, 0.92], [-1.18, 1.23]],
    [[1.25, -1.27], [1.25, -0.94], [1.25, -0.65], [1.25, -0.34], [1.25, -0.03],
      [1.27, 0.29], [1.27, 0.58], [1.28, 0.92], [1.30, 1.23]]
  ];
  const antenBurnGaps = [2.55, 2.60, 2.60];
  const phillipsBook = "https://cufos.org/PDFs/books/Physical_Traces.pdf";

  function phillipsEntry(id, pdfPage, locator) {
    return {
      id: "phillips",
      label: "Ted Phillips, Physical Traces Associated with UFO Sightings",
      url: phillipsBook + "#page=" + pdfPage,
      locator: "CUFOS 1975, case " + id + ", printed p. " + (pdfPage - 18) + ". " + locator
    };
  }

  function triangleDossier({ id, title, date, location, number, page, summary, locator, detail, sides, sharedSpan, extraTraces = [] }) {
    const [ab, ac, bc] = sides;
    const x = (ab * ab + ac * ac - bc * bc) / (2 * ab);
    const y = Math.sqrt(ac * ac - x * x);
    const pad = Math.max(ab, y) * 0.18;
    const left = Math.min(0, x);
    const right = Math.max(ab, x);
    return {
      id, title, date, location, phillipsCaseNumber: number, summary,
      limits: "The available entry reports the geometry and cites an upstream account. Survey uncertainty, geographic bearings and the origin of the traces remain open.",
      sources: [phillipsEntry(number, page, locator)],
      traces: [{
        kind: "impression", observation: detail, sourceIds: ["phillips"],
        pattern: {
          label: "Three marks with reported spacing", families: ["three_point"], basis: "dimensions",
          details: sharedSpan ? "The reconstruction uses a shared side description. Individual lengths were unavailable." :
            "The three reported side lengths are retained. Their agreement or spread is descriptive.",
          ...(sharedSpan ? {} : { edgesM: sides })
        }
      }, ...extraTraces],
      diagram: {
        title: title + " reported three-mark layout",
        basis: sharedSpan ? "Schematic from the reported shared span" : "Reconstruction from three reported side lengths",
        note: "The orientation is arbitrary. The diagram plots the documented triangle. Other marks and vegetation are described separately where their positions are unavailable.",
        viewBox: [left - pad, -pad, right - left + 2 * pad, y + 2 * pad],
        layers: [{
          kind: "impression", label: "Three reported marks", note: detail, sourceIds: ["phillips"],
          marks: [[0, 0], [ab, 0], [x, y]].map(([px, py], index) => ({
            type: "point", x: px, y: py, tag: "ABC"[index], label: "Reconstructed mark " + "ABC"[index], estimated: true
          }))
        }]
      }
    };
  }

  return [
    {
      id: "south_hill",
      title: "South Hill",
      date: "1967-04-21",
      location: "South Hill, Virginia, United States",
      summary: "A driver reported an object on a road and returned with two state troopers. They found a burned patch and spent paper matches. The next inspection found four small holes around the patch.",
      limits: "The troopers said the holes were absent during the first inspection. The Air Force flagged a possible prank and continued to carry the sighting as unidentified.",
      controls: "Investigators compared asphalt from the burned patch with an unburned sample. Infrared spectroscopy of the extracts found no foreign material, and the report noted that a chemical could have evaporated.",
      sources: [
        {
          id: "blue-book",
          label: "U.S. Air Force Project Blue Book case summary",
          url: "https://documents.theblackvault.com/bluebookdesk/pbb-univcol.pdf",
          locator: "South Hill, Virginia, April 21, 1967, narrative and investigative comments."
        }
      ],
      traces: [
        {
          kind: "scorching",
          observation: "State troopers found a burned patch on the road and three spent paper matches near its center.",
          context: "The Air Force considered ignition of a flammable liquid and described an absence of outward blast marks or blast damage to the pavement.",
          sourceIds: ["blue-book"]
        },
        {
          kind: "impression",
          observation: "On the following morning four holes, each roughly ½ in (1.3 cm) in diameter, were reported around the burned patch.",
          context: "The sequence matters because the burn was already present at the first search and the holes were first recorded the following day.",
          sourceIds: ["blue-book"],
          pattern: {
            label: "Reported square around a burn",
            families: ["four_point"],
            basis: "description",
            details: "The Air Force describes the holes as forming a square. The case summary gives no perimeter lengths or angles to test the reported symmetry."
          }
        }
      ]
    },
    {
      id: "falcon_lake",
      title: "Falcon Lake",
      date: "1967-05-20",
      location: "Falcon Lake, Manitoba, Canada",
      summary: "Stefan Michalak reported a landing on a rocky outcrop. After unsuccessful early searches, he and a companion identified a site with a roughly circular area of missing moss. Canadian investigators later examined the site.",
      limits: "The site was identified more than a month after the report. Michalak and his companion collected the first samples before an official site inspection, leaving their original placement and history uncertain.",
      controls: "A federal radiation officer surveyed the identified site, the perimeter and water runoff areas. Contamination was localized in and near a rock fissure, with none reported at the perimeter or in the runoff areas checked.",
      sources: [
        {
          id: "craig",
          label: "Roy Craig, University of Colorado field investigation",
          url: "https://www.project1947.com/shg/condon/case22.html",
          locator: "Scientific Study of Unidentified Flying Objects, Case 22, printed pp. 489–491, quoting the federal site survey."
        },
        {
          id: "lac",
          label: "Library and Archives Canada, Falcon Lake case records",
          url: "https://www.canada.ca/en/library-archives/collection/engage-learn/podcasts/discover/episode-054.html",
          locator: "Part 2 transcript, rediscovery of the site, sample handling and federal findings."
        }
      ],
      traces: [
        {
          kind: "surface",
          observation: "Reports describe a roughly circular area on the outcrop where moss was missing.",
          context: "The surviving descriptions establish a reported outline. The way the moss was removed, the date of formation and its connection to the sighting are unresolved.",
          sourceIds: ["craig", "lac"],
          pattern: {
            label: "Reported circular clearing in moss",
            families: ["ring"],
            basis: "description",
            details: "The reported outline gives a broad circular pattern. The reviewed records give too little boundary detail to quantify its symmetry."
          }
        },
        {
          kind: "surface",
          observation: "The federal site survey located contamination within and immediately beside a fissure across the rock. The reported contaminated area was no greater than about 100 in² (645 cm²).",
          context: "This was a localized radiological finding. Its spatial extent differed from the broad outline of missing moss.",
          sourceIds: ["craig", "lac"],
          pattern: {
            label: "Localized along a rock fissure",
            families: ["rows"],
            basis: "description",
            details: "The survey describes a narrow smear and adjacent affected vegetation. The perimeter of the reported moss clearing was free of contamination in that survey."
          }
        }
      ]
    },
    {
      id: "lake_anten",
      title: "Lake Anten",
      date: "1970-08-30",
      location: "Enebacken near Lake Anten, Sweden",
      summary: "After reports of a light overnight on August 29–30, three shallow, burn-like lawn depressions were found at Enebacken. GICOFF investigators photographed and measured them a few days later.",
      limits: "The marks had unequal shapes and depths. The observations leave the timing of their formation, their relation to the light and the number of sources open.",
      controls: "The investigators compared soil from one mark with soil sampled 4 m away and with an instrument background. They reported a weak gamma signal in the mark sample. The limited comparison leaves the source and its relation to the marks unresolved.",
      sources: [
        {
          id: "gicoff",
          label: "Sven-Olof Fredrickson, GICOFF field investigation",
          url: "https://ignaciodarnaude.es/wp-content/uploads/2025/08/FSR-1971-V-17-N-1.pdf#page=19",
          locator: "Flying Saucer Review 17(1), January–February 1971, pp. 13–17, Fig. 2 and site photos."
        },
        {
          id: "ufo-sweden",
          label: "UFO-Sverige case index",
          url: "https://www.ufo.se/index.php/a/796-anten-fallet2",
          locator: "Anten entry, ground trace and date summary."
        }
      ],
      traces: [
        {
          kind: "scorching",
          observation: "GICOFF documented three dark, shallow holes it described as burned, roughly 40 cm across and 4 cm deep. One was less round than the others.",
          context: "The apparent scorching and depressions refer to the same three features. Their depth alone does not distinguish loading from loss of material during burning or another process.",
          sourceIds: ["gicoff", "ufo-sweden"],
          pattern: {
            label: "Near-equilateral spacing of burn-like holes",
            families: ["three_point"],
            basis: "dimensions",
            details: "Figure 2 labels edge-to-edge gaps A–B 2.55 m, A–C 2.60 m and B–C 2.60 m. This is near-regular spacing, with unknown measurement uncertainty and some differences in the shapes of the marks.",
            edgeLabel: "Gap",
            edgesM: antenBurnGaps
          }
        }
      ],
      diagram: {
        title: "Lake Anten site diagram of three burn-like depressions",
        basis: "Reconstructed from measured gaps",
        note: "Local metres. The sketch gives edge-to-edge gaps, so each plotted center distance includes a nominal 0.40 m mark diameter. Markers indicate approximate locations, and the diagram is rotated to put A–B on a horizontal baseline.",
        viewBox: [-0.75, -0.7, 4.7, 4.05],
        layers: [{
          kind: "scorching",
          label: "Burn-like depressions",
          note: "The gaps differ by 5 cm. Two are equal at the reported precision. Exact symmetry and the origin of the three marks remain undetermined.",
          sourceIds: ["gicoff"],
          marks: [
            { type: "point", x: 0, y: 0, tag: "A", label: "Burn-like depression A", estimated: true },
            { type: "point", x: 2.95, y: 0, tag: "B", label: "Burn-like depression B", estimated: true },
            { type: "point", x: 1.475, y: 2.612, tag: "C", label: "Burn-like depression C", estimated: true }
          ]
        }]
      }
    },
    {
      id: "dechmont",
      title: "Dechmont Law",
      date: "1979-11-09",
      location: "Livingston, West Lothian, Scotland",
      summary: "Forestry worker Robert Taylor reported an encounter in a clearing. Police recorded ground marks and Steuart Campbell inspected and photographed the site the following day.",
      limits: "Campbell separated folded grass from the holes that reached soil. His account records no grass scorching. The formation process of both mark types remains open.",
      sources: [
        {
          id: "campbell",
          label: "Steuart Campbell, Close Encounter in Scotland",
          url: "https://www.bufora.org.uk/_files/ugd/4719c2_5c0378ccfd834e4a8485f4cb118e0fb5.pdf#page=22",
          locator: "Journal of Transient Aerial Phenomena, March 1980, printed pp. 43–46, Fig. 3 and site description."
        },
        {
          id: "council",
          label: "West Lothian Council, Dechmont Law case summary",
          url: "https://www.westlothian.gov.uk/media/26988/Dechmont-Law-UFO-info/pdf/Dechmont_Law_UFO.pdf",
          locator: "Council summary of the reported encounter and marks."
        }
      ],
      traces: [
        {
          kind: "deformation",
          observation: "Campbell described two ladder-like tracks, each about 2.5 m long and about 2.5 m apart, with rungs about 30 cm long. The grass blades folded but the ground profile beneath was undisturbed in his inspection.",
          sourceIds: ["campbell", "council"],
          pattern: {
            label: "Paired parallel ladder-like tracks",
            families: ["rows"],
            basis: "dimensions",
            details: "Each track repeats transverse rungs. The plan shows approximate bilateral balance between the two tracks. The repeated marks occurred in grass and are separate from the tapered holes."
          }
        },
        {
          kind: "impression",
          observation: "Campbell recorded 40 shallow angled holes in the soil, tapering from widths of up to about 10 cm.",
          sourceIds: ["campbell", "council"],
          pattern: {
            label: "Two described series with opposing directions",
            families: ["irregular"],
            basis: "description",
            details: "Campbell interpreted the individual inclinations as a clockwise and an anticlockwise series. The plotted centers retain the irregular paths. They leave the direction of any movement and exact mirror symmetry undetermined."
          }
        }
      ],
      diagram: {
        title: "Dechmont Law diagram of grass tracks and soil holes",
        basis: "Redrawn from the published field sketch",
        note: "Approximate plan-relative metres, scaled using the reported 2.5 m track separation. The source plan's orientation is retained with up on the page distinct from geographic north.",
        viewBox: [-3.35, -3.75, 7.4, 6.85],
        layers: [
          {
            kind: "deformation",
            label: "Flattened grass tracks",
            note: "Two approximately parallel tracks repeat a rung pattern. Line segments represent nominal 30 cm rungs based on the description.",
            sourceIds: ["campbell"],
            marks: dechmontTracks.map((rungs, index) => ({
              type: "path",
              d: rungs.map(([x, y]) => "M " + (x - 0.15) + " " + y + " h 0.3").join(" "),
              label: "Flattened grass track " + (index + 1)
            }))
          },
          {
            kind: "impression",
            label: "Tapered soil holes",
            note: "The 40 positions are approximate. The centers preserve the irregular arrangement while individual depths and angles remain in the source text.",
            sourceIds: ["campbell"],
            marks: dechmontHoles.map(([x, y], index) => ({
              type: "point", x, y, label: "Mapped hole " + (index + 1), estimated: true
            }))
          }
        ]
      }
    },
    {
      id: "rendlesham",
      title: "Rendlesham Forest",
      date: "1980-12-26",
      location: "Rendlesham Forest, Suffolk, England",
      summary: "U.S. Air Force personnel reported lights near RAF Woodbridge in late December. Lieutenant Colonel Charles Halt's subsequent memo describes three shallow depressions at the reported site.",
      limits: "The date follows Forestry England's chronology. Halt's memo dates the initial report December 27 and gives individual mark sizes but no distances between them.",
      controls: "Halt records radiation readings at several locations in the clearing. The memo alone gives too little instrument and background information to establish a local excess or its cause.",
      sources: [
        {
          id: "halt",
          label: "Lt. Col. Charles Halt, Unexplained Lights memorandum",
          url: "https://avalonlibrary.net/Rendlesham_Forest_incident_1980/Lt.%20Col.%20Halt%20Memorandum%20to%20MoD%20RAF%2013%20January%201981.pdf",
          locator: "January 13, 1981, paragraph 2, UK National Archives reference DEFE 24/1948/1."
        },
        {
          id: "tna",
          label: "UK National Archives UFO records guide",
          url: "https://cdn.nationalarchives.gov.uk/documents/aug-2009-research-guide.pdf",
          locator: "Research Notes 6, section 7, Rendlesham Forest and the MoD file."
        },
        {
          id: "forestry-england",
          label: "Forestry England, Rendlesham Forest chronology",
          url: "https://www.forestryengland.uk/rendlesham-forest/discovery-trail",
          locator: "Overview dates for the two reported sightings."
        }
      ],
      traces: [
        {
          kind: "impression",
          observation: "Halt recorded three depressions about 7 in (18 cm) across and 1½ in (3.8 cm) deep.",
          context: "The memo describes a triangle when locating instrument readings. Three depressions can form many different triangles.",
          sourceIds: ["halt"],
          pattern: {
            label: "Reported three-point arrangement",
            families: ["three_point"],
            basis: "description",
            details: "The memo gives sizes of the depressions. Between-mark distances and angles are absent, so mirror symmetry and even spacing cannot be assessed."
          }
        }
      ]
    },
    {
      id: "delroy_wheat",
      phillipsCaseNumber: 199,
      title: "Delroy",
      date: "1965-06-28",
      location: "Delroy, Ohio, United States",
      summary: "Phillips’s entry describes a farmer finding a bare circular patch in wheat, a central crater and flattened stalks around the perimeter. The entry reports a discovery and cites Fate magazine.",
      limits: "The stated width and diameter support a schematic. The source gives no measured angular spacing, stalk bearings or mapped crater profile.",
      sources: [phillipsEntry(199, 54, "Trace discovery summarized from Fate magazine.")],
      traces: [
        {
          kind: "impression", observation: "The reported central crater was about 28 in across and 5 in deep.",
          sourceIds: ["phillips"],
          pattern: { label: "Single central crater", families: ["isolated"], basis: "dimensions", details: "The entry locates the crater at the center of the bare area." }
        },
        {
          kind: "surface", observation: "The bare inner area was reported to be about 26 ft across.",
          sourceIds: ["phillips"],
          pattern: { label: "Circular bare area", families: ["ring"], basis: "dimensions", details: "The single diameter gives a nominal extent." }
        },
        {
          kind: "deformation", observation: "Wheat in a band about 13 ft wide was described as lying radially around the bare area.",
          sourceIds: ["phillips"],
          pattern: { label: "Radially flattened band", families: ["ring", "radial"], basis: "dimensions", details: "The report likens the stalk layout to wheel spokes. It gives no local directions or repeated sector count." }
        }
      ],
      diagram: {
        title: "Delroy bare circle, central crater and flattened wheat",
        basis: "Schematic from reported concentric dimensions",
        note: "The diagram derives the outer radius by adding the stated 13 ft band width to the inner 13 ft radius. Individual stalk directions were unmeasured.",
        viewBox: [-9, -9, 18, 18],
        layers: [
          { kind: "deformation", label: "Flattened wheat band", note: "The reported wheat lay is radial within the band.", sourceIds: ["phillips"],
            marks: [{ type: "ellipse", x: 0, y: 0, rx: 7.925, ry: 7.925, estimated: true, label: "Approximate outside of the flattened band" }] },
          { kind: "surface", label: "Bare inner area", note: "The circular outline represents the nominal 26 ft bare area.", sourceIds: ["phillips"],
            marks: [{ type: "ellipse", x: 0, y: 0, rx: 3.962, ry: 3.962, estimated: true, label: "Nominal bare-area boundary" }] },
          { kind: "impression", label: "Central crater", note: "The crater’s recorded diameter is small relative to either zone.", sourceIds: ["phillips"],
            marks: [{ type: "ellipse", x: 0, y: 0, rx: 0.356, ry: 0.356, label: "Crater nominal diameter 28 inches" }] }
        ]
      }
    },
    {
      id: "chapeau_rings",
      phillipsCaseNumber: 381,
      title: "Chapeau",
      date: "1969-05-11",
      location: "Chapeau, Québec, Canada",
      summary: "Phillips reports four circular or partial ground features found after a bright-light report. His published sketch shows the second ring and its three interior marks.",
      limits: "The measurements on the plan concern ring 2. The relative locations of all four features are absent from the plan. The described traces leave the source and formation dates open.",
      sources: [phillipsEntry(381, 82, "Account attributed to Brian Cannon and H. H. McKay."), {
        id: "plan", label: "Phillips’s Chapeau ring 2 plan", url: phillipsBook + "#page=10",
        locator: "PDF p. 10, upper diagram."
      }],
      traces: [
        {
          kind: "impression", observation: "Three round marks are shown inside ring 2. The entry also describes a separate 9 ft depression elsewhere in the field.",
          sourceIds: ["phillips", "plan"],
          pattern: { label: "Nearly equal-sided layout inside ring 2", families: ["three_point"], basis: "dimensions",
            details: "The ring 2 plan labels the three distances 13 ft 9 in, 13 ft 9 in and 14 ft 6 in. This gives two equal reported distances and a slightly longer third.", edgesM: [4.191, 4.191, 4.420] }
        },
        {
          kind: "surface", observation: "The sketch identifies a roughly 28 ft outside diameter for ring 2 and a nominal 3 ft band.",
          sourceIds: ["phillips", "plan"],
          pattern: { label: "Annular ground trace", families: ["ring"], basis: "dimensions", details: "The text gives 2 ft 6 in to 3 ft for the band. The recorded variation limits a circular-symmetry inference." }
        }
      ],
      diagram: {
        title: "Chapeau ring 2 and three interior marks",
        basis: "Redrawn from Phillips’s ring 2 plan",
        note: "Local orientation is that of the sketch. Symbols mark center locations. Three other reported features at Chapeau have no registered placement in this plan.",
        viewBox: [235, 65, 585, 580],
        layers: [
          { kind: "surface", label: "Ring 2", note: "The redrawn boundaries represent the nominal ring and band.", sourceIds: ["plan"],
            marks: [
              { type: "ellipse", x: 530, y: 354, rx: 257, ry: 256, estimated: true, label: "Outer boundary of ring 2" },
              { type: "ellipse", x: 530, y: 354, rx: 205, ry: 203, estimated: true, label: "Inner boundary of ring 2" }
            ] },
          { kind: "impression", label: "Three interior marks", note: "Two sides match at the reported precision, with the third about 23 cm longer.", sourceIds: ["plan"],
            marks: [
              { type: "point", x: 371, y: 332, label: "Left interior mark" },
              { type: "point", x: 625, y: 265, label: "Upper-right interior mark" },
              { type: "point", x: 569, y: 514, label: "Lower interior mark" }
            ] }
        ]
      }
    },
    {
      id: "east_connersville",
      phillipsCaseNumber: 248,
      title: "East Connersville",
      date: "1966-10-05",
      location: "East Connersville, Indiana, United States",
      summary: "Phillips summarizes two paperboys’ report of seeing lights and hearing stubble break in a field. A return visit the next evening reportedly found three cone-shaped holes.",
      limits: "The catalog attributes the account to Don Worley via CUFOS and APRO. Spacing and depth are estimates reported in the account.",
      sources: [phillipsEntry(248, 62, "Account attributed to Don Worley, APRO.")],
      traces: [{
        kind: "impression",
        observation: "Three cone-shaped holes were reported at about 7 in (18 cm) across, 7–8 in (18–20 cm) deep, and about 8 ft (2.4 m) apart.",
        sourceIds: ["phillips"],
        pattern: {
          label: "Reported near-equal separation",
          families: ["three_point"],
          basis: "dimensions",
          details: "The catalog describes roughly equal gaps with a single shared estimate. Exact distances and measurement uncertainty are unknown."
        }
      }],
      diagram: {
        title: "East Connersville reported three-hole layout",
        basis: "Schematic from reported spacing",
        note: "The diagram illustrates the stated approximate equal spacing. The catalog gives no surveyed coordinates, bearings or individual side lengths.",
        viewBox: [-0.5, -0.5, 3.55, 3.15],
        layers: [{
          kind: "impression",
          label: "Reported cone-shaped holes",
          note: "About 8 ft between holes was reported. Exact threefold symmetry cannot be tested from that single estimate.",
          sourceIds: ["phillips"],
          marks: [
            { type: "point", x: 0, y: 0, label: "First reported hole, schematic position", estimated: true },
            { type: "point", x: 2.44, y: 0, label: "Second reported hole, schematic position", estimated: true },
            { type: "point", x: 1.22, y: 2.11, label: "Third reported hole, schematic position", estimated: true }
          ]
        }]
      }
    },
    {
      id: "houston_missouri",
      phillipsCaseNumber: 537,
      title: "Houston, Missouri",
      date: "1972-09-14",
      location: "Houston, Missouri, United States",
      summary: "Phillips’s personal-file entry records an aerial light and a later ground-level flash. The witnesses reported finding flattened grass, three imprints and a blackened patch the next morning.",
      limits: "The date is Phillips’s catalog date. The later flash and discovery crossed midnight. The dark area is labelled scorched in Phillips’s plan. The available report gives no material analysis for its origin.",
      sources: [phillipsEntry(537, 104, "Phillips’s personal files."), {
        id: "plan", label: "Phillips’s Houston site plan and imprint detail",
        url: phillipsBook + "#page=12", locator: "PDF pp. 12 and 15, plan and detailed side lengths."
      }],
      traces: [
        {
          kind: "impression",
          observation: "Three small imprints with toe-like extensions were reported near the center of the depressed grass. Each was roughly 60 mm long and one was 40 mm deep.",
          sourceIds: ["phillips", "plan"],
          pattern: {
            label: "Long triangle of imprints", families: ["three_point", "irregular"], basis: "dimensions",
            details: "The imprint detail gives sides of 7.8, 8.0 and 2.7 ft. Two sides are similar in length, with a much shorter base.",
            edgesM: [2.377, 2.438, 0.823]
          }
        },
        {
          kind: "deformation",
          observation: "The catalog describes an oval of depressed grass on the yellowed side of an evergreen.",
          sourceIds: ["phillips"],
          pattern: { label: "Oval of depressed grass", families: ["oval"], basis: "dimensions", details: "The estimated footprint was 20 by 14 ft.", dimensions: { longM: 6.10, shortM: 4.27 } }
        },
        {
          kind: "scorching",
          observation: "The catalog places a blackened area in the center of the triangle of imprints.",
          context: "The plan labels this as scorch. Its heat source and physical mechanism remain unverified.",
          sourceIds: ["phillips", "plan"],
          pattern: { label: "Small patch within the imprint triangle", families: ["isolated"], basis: "description", details: "The plan shows a localized area. Its boundary was not surveyed." }
        }
      ],
      diagram: {
        title: "Houston grass outline, three impressions and reported scorching",
        basis: "Redrawn from Phillips’s site plan",
        note: "Plan-relative placement from PDF p. 12. Symbols indicate trace locations. The separately drawn imprint detail on p. 15 records the triangle side lengths.",
        viewBox: [155, 165, 740, 865],
        layers: [
          {
            kind: "deformation", label: "Depressed grass", note: "The report describes an elongated patch with a distinct, uneven boundary.", sourceIds: ["plan"],
            marks: [{ type: "path", d: "M 198 676 Q 210 493 313 346 Q 411 185 555 205 Q 745 202 821 360 Q 884 506 777 767 Q 692 955 509 980 Q 337 1007 241 882 Q 181 791 198 676 Z", estimated: true, label: "Approximate outline of depressed grass" }]
          },
          {
            kind: "impression", label: "Three ground impressions", note: "The short base distinguishes this triangle from roughly equal-sided arrangements.", sourceIds: ["plan"],
            marks: [
              { type: "point", x: 620, y: 383, tag: "A", label: "Imprint A" },
              { type: "point", x: 439, y: 645, tag: "B", label: "Imprint B" },
              { type: "point", x: 533, y: 695, tag: "C", label: "Imprint C" }
            ]
          },
          {
            kind: "scorching", label: "Area labelled scorched", note: "The diagram records one area near the upper part of the imprint triangle. Its outline remains uncertain.", sourceIds: ["plan"],
            marks: [{ type: "point", x: 550, y: 519, estimated: true, label: "Location of reported scorch patch" }]
          }
        ]
      }
    },
    {
      id: "montauroux",
      phillipsCaseNumber: 535,
      title: "Montauroux",
      date: "1972-09-20",
      location: "Montauroux, France",
      summary: "Phillips lists a report of twisted and cut trees and damage to a stone wall. His entry cites a newspaper account.",
      limits: "The entry supplies no ground plan or measured twist angles. The underlying report and the cause of the damage remain unverified.",
      sources: [phillipsEntry(535, 104, "Catalog entry citing the National Enquirer.")],
      traces: [{
        kind: "deformation",
        observation: "The reported cut heights increased from about 18 in to 6 ft. The account also describes twisting of trunks up to about 18 in thick.",
        sourceIds: ["phillips"],
        pattern: { label: "Reported twisted trunks and varying cut heights", families: ["twist"], basis: "description", details: "The locations of individual trees and the sense of twisting were unspecified." }
      }]
    },
    {
      id: "valea_popiliu",
      phillipsCaseNumber: 673,
      title: "Valea Popiliu",
      date: "1972-09-28",
      location: "Valea Popiliu, Prahova, Romania",
      summary: "The catalog relays a night watchman’s sighting and describes a reportedly scorched circle, a central hole, three radial ground marks and damaged corn at the presumed site.",
      limits: "Phillips cites an earlier published account. The reported radial mark length, circle diameter and center hole diameter leave the stated start and end positions inconsistent. The diagram shows the reported angles with approximate geometry.",
      sources: [phillipsEntry(673, 104, "Catalog entry citing UFOs from behind the Iron Curtain.")],
      traces: [
        {
          kind: "impression",
          observation: "The account describes a central hole about 14 cm wide and three tapering ground marks about 2.16 m long and 35 cm wide.",
          sourceIds: ["phillips"],
          pattern: { label: "Three reported radial marks at 120°", families: ["three_point", "radial"], basis: "dimensions", details: "The account describes threefold angular spacing. It gives no survey uncertainties or separately located endpoints." }
        },
        {
          kind: "scorching",
          observation: "The report describes scorched grass in a circular area about 5.82 m across.",
          sourceIds: ["phillips"],
          pattern: { label: "Reported circular scorched area", families: ["ring"], basis: "dimensions", details: "A single diameter cannot establish roundness or the distribution of scorching inside the area." }
        },
        {
          kind: "deformation",
          observation: "Corn stems near the site were reportedly bent or broken around 1 m above the ground.",
          sourceIds: ["phillips"]
        }
      ],
      diagram: {
        title: "Valea Popiliu reported radial marks and scorched area",
        basis: "Schematic from catalog dimensions and angles",
        note: "The outer boundary represents the stated scorch diameter. Dashed spokes show the reported directions, with endpoints and geographic orientation unresolved. The central hole symbol is enlarged.",
        viewBox: [-3.5, -3.5, 7, 7],
        layers: [
          {
            kind: "scorching", label: "Reported scorch outline",
            note: "The 5.82 m diameter describes the overall boundary. The source gives no pattern of scorching within it.", sourceIds: ["phillips"],
            marks: [{ type: "ellipse", x: 0, y: 0, rx: 2.91, ry: 2.91, estimated: true, label: "Nominal 5.82 metre scorch boundary" }]
          },
          {
            kind: "impression", label: "Hole and reported radial marks",
            note: "The account gives 120° separation. The dashed spokes depict angles, with exact positions and contact mechanism unresolved.", sourceIds: ["phillips"],
            marks: [
              { type: "point", x: 0, y: 0, estimated: true, label: "Reported central hole" },
              { type: "path", d: "M 0 -.4 V -2.6 M .346 .2 L 2.25 1.3 M -.346 .2 L -2.25 1.3", estimated: true, label: "Three reported directions separated by 120 degrees" }
            ]
          }
        ]
      }
    },
    {
      id: "junee",
      phillipsCaseNumber: 583,
      title: "Junee",
      date: "1973-06-03",
      location: "Junee, New South Wales, Australia",
      summary: "Phillips summarizes a newspaper account of lights seen near the ground and later findings of a lightly scorched area and holes outside it.",
      limits: "The catalog gives a nominal scorch diameter and approximate hole sizes. The count, bearings and spacing of the holes remain unspecified.",
      sources: [phillipsEntry(583, 108, "Catalog entry citing the Junee Southern Cross, June 6, 1973.")],
      traces: [
        {
          kind: "scorching", observation: "A circular patch about 15 ft (4.6 m) across reportedly appeared lightly scorched.", sourceIds: ["phillips"],
          pattern: { label: "Reported circular scorch patch", families: ["ring"], basis: "dimensions", details: "The account gives one diameter and no trace of variation around the boundary." }
        },
        {
          kind: "impression", observation: "Several holes about 4 in (10 cm) in diameter were reported outside the scorched area.", sourceIds: ["phillips"]
        }
      ]
    },
    {
      id: "hinsdale_reeds",
      phillipsCaseNumber: 753,
      title: "Hinsdale reed formation",
      date: "1973-07",
      location: "Hinsdale, New Hampshire, United States",
      summary: "Phillips lists a roughly circular formation in tall water reeds, attributed to Ray Fowler. The entry describes the reeds as swirled counterclockwise.",
      limits: "The entry gives July 1973 without a day and describes a trace discovery. It provides no stem-by-stem bearings or primary diagram.",
      sources: [phillipsEntry(753, 108, "Trace discovery attributed to Ray Fowler. The p marker indicates a photograph of the trace.")],
      traces: [{
        kind: "deformation",
        observation: "The reported area was about 20–30 ft (6–9 m) across, with the reeds packed tightly down near the center.",
        sourceIds: ["phillips"],
        pattern: { label: "Reported counterclockwise reed swirl", families: ["swirl"], handedness: "counterclockwise", basis: "description", details: "The account gives a direction and rough diameter range. Local directions and symmetry cannot be reconstructed from the entry." }
      }]
    },
    triangleDossier({
      id: "brasilia_dasilva", title: "Brasília, da Silva property", date: "1968", location: "Brasília, Brazil",
      number: 618, page: 75, locator: "Flying Saucer Review Case Histories 15, p. 6, via Fred Merritt.",
      summary: "In July or August 1968 a witness reported an object landing. Marks were later described at the reported spot.",
      detail: "The entry gives one side of 2.1 m and two of 1.2 m, forming a narrow isosceles layout.", sides: [2.1, 1.2, 1.2]
    }),
    triangleDossier({
      id: "la_criolla", title: "La Criolla", date: "1968-08-10", location: "La Criolla, Argentina",
      number: 708, page: 75, locator: "Flying Saucer Review Case Histories 13, p. 14.",
      summary: "The catalog describes a witness seeing an object on the ground and later finding three marks in the soil.",
      detail: "The entry gives sides of 2.28, 2.33 and 2.33 m. The short side differs by 5 cm from the other two.", sides: [2.28, 2.33, 2.33]
    }),
    triangleDossier({
      id: "lucerne_valley", title: "Lucerne Valley", date: "1971-11-13", location: "Lucerne Valley, California, United States",
      number: 496, page: 97, locator: "Catalog entry citing Data-Net.",
      summary: "After a reported sighting, three hunters returned at sunrise and found five round imprints. The catalog gives side lengths for a subset of three.",
      detail: "The three sides were reported as 14 ft, 14.4 ft and 10 ft. Two further marks were reportedly 10 ft away, with positions unspecified.",
      sides: [3.048, 4.2672, 4.38912]
    }),
    triangleDossier({
      id: "saint_matthias", title: "St. Matthias", date: "1974-10-06", location: "St. Matthias, Canada",
      number: 726, page: 111, locator: "APRO Bulletin Sep–Oct 1974, p. 1, and Canadian UFO Report 17.",
      summary: "Phillips describes three imprints, flattened and discolored grass, and a separate track leading toward a spring.",
      detail: "Three imprints reportedly measured 22 by 15 in each. The catalog gives 34 ft for each side of the triangle.",
      sides: [10.3632, 10.3632, 10.3632], sharedSpan: true,
      extraTraces: [
        { kind: "deformation", observation: "A straight flattened-grass track about 6 in wide was reported.", sourceIds: ["phillips"],
          pattern: { label: "Straight track toward a spring", families: ["rows"], basis: "description", details: "Track bearings relative to the imprints are unavailable." } },
        { kind: "surface", observation: "Discolored grass was reported at the location associated with the largest object.", sourceIds: ["phillips"] }
      ]
    }),
    triangleDossier({
      id: "lemon_grove", title: "Lemon Grove", date: "1973-11-16", location: "Lemon Grove, California, United States",
      number: 643, page: 115, locator: "Catalog entry citing Skylook.",
      summary: "A reported landing was followed by two square holes, a partial third mark and a circular pattern of dead grass.",
      detail: "Two holes were reportedly 6 ft 8 in apart. The partial third mark was described as forming an equilateral triangle with them.",
      sides: [2.032, 2.032, 2.032], sharedSpan: true,
      extraTraces: [{
        kind: "deformation", observation: "Dead grass reportedly lay in a counterclockwise circular pattern.", sourceIds: ["phillips"],
        pattern: { label: "Counterclockwise circular lay", families: ["swirl", "ring"], handedness: "counterclockwise",
          basis: "description", details: "The report gives a direction. The grass boundary and registration to the holes are unavailable." }
      }]
    }),
    {
      id: "langenburg_rings", phillipsCaseNumber: 746, title: "Langenburg", date: "1974-09-01", location: "Langenburg, Saskatchewan, Canada",
      summary: "Phillips’s investigation summary describes five vegetation rings arranged in a semicircle, with flattened grass in the bands and undisturbed centers.",
      limits: "The entry gives ring sizes and a shared direction. It supplies no center coordinates, band widths or separately measured orientations.",
      sources: [phillipsEntry(746, 122, "Phillips’s personal investigation.")],
      traces: [{
        kind: "deformation", observation: "Four rings were reported at 11 ft across and one at 8 ft. Flattening in the rings was described as clockwise.",
        sourceIds: ["phillips"],
        pattern: { label: "Five rings with clockwise grass lay", families: ["ring", "swirl"], handedness: "clockwise",
          basis: "dimensions", details: "The reported sizes apply to the boundaries. The relative placements and band widths cannot be reconstructed from the catalog." }
      }],
      diagram: {
        title: "Langenburg nominal outline of one of four larger rings",
        basis: "Single-ring schematic from reported diameter",
        note: "The circle represents one reported 11 ft outer boundary. The four other rings have no plotted coordinates, and internal blade directions are described in the notes.",
        viewBox: [-2.1, -2.1, 4.2, 4.2],
        layers: [{ kind: "deformation", label: "Nominal outer boundary", note: "Clockwise flattening was reported within the band.", sourceIds: ["phillips"],
          marks: [{ type: "ellipse", x: 0, y: 0, rx: 1.6764, ry: 1.6764, estimated: true, label: "Nominal 11 ft ring boundary" }] }]
      }
    }
  ];
});
