(function (root, factory) {
  "use strict";

  const cases = factory();
  if (typeof module === "object" && module && module.exports) {
    module.exports = cases;
  }
  if (root) {
    root.UfoLandingSiteCases = cases;
  }
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";

  // One entry per site event. Keep observations and geometry tied to their individual traces.
  return [
    {
      id: "socorro",
      title: "Socorro",
      date: "1964-04-24",
      location: "Socorro, New Mexico, United States",
      summary: "Police officer Lonnie Zamora reported seeing an object on the ground and then watching it lift off with a flame. Investigators surveyed impressions and burned vegetation that evening.",
      limits: "Zamora described two apparent legs. The investigators' four large depressions, smaller round marks and burned patches are separate observations whose origins remain uncertain.",
      controls: "The FBI memo records patches of unburned grass among the burned clumps. This is an on-site contrast, with no matched burn reconstruction in that memo.",
      sources: [
        {
          id: "blue-book",
          label: "U.S. Air Force Project Blue Book, case 8766",
          url: "https://catalog.archives.gov/id/302532129?objectPage=57",
          locator: "National Archives record 302532129, images 56–57, site plans of burns and impressions."
        },
        {
          id: "fbi",
          label: "FBI Albuquerque field office memoranda",
          url: "https://documents2.theblackvault.com/documents/fbifiles/paranormal/FBI-UFO-Socorro-fbi1.pdf",
          locator: "May 8, 1964, Byrnes's site observations, printed pp. 1–2, and Zamora interview, printed p. 3."
        },
        {
          id: "site-plans",
          label: "Site plans reproduced in the FBI file",
          url: "https://documents2.theblackvault.com/documents/fbifiles/paranormal/FBI-UFO-Socorro-fbi1.pdf#page=26",
          locator: "Scan pp. 26–27, surveyed impression dimensions and separate burn locations."
        },
        {
          id: "burn-plan",
          label: "FBI file, combined impression and burn plan",
          url: "https://documents2.theblackvault.com/documents/fbifiles/paranormal/FBI-UFO-Socorro-fbi1.pdf#page=27",
          locator: "Scan p. 27."
        }
      ],
      diagram: {
        title: "Socorro impression and scorch locations",
        basis: "Redrawn from the investigators’ combined sketch",
        note: "Positions were read from the same sketch and rotated for display. Symbols mark approximate locations. Use the separate measurement sketch for distances. The three smaller round marks have no secure plotted positions here.",
        viewBox: [0, 0, 86, 51],
        layers: [
          {
            kind: "impression",
            label: "Possible support impressions",
            note: "The four large impressions form an uneven quadrilateral. The separately surveyed opposite sides differ in length.",
            sourceIds: ["site-plans", "burn-plan"],
            // Centers picked from the 110 dpi scan. Plot x = (1160 − scan y)/10; y = (scan x − 135)/10.
            marks: [
              { type: "point", x: 9.7, y: 4.2, tag: "A", label: "Large impression A" },
              { type: "point", x: 54.5, y: 3.7, tag: "B", label: "Large impression B" },
              { type: "point", x: 73, y: 45.4, tag: "C", label: "Large impression C" },
              { type: "point", x: 2, y: 42.6, tag: "D", label: "Large impression D" }
            ]
          },
          {
            kind: "scorching",
            label: "Scorch marks",
            note: "Three burned patches lie inside the impression perimeter and one lies outside. The recorded patches do not form a matching four-corner pattern.",
            sourceIds: ["burn-plan"],
            marks: [
              { type: "point", x: 24.9, y: 19.2, tag: "1", label: "Inner burn patch 1" },
              { type: "point", x: 31.5, y: 36.3, tag: "2", label: "Inner burn patch 2" },
              { type: "point", x: 49.1, y: 39.6, tag: "3", label: "Inner burn patch 3" },
              { type: "point", x: 77.3, y: 6.7, tag: "4", label: "Outer burn patch 4" }
            ]
          }
        ]
      },
      traces: [
        {
          kind: "impression",
          observation: "Agent Byrnes described four roughly rectangular depressions, about 16 × 6 in (41 × 15 cm) and 2 in (5 cm) deep, with soil pushed toward the far side.",
          context: "The depressions appeared angled outward from a center line. Angled supports are one possible reading of the shape.",
          sourceIds: ["blue-book", "fbi", "site-plans"],
          pattern: {
            label: "Uneven four-point layout",
            families: ["four_point", "irregular"],
            basis: "dimensions",
            details: "The survey records four unequal perimeter lengths, in clockwise order from the upper-left corner of the plan. Their differences rule out a square or rectangle at the reported precision.",
            edgesM: [2.934, 3.620, 4.509, 4.026]
          }
        },
        {
          kind: "impression",
          observation: "Byrnes also recorded three smooth circular marks about 4 in (10 cm) wide and ⅛ in (3 mm) deep.",
          context: "These shallow marks were described separately from the four large depressions. Their origin is unknown.",
          sourceIds: ["fbi"]
        },
        {
          kind: "scorching",
          observation: "Byrnes recorded three burned patches within the group of large depressions and one outside. Other clumps of grass remained undisturbed.",
          sourceIds: ["blue-book", "fbi", "site-plans"],
          pattern: {
            label: "Separated burn patches",
            families: ["four_point", "irregular"],
            basis: "description",
            details: "The plan places two patches toward one edge of the impression perimeter, a third farther inward and the fourth beyond a corner. The pattern leaves the number and positions of heat sources undetermined."
          }
        }
      ]
    },
    {
      id: "valensole",
      title: "Valensole",
      date: "1965-07-01",
      location: "Valensole, Alpes-de-Haute-Provence, France",
      summary: "A lavender farmer reported a landed object and then found a ground disturbance in the field. The gendarmerie examined the site and took measurements and photographs.",
      limits: "Visitors trampled the area before the formal July 3 survey. The witness described a star-like trace, and the gendarmerie documented a rough cross with no measured inter-arm angles.",
      sources: [
        {
          id: "geipan",
          label: "CNES / GEIPAN Valensole case file",
          url: "https://www.cnes-geipan.fr/fr/cas/1965-07-00050",
          locator: "Case 1965-07-00050, gendarmerie chronology and procès-verbal no. 445."
        },
        {
          id: "survey",
          label: "Gendarmerie survey of the Valensole ground trace",
          url: "https://www.cnes-geipan.fr/sites/default/files/PV%20n%C2%B0445%20%281965309761%29.pdf#page=6",
          locator: "Procès-verbal no. 105 in the case dossier, PDF pp. 6, 9 and 13–14."
        }
      ],
      diagram: {
        title: "Valensole central hole, shallow basin, and four furrows",
        basis: "Recorded dimensions and approximate sketch directions",
        note: "The hole and basin use reported diameters. The four arms show the approximate directions in the police sketch and the reported length of about 2 m each. Exact arm endpoints and angles were unmeasured.",
        viewBox: [-220, -215, 440, 430],
        layers: [
          {
            kind: "impression",
            label: "Hole, basin and furrows",
            note: "Four shallow furrows formed a rough cross around a single hole. The sketch gives a central arrangement with insufficient precision to test quarter-turn symmetry.",
            sourceIds: ["survey"],
            marks: [
              { type: "ellipse", x: 0, y: 0, rx: 60, ry: 60, estimated: true, label: "Shallow basin about 1.20 metres across" },
              { type: "ellipse", x: 0, y: 0, rx: 9, ry: 9, label: "Central hole about 18 centimetres across" },
              { type: "path", d: "M -5 -9 L -98 -174 M 8 -6 L 156 -126 M 4 9 L 80 184 M -9 5 L -172 102", estimated: true, label: "Four furrows with approximate directions" }
            ]
          }
        ]
      },
      traces: [
        {
          kind: "impression",
          observation: "The farmer described a star-like ground trace with a cylindrical hole in the center. He said the soil was initially sodden and later hardened.",
          context: "The gendarmerie recorded a shallow basin about 1.20 m across, a central hole about 18 cm wide and 40 cm deep, and four shallow furrows roughly 8 cm wide and 2 m long.",
          sourceIds: ["geipan", "survey"],
          pattern: {
            label: "Four furrows around a central hole",
            families: ["four_point", "radial"],
            basis: "dimensions",
            details: "The similar reported lengths give a rough radial pattern. The survey gives too little angular detail to assess rotational symmetry."
          }
        }
      ]
    },
    {
      id: "tully",
      title: "Horseshoe Lagoon",
      date: "1966-01-19",
      location: "Near Tully, Queensland, Australia",
      summary: "George Pedley reported seeing an object rise near the lagoon. Police inspected the flattened reeds the next morning and later sent a grass sample to the Royal Australian Air Force.",
      limits: "The inspection establishes the formation's presence after the sighting. Its time of formation and relationship to the reported object are uncertain.",
      controls: "The RAAF considered small waterspouts. Department of Air correspondence separately reports that residents had seen similar formations in the wet season and summarizes a university examination of vegetation samples.",
      sources: [
        {
          id: "raaf",
          label: "Royal Australian Air Force correspondence and police questionnaire",
          url: "https://documents.theblackvault.com/documents/ufos/australia/A703_580-1-1_Part%205_645646.pdf#page=167",
          locator: "National Archives of Australia item 645646, A703, 580/1/1 Part 5, scan pp. 165–167 and 183."
        },
        {
          id: "mat-photo",
          label: "Tully Studio photo of the main reed mat",
          url: "https://documents.theblackvault.com/documents/ufos/australia/A703_580-1-1_Part%205_645646.pdf#page=170",
          locator: "Townsville Daily Bulletin, January 21, 1966, clipping preserved in the RAAF file."
        },
        {
          id: "ufoic-plan",
          label: "UFOIC main reed mat photograph and Horseshoe Lagoon sketch",
          url: "https://files.afu.se/Downloads/Magazines/Australia/Australian%20Flying%20Saucer%20Review/Australian%20Flying%20Saucer%20Review%20-%201966%2011%20-%20no%209%20UFOIC.pdf#page=17",
          locator: "Australian Flying Saucer Review No. 9, November 1966, pp. 16–17. Photograph and caption p. 16, lagoon sketch and clipped patch dimensions p. 17."
        }
      ],
      diagram: {
        title: "Horseshoe Lagoon main reed mat and adjacent clipped patch",
        basis: "Reported spans and a relative direction from the lagoon sketch",
        note: "North is up. The main outline uses the police questionnaire’s approximate 32 × 25 ft spans. Its long-axis bearing and the clipped patch’s orientation are schematic. The photograph is oblique and individual reed paths are unplotted.",
        viewBox: [0, -360, 1250, 1290],
        layers: [
          {
            kind: "deformation",
            label: "Flattened and curved reeds",
            note: "The reported length was about 1.28 times the width. The outline describes elongation. The witness and police record give too little information to assess symmetry in the reed lay.",
            sourceIds: ["raaf", "mat-photo"],
            marks: [{ type: "ellipse", x: 625, y: 465, rx: 487.5, ry: 381, estimated: true, label: "Approximate envelope of the flattened reeds" }]
          },
          {
            kind: "deformation",
            label: "Separate clipped and uprooted grass patch",
            note: "The UFOIC drawing places the clipped patch approximately north of the main mat. Its account estimates a 5 × 6 ft area and roughly 6 ft between it and the main mat edge.",
            sourceIds: ["ufoic-plan"],
            marks: [{ type: "path", d: "M 549 -282 H 701 V -99 H 549 Z", estimated: true, label: "Approximate clipped grass patch" }]
          }
        ]
      },
      traces: [
        {
          kind: "deformation",
          observation: "Reeds were flattened in curved strands down to the water surface, with an approximately 32 × 25 ft (9.75 × 7.62 m) boundary.",
          context: "The witness reported seeing no scorch marks and detecting no burning smell. UFOIC labels the main mat clockwise in the photo caption and sketch. The typed-over direction in the police questionnaire is ambiguous.",
          sourceIds: ["raaf", "ufoic-plan"],
          pattern: {
            label: "Curved reeds in an elongated patch",
            families: ["oval", "swirl"], handedness: "uncertain",
            basis: "dimensions",
            details: "The rough outline dimensions differ. They describe the patch envelope and leave local reed angles and the precision of the boundary undetermined.",
            dimensions: { longM: 9.75, shortM: 7.62 }
          }
        },
        {
          kind: "deformation",
          observation: "The contemporary UFOIC account describes an adjacent rectangular patch, roughly 5 × 6 ft, where grass was clipped at the water line and removed with roots and muddy soil.",
          context: "The lagoon sketch places it north of the main mat. Timing and formation mechanism are uncertain.",
          sourceIds: ["ufoic-plan"]
        }
      ]
    },
    {
      id: "delphos",
      title: "Delphos",
      date: "1971-11-02",
      location: "Delphos, Kansas, United States",
      summary: "Ronald Johnson described a glowing object hovering close to the ground. An undersheriff examined and sampled a pale soil ring the following day.",
      limits: "Johnson reported hovering. The ring's appearance, later soil comparisons and nearby broken vegetation leave their date of formation and causes open.",
      controls: "Enlow contrasted the dry ring with muddy soil inside and outside it. Phillips sampled inside the ring band and from the surrounding soil a month later and compared how those areas absorbed water.",
      sources: [
        {
          id: "phillips",
          label: "Ted Phillips, Delphos investigation and Enlow's report",
          url: "https://projectaquarius.mufon.com/wp-content/uploads/2023/09/December_November_1985.pdf#page=194",
          locator: "MUFON UFO Journal no. 209 (September 1985), printed pp. 9, 12 and 14, including the November 3 undersheriff's statement and later measurements."
        },
        {
          id: "bearings",
          label: "Ted Phillips, measurements around the Delphos ring",
          url: "https://projectaquarius.mufon.com/wp-content/uploads/2023/09/December_November_1985.pdf#page=193",
          locator: "Printed p. 13, distances and bearings from the ring center."
        }
      ],
      diagram: {
        title: "Delphos ring and nearby tree damage",
        basis: "Positions from field bearings and distances",
        note: "North is up. Tree markers use the investigator’s bearings from the ring center. The dashed arc gives the nominal 8 ft diameter. The sketch represents the western break schematically because its extent was unmeasured.",
        viewBox: [-420, -190, 820, 670],
        layers: [
          {
            kind: "surface",
            label: "Soil ring and discoloration",
            note: "The pale band varied in width and had an interruption to the west. The two nearby trees with slight discoloration were both reported about 5 ft from the center.",
            sourceIds: ["phillips", "bearings"],
            marks: [
              { type: "path", d: "M -112 -48 A 122 122 0 1 1 -112 48", estimated: true, label: "Nominal ring outline with schematic western break" },
              { type: "point", x: -87.4, y: -124.8, tag: "C1", label: "Tree with slight discoloration, bearing 325 degrees" },
              { type: "point", x: 87.4, y: -124.8, tag: "C2", label: "Tree with slight discoloration, bearing 35 degrees" }
            ]
          },
          {
            kind: "deformation",
            label: "Broken vegetation",
            note: "The two plotted break locations have different bearings and distances. The source leaves the timing and cause of the breaks uncertain.",
            sourceIds: ["bearings"],
            marks: [
              { type: "point", x: 279.7, y: 399.5, tag: "B1", label: "Broken dead tree, bearing 145 degrees" },
              { type: "point", x: -330.2, y: 58.2, tag: "B2", label: "Tree with broken limb, bearing 260 degrees" }
            ]
          }
        ]
      },
      traces: [
        {
          kind: "surface",
          observation: "The undersheriff reported a dry, pale soil ring surrounded by mud, with mud also in the center. Reporter Thaddia Smith estimated an overall diameter of about 8 ft (2.4 m).",
          context: "Phillips reported poor water infiltration in the ring band on later visits. The pale soil and drying were observations, with heating or other causes unresolved.",
          sourceIds: ["phillips"],
          pattern: {
            label: "Irregular ring of soil discoloration",
            families: ["ring", "irregular"],
            basis: "dimensions",
            details: "Smith estimated the pale band at about 1 ft (0.3 m) wide. Phillips later recorded widths from about 12 in to more than 20 in (30 to more than 51 cm), with the widest band on the east side and a gap in the pale material and drying to the west."
          }
        },
        {
          kind: "deformation",
          observation: "Enlow reported broken tree limbs and a broken dead tree nearby. Phillips later recorded the positions of several trees and the broken limb.",
          context: "The age and cause of the tree damage are uncertain.",
          sourceIds: ["phillips"]
        },
        {
          kind: "surface",
          observation: "Phillips reported slight discoloration on the ring-facing sides of two trees about 5 ft from the ring center.",
          context: "The field description leaves the cause of the color change open.",
          sourceIds: ["bearings"]
        }
      ]
    },
    {
      id: "trans_provence",
      title: "Trans-en-Provence",
      date: "1981-01-08",
      location: "Trans-en-Provence, Var, France",
      summary: "A resident reported a brief landing. The gendarmerie examined a ring on a hard-packed terrace the next day, and GEPAN followed up with site measurements and laboratory work.",
      limits: "The witness's sketch of circular features under the reported object is separate from the surveyed ground trace. The soil and plant analyses constrain some possible effects while leaving the origin open.",
      controls: "GEPAN compared ring soil with a sample taken roughly 3–4 m away and sampled vegetation at several distances. Sample locations and dates differed, and the initial condition of the ring soil and plants was unknown.",
      sources: [
        {
          id: "technical-note",
          label: "GEPAN Technical Note 16, Analysis of a trace",
          url: "https://www.cnes-geipan.fr/sites/default/files/Note%20techn16-R.pdf",
          locator: "Printed pp. 27–33, trace measurements, sketch 7 and sampling plan. Sections 6–8, laboratory analyses and synthesis."
        },
        {
          id: "geipan",
          label: "CNES / GEIPAN Trans-en-Provence case file",
          url: "https://www.cnes-geipan.fr/en/node/48918",
          locator: "Case summary, technical note, photographs, gendarmerie record and laboratory annexes."
        },
        {
          id: "sketch",
          label: "Gendarmerie sketch of the ground trace",
          url: "https://www.cnes-geipan.fr/sites/default/files/Note%20techn16-R.pdf#page=29",
          locator: "Technical Note 16, sketch 7, printed p. 28."
        }
      ],
      diagram: {
        title: "Trans-en-Provence ground ring and striated sectors",
        basis: "Redrawn from Gendarmerie sketch 7",
        note: "The diagram keeps the sketch’s relative orientation and the reported 2.20 m and 2.40 m ring diameters. The highlighted arcs show the two marked sectors. Later descriptions differ.",
        viewBox: [0, 0, 310, 275],
        layers: [
          {
            kind: "impression",
            label: "Ground ring and striations",
            note: "The two highlighted sectors are approximately opposite. This describes a half-turn relationship between the recorded sectors, with individual support positions undetermined.",
            sourceIds: ["sketch"],
            marks: [
              { type: "ellipse", x: 155, y: 137, rx: 110, ry: 110, estimated: true, label: "Inner boundary, about 2.20 metres in diameter" },
              { type: "ellipse", x: 155, y: 137, rx: 120, ry: 120, estimated: true, label: "Outer boundary, about 2.40 metres in diameter" },
              { type: "path", d: "M 55.4 79.5 A 115 115 0 0 1 115.7 28.9", label: "First striated sector, about 0.80 metres long" },
              { type: "path", d: "M 254.6 194.5 A 115 115 0 0 1 194.3 245.1", label: "Opposite striated sector, about 0.80 metres long" }
            ]
          }
        ]
      },
      traces: [
        {
          kind: "impression",
          observation: "The gendarmerie measured two concentric boundaries of about 2.20 and 2.40 m across. GEPAN later described compacted soil and areas with surface abrasion.",
          context: "The surveyed shape was a narrow band of disturbed ground. Individual support positions could not be identified from this geometry.",
          sourceIds: ["technical-note", "geipan"],
          pattern: {
            label: "Concentric ring with opposed striated sectors",
            families: ["ring", "opposed"],
            basis: "dimensions",
            details: "The gendarmerie mapped two approximately 0.80 m striated sectors on opposite sides of a roughly 10 cm wide ring. This suggests approximate half-turn symmetry in the position of the two sectors. A later investigator described a horseshoe-like trace."
          }
        },
        {
          kind: "surface",
          observation: "Laboratories reported iron-bearing material and dark residue in samples from the ring. The case summary says the dark material could include combustion residue.",
          context: "GEPAN inferred heating from laboratory evidence. A heat source, RF exposure and positions of individual heated patches were not established.",
          sourceIds: ["technical-note", "geipan"]
        },
        {
          kind: "surface",
          observation: "An INRA laboratory reported biochemical differences in wild alfalfa samples that varied with distance from the trace.",
          context: "This was a comparison across sampled locations. The measurements leave the cause of the plant differences undetermined.",
          sourceIds: ["technical-note", "geipan"]
        }
      ]
    }
  ];
});
