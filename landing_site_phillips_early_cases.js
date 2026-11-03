(function (root, factory) {
  "use strict";

  const cases = factory();
  if (typeof module === "object" && module && module.exports) {
    module.exports = cases;
  }
  root.UfoLandingSitePhillipsEarlyCases = cases;
})(globalThis, function () {
  "use strict";

  const feet = (value) => value * 0.3048;
  const inches = (value) => value * 0.0254;
  const phillips = (caseNumber, page, attribution) => [{
    id: "phillips",
    label: "Ted Phillips, Physical Traces Associated with UFO Sightings",
    url: "https://cufos.org/PDFs/books/Physical_Traces.pdf#page=" + page,
    locator: "Case " + caseNumber + ", printed p. " + (page - 18) + ". " + attribution
  }];

  function point(x, y, label, tag) {
    return { type: "point", x, y, label, tag, estimated: true };
  }

  function circle(x, y, radius, label) {
    return { type: "ellipse", x, y, rx: radius, ry: radius, label, estimated: true };
  }

  function square(side, label) {
    const half = side / 2;
    return { type: "path", d: "M " + (-half) + " " + (-half) + " h " + side +
      " v " + side + " h " + (-side) + " Z", label, estimated: true };
  }

  function triangle(base, leg, label) {
    const half = base / 2;
    return [
      point(-half, 0, label + " A", "A"),
      point(half, 0, label + " B", "B"),
      point(0, -Math.sqrt(leg ** 2 - half ** 2), label + " C", "C")
    ];
  }

  const stirumBase = feet(26);
  const stirumLeg = feet(21.5);
  const tucumanRadius = feet(6);
  const tucumanOffset = tucumanRadius + inches(8);

  return [
    {
      id: "la_madera_1964",
      phillipsCaseNumber: 168,
      inventoryIds: ["hatch:Hatch_UDB_6933"],
      evidenceOrigin: "original",
      title: "La Madera",
      date: "1964-04-26",
      location: "Near La Madera, New Mexico, United States",
      summary: "Police examined a smoldering patch after Orlando Gallegos reported a luminous object near a road and dumping area. APRO interviewed the witness and the state police captain who visited the site.",
      limits: "The captain described four indentations, while the witness described two. The photographs reviewed by APRO did not resolve their layout. The Air Force file attributed the fire to burning refuse.",
      sources: [
        ...phillips(168, 48, "Later compilation of the police and APRO account."),
        { id: "apro", label: "APRO Bulletin, Incident at La Madera",
          url: "https://noufors.com/Documents/Books%2C%20Manuals%20and%20Published%20Papers/Specialty%20UFO%20Publications/A.P.R.O.%20Bulletin/apro_july_1964.pdf#page=6",
          locator: "July 1964, printed pp. 4 and 6. Lorenzen's interviews with Captain Vigil and Gallegos." },
        { id: "bluebook", label: "U.S. Air Force, La Madera investigation",
          url: "https://catalog.archives.gov/id/302532310",
          locator: "Project Blue Book record card and April 27, 1964 report extract." }
      ],
      traces: [
        { kind: "impression", observation: "Vigil described four wedge-bottomed depressions about 8 by 12 in and at least a dozen smaller round marks. Gallegos said he saw two wedge-shaped impressions.",
          sourceIds: ["apro"], pattern: { label: "Conflicting impression counts", basis: "description", details: "The reports give individual mark sizes without positions, spacing or orientation." } },
        { kind: "scorching", observation: "Vigil gave a diameter of 35–40 ft (10.7–12.2 m) for the scorched and smoldering area.",
          sourceIds: ["apro", "bluebook"], pattern: { label: "Reported burn extent", basis: "dimensions", families: ["ring"], details: "The diameter supports a nominal circular envelope. The field record gives no surveyed boundary." } }
      ],
      diagram: {
        title: "La Madera reported scorch extent",
        viewBox: [-7, -7, 14, 14],
        basis: "Nominal diameter bounds from the state police interview",
        note: "The two outlines bracket a single reported burned area. The locations of the depressions and smaller marks are undetermined.",
        layers: [{ kind: "scorching", label: "Scorch diameter bounds", note: "Nominal diameters of 35 and 40 ft, in local metres.", sourceIds: ["apro"],
          marks: [circle(0, 0, feet(17.5), "35 ft diameter"), circle(0, 0, feet(20), "40 ft diameter")] }]
      }
    },
    {
      id: "hubbard_wheat_1964",
      phillipsCaseNumber: 172,
      evidenceOrigin: "original",
      title: "Hubbard wheat field",
      date: "1964-05-18",
      location: "Hubbard, Oregon, United States",
      summary: "A deputy sheriff and the first adult at the site described crushed wheat after a boy's sighting. The deputy reported three localized spots about three feet apart.",
      limits: "The first published investigation reports crushed wheat, with no surveyed soil impressions or bearings. The spot count and spacing describe the vegetation observations. The reported object was described with four legs.",
      sources: [
        ...phillips(172, 48, "Catalog entry citing NICAP."),
        { id: "nicap", label: "NICAP, Physical Evidence: Landing Reports",
          url: "https://cufos.org/PDFs/UFOI_and_Selected_Documents/UFOI/023%20JUL-AUG%201964.pdf#page=6",
          locator: "UFO Investigator 2(11), July–August 1964, PDF p. 6. Deputy Sheriff Davidson and Ray Mortensen accounts." }
      ],
      traces: [
        { kind: "deformation", observation: "The deputy described three areas of crushed wheat about 3 ft (0.91 m) apart.",
          sourceIds: ["nicap"], pattern: { label: "Three vegetation spots", basis: "dimensions", families: ["three_point"], details: "One approximate spacing is reported. A nominal equal-sided rendering assumes it applies to all three pairs." } },
        { kind: "deformation", observation: "Mortensen described the flattened wheat as splayed outward in several directions.",
          sourceIds: ["nicap"], pattern: { label: "Outward flattened wheat", basis: "description", families: ["radial"], details: "The account describes radial lay. It supplies no measured angles or independent twist direction." } }
      ],
      diagram: {
        title: "Hubbard nominal positions of the three crushed-wheat spots",
        viewBox: [-0.65, -0.97, 1.30, 1.18],
        basis: "Illustration using the deputy's approximate shared spacing",
        note: "Local metres. The diagram assumes all three distances are approximately 3 ft. Individual spot outlines and the wider flattened area are undetermined.",
        layers: [{ kind: "deformation", label: "Three reported vegetation spots", note: "The marks represent crushed wheat.", sourceIds: ["nicap"],
          marks: triangle(feet(3), feet(3), "Crushed wheat spot") }]
      }
    },
    {
      id: "dale_englebrecht",
      phillipsCaseNumber: 173,
      inventoryIds: ["ufocat:214890"],
      evidenceOrigin: "original",
      title: "Dale farmyard",
      date: "1964-06",
      location: "Near Dale, Indiana, United States",
      summary: "William T. Powers drew a small irregular burn and three shallow indentations after interviewing Charles Englebrecht. The later field history separately describes swirled grass around the affected patch.",
      limits: "The preliminary NICAP bulletin and later follow-up presentation date the report to June 14. A separately reproduced NICAP account gives June 24. The sources describe the same witness and farm. The published trace drawing omits the grass boundary and stem orientation.",
      sources: [
        ...phillips(173, 49, "Catalog summary of the Dale traces."),
        { id: "powers", label: "William T. Powers, burn and indentation field sketch",
          url: "https://www.iccra.org/reports/ICCRA%20pdf%20reports/Dale%2C%20IN%201964%20for%202010%20ICCRA%20Conference_v%20website.pdf#page=14",
          locator: "PDF p. 14. Reproduced drawing signed WTP, with a Dale News photograph alongside." },
        { id: "interviews", label: "Dale historical witness and investigator follow-up",
          url: "https://www.iccra.org/reports/ICCRA%20pdf%20reports/Dale%2C%20IN%201964%20for%202010%20ICCRA%20Conference_v%20website.pdf#page=10",
          locator: "PDF pp. 10–12 describe witness recollections and the samples collected. PDF p. 17 reproduces the NICAP account." },
        { id: "nicap", label: "NICAP, contemporary Dale account",
          url: "https://cufos.org/PDFs/UFOI_and_Selected_Documents/UFOI/023%20JUL-AUG%201964.pdf#page=6",
          locator: "UFO Investigator 2(11), PDF p. 6. Names Englebrecht, gives June 14 and reports scorch samples." }
      ],
      traces: [
        { kind: "impression", observation: "Powers plotted three indentations near the boundary of a small burned patch.",
          sourceIds: ["powers"], pattern: { label: "Unequal three-point layout", basis: "dimensions", families: ["three_point"], details: "Two sides are similar in the drawing and the remaining side is shorter. The sketch gives no measurement uncertainty." } },
        { kind: "scorching", observation: "The field drawing outlines an irregular burned patch with annotated spans of about 3 by 4 in.",
          sourceIds: ["powers"], pattern: { label: "Irregular small burn", basis: "dimensions", families: ["irregular"], details: "These dimensions describe the drawn patch. Later recollections describe a larger affected area.",
            dimensions: { longM: inches(4), shortM: inches(3) } } },
        { kind: "deformation", observation: "The historical follow-up describes a flattened, swirled grass circle about 5–6 ft across.",
          sourceIds: ["interviews"], pattern: { label: "Reported grass swirl", basis: "dimensions", families: ["ring", "swirl"], details: "The published field drawing does not register the grass to the small burn and depressions. The direction was not reported." } }
      ],
      diagram: {
        title: "Dale burn and indentation sketch",
        viewBox: [-12, -12, 226, 310],
        basis: "Relative positions redrawn from Powers's field sketch",
        note: "The sketch has north upward. Outlines follow the field drawing approximately. The wider grass report has no independently plotted boundary.",
        layers: [
          { kind: "impression", label: "Three indentations", note: "Markers use the approximate centers of the three numbered marks in the original sketch.", sourceIds: ["powers"],
            marks: [point(189, 22, "Indentation 1", "1"), point(96, 272, "Indentation 2", "2"), point(31, 202, "Indentation 3", "3")] },
          { kind: "scorching", label: "Burned patch", note: "The irregular perimeter is taken from the same sketch as the indentations.", sourceIds: ["powers"],
            marks: [{ type: "path", d: "M 12 47 Q 8 20 39 15 L 110 9 Q 158 2 182 27 Q 176 81 168 121 L 154 195 Q 143 252 122 264 Q 103 275 84 263 Q 53 240 33 197 L 19 131 Q 9 80 12 47 Z", label: "Approximate burn outline", estimated: true }] }
        ]
      }
    },
    {
      id: "presque_isle_1966",
      phillipsCaseNumber: 244,
      inventoryIds: ["hatch:Hatch_UDB_7752"],
      evidenceOrigin: "original",
      title: "Presque Isle State Park",
      date: "1966-07-31",
      location: "Presque Isle State Park, Pennsylvania, United States",
      summary: "Air Force and police investigators photographed two larger triangular depressions and noted a smaller mark in beach sand. The Flight Dynamics Laboratory compared the photographs with the field sketch.",
      limits: "The photographs contradicted the sketch's footprint orientations. The engineering review found the pattern asymmetric and considered it unlikely to have served as landing supports. The marks were found away from the point where a witness reported the object settling.",
      controls: "Police took a plaster cast. The laboratory traced an acrylic residue to the lacquer applied before casting. The case file reports no evidence of heat blast.",
      sources: [
        ...phillips(244, 61, "Catalog entry for the beach traces."),
        { id: "engineering", label: "U.S. Air Force, evaluation of beach depressions",
          url: "https://documents2.theblackvault.com/documents/projectbluebook/PresqueIslandStatePark-Pennsylvania-07-31-1966-main.pdf#page=77",
          locator: "Project Blue Book case file, PDF pp. 76–77. Flight Dynamics Laboratory photograph and sketch comparison." },
        { id: "memo", label: "Project Blue Book field evidence and spacing memo",
          url: "https://documents2.theblackvault.com/documents/projectbluebook/PresqueIslandStatePark-Pennsylvania-07-31-1966-main.pdf#page=96",
          locator: "PDF pp. 89, 91–92 and 96. Field evidence, sand analysis summary and reported spacing." }
      ],
      traces: [
        { kind: "impression", observation: "The file describes two larger triangular depressions and a smaller third depression. A memo reports 16 ft between the larger marks.",
          sourceIds: ["engineering", "memo"], pattern: { label: "Asymmetric three-mark group", basis: "dimensions", families: ["three_point", "irregular"], details: "The large pair has one reported spacing. The footprint axes in the photograph do not converge symmetrically, and the remaining position lacks measured registration." } }
      ],
      diagram: {
        title: "Presque Isle reported spacing of two larger depressions",
        viewBox: [-3.2, -1.5, 6.4, 3],
        basis: "One reported distance from the Air Force memo",
        note: "Local metres. Only the reported 16 ft spacing is represented. Markers omit the disputed footprint orientation and the unmeasured third position.",
        layers: [{ kind: "impression", label: "Larger depression pair", note: "The drawn baseline represents the reported spacing, with arbitrary orientation.", sourceIds: ["memo", "engineering"],
          marks: [point(-feet(8), 0, "Larger depression A", "A"), point(feet(8), 0, "Larger depression B", "B")] }]
      }
    },
    {
      id: "hampton_falls_1966",
      phillipsCaseNumber: 754,
      evidenceOrigin: "original",
      title: "Hampton Falls",
      date: "1966-03-29",
      location: "Hampton Falls, New Hampshire, United States",
      summary: "A boy and his mother described an approximately circular depression in pine litter and elongated impressions around it. Raymond Fowler's field investigation was conducted several years after the event.",
      limits: "The impressions were reported outside the circular depression. The published narrative gives no bearings or spacings for individual marks. Clockwise rotation in the account concerns the reported object.",
      sources: [
        ...phillips(754, 59, "Catalog trace account."),
        { id: "fowler", label: "Raymond Fowler, The Flying Box, and Other Cases",
          url: "https://cufos.org/PDFs/IUR%20issues/IUR%20Vol.%2028%20No.%202%20Summer%202003.pdf#page=17",
          locator: "International UFO Reporter 28(2), Summer 2003, p. 17. Witness and family observations of the traces." },
        { id: "nicap", label: "NICAP Massachusetts Subcommittee investigation",
          url: "https://noufors.com/Documents/Books%2C%20Manuals%20and%20Published%20Papers/Specialty%20UFO%20Publications/NICAP%20UFO%20Investigator/072%20MARCH%201972.pdf#page=3",
          locator: "UFO Investigator, March 1972, p. 3. First published field investigation summary." }
      ],
      traces: [
        { kind: "impression", observation: "The witness and his mother recalled elongated impressions outside the central depression.",
          sourceIds: ["fowler", "phillips"], pattern: { label: "Three reported marks around a depression", basis: "description", families: ["three_point"], details: "Phillips gives the count. Distances and orientations for individual impressions are missing." } },
        { kind: "surface", observation: "The central bowl-like patch through the pine litter was described as roughly 2 ft across and 4–6 in deep at the center.",
          sourceIds: ["fowler"], pattern: { label: "Circular central disturbance", basis: "dimensions", families: ["ring"], details: "The witnesses described displacement of litter and soil. They reported no scorching." } }
      ],
      diagram: {
        title: "Hampton Falls central surface disturbance",
        viewBox: [-0.42, -0.42, 0.84, 0.84],
        basis: "Schematic from the reported central diameter",
        note: "Local metres. The elongated impressions are omitted because individual positions were not reported.",
        layers: [{ kind: "surface", label: "Central bowl-like depression", note: "The perimeter uses the approximate two-foot diameter.", sourceIds: ["fowler"],
          marks: [circle(0, 0, feet(1), "Approximate circular depression")] }]
      }
    },
    {
      id: "villares_del_saz",
      phillipsCaseNumber: 54,
      title: "Villares del Saz",
      date: "1953-07-02",
      location: "Villares del Saz, Spain",
      summary: "The catalog recounts an encounter reported by a teenager and a subsequent police finding of footprints and four holes.",
      limits: "Phillips cites Vallée’s catalog. The source entry gives one square dimension and no survey, individual side lengths or bearings.",
      sources: phillips(54, 28, "Catalog entry citing Vallée."),
      traces: [{
        kind: "impression",
        observation: "Four holes about 2 in (5 cm) deep were reportedly arranged in a square about 14 in (36 cm) across a side. The same account mentions footprints.",
        sourceIds: ["phillips"],
        pattern: {
          label: "Reported square of four holes", basis: "dimensions", families: ["four_point"],
          details: "The shared side dimension supports a square schematic. The record gives no coordinates for the footprints or independently measured sides."
        }
      }],
      diagram: {
        title: "Villares del Saz reported square of four holes",
        basis: "Schematic from one reported square dimension",
        note: "Local metres. The drawing uses 14 in as a nominal side length. Orientation, footprint positions and deviations from the square are unknown.",
        viewBox: [-0.12, -0.12, 0.65, 0.65],
        layers: [{
          kind: "impression", label: "Four reported holes",
          note: "Each marker represents a nominal corner. Mark widths and individual spacing are unspecified.",
          sourceIds: ["phillips"],
          marks: [[0, 0], [inches(14), 0], [inches(14), inches(14)], [0, inches(14)]]
            .map(([x, y], index) => point(x, y, "Reported hole " + (index + 1)))
        }]
      }
    },
    {
      id: "premanon",
      phillipsCaseNumber: 787,
      title: "Prémanon",
      date: "1954-09-27",
      location: "Prémanon, Jura, France",
      summary: "The catalog describes an encounter reported by four children. It recounts a police examination of a circular area of flattened grass and nearby soil marks.",
      limits: "Phillips cites Aimé Michel’s account. It gives the grass patch diameter and the holes’ inclination, with their spacing and relation to the patch center unspecified.",
      sources: phillips(787, 32, "Catalog entry citing Aimé Michel’s Flying Saucers and the Straight Line Mystery."),
      traces: [
        {
          kind: "deformation",
          observation: "A sharply defined area of grass about 12 ft (3.66 m) across was reportedly flattened counterclockwise.",
          sourceIds: ["phillips"],
          pattern: {
            label: "Circular patch with reported counterclockwise lay", basis: "dimensions",
            families: ["ring", "swirl"], handedness: "counterclockwise",
            details: "The single diameter gives the nominal outer boundary. The entry supplies no individual blade directions."
          }
        },
        {
          kind: "impression",
          observation: "Within the flattened grass were four triangular holes about 4 in (10 cm) across, reported to angle inward at 45°. Two more elongated marks were reported at the base of a pole outside.",
          sourceIds: ["phillips"],
          pattern: {
            label: "Reported square of four holes", basis: "description", families: ["four_point"],
            details: "The entry describes a square with no side lengths or bearings. The 45° figure refers to the inclination of the holes."
          }
        }
      ],
      diagram: {
        title: "Prémanon reported flattened-grass boundary",
        basis: "Outline from the reported diameter",
        note: "Local metres. The reported square of holes lies inside the grass patch, with too little positional detail to plot it.",
        viewBox: [-2.3, -2.3, 4.6, 4.6],
        layers: [{
          kind: "deformation", label: "Flattened grass",
          note: "The nominal circle represents the 12-ft span. The reported counterclockwise lay is recorded separately from the shape.",
          sourceIds: ["phillips"], marks: [circle(0, 0, feet(6), "Nominal 12-foot flattened-grass boundary")]
        }]
      }
    },
    {
      id: "bethel_burn_ring_1956",
      phillipsCaseNumber: 112,
      title: "Bethel burn ring",
      date: "1956",
      location: "Bethel, Connecticut, United States",
      summary: "Phillips lists a fall 1956 discovery of a round patch of burned grass with a small intact circle at its center.",
      limits: "The date is given only as fall 1956. The entry cites a local newspaper published years later and gives no pre-event observations or measurements of scorch intensity.",
      sources: phillips(112, 37, "Catalog entry citing the Bethel Home News, November 26, 1969."),
      traces: [
        {
          kind: "scorching",
          observation: "A burned circle about 18 ft (5.49 m) in diameter reportedly surrounded intact grass in a central circle about 3 ft (91 cm) in diameter.",
          sourceIds: ["phillips"],
          pattern: {
            label: "Burned annulus with intact center", basis: "dimensions", families: ["ring"],
            details: "The two reported diameters describe a nominal annulus. The entry supplies no evidence about variation in the severity of burning within the band."
          }
        },
        {
          kind: "surface",
          observation: "The entry reports traces of nickel and chromium in grass outside the burned area.",
          context: "Sampling locations, comparison samples and analytical methods are unspecified.",
          sourceIds: ["phillips"]
        }
      ],
      diagram: {
        title: "Bethel nominal burn and intact center",
        basis: "Schematic from the two reported diameters",
        note: "Local metres. The smaller circle is the reported intact area within the burned grass. Outline variation and geographic orientation are unknown.",
        viewBox: [-3.4, -3.4, 6.8, 6.8],
        layers: [{
          kind: "scorching", label: "Reported burn boundary and intact center",
          note: "The outer 18-ft and inner 3-ft circles show the nominal extent of the burned band.",
          sourceIds: ["phillips"],
          marks: [circle(0, 0, feet(9), "Nominal outer scorch boundary"),
            circle(0, 0, feet(1.5), "Nominal unburned central area")]
        }]
      }
    },
    {
      id: "tucuman_rings_1963",
      phillipsCaseNumber: 158,
      title: "Tucumán paired scorch rings",
      date: "1963-01-31",
      location: "Tucumán, Argentina",
      summary: "Phillips reports the discovery of two scorched rings. A witness later described seeing an object pass over the area at night.",
      limits: "The entry cites Flying Saucer Review and gives shared nominal dimensions, with no separate diameters, bearing, survey plan or verified source of heating.",
      sources: phillips(158, 46, "Catalog entry citing Flying Saucer Review."),
      traces: [
        {
          kind: "scorching",
          observation: "Two rings were reported as 12 ft (3.66 m) in diameter, each with a 14 in (36 cm) band and a reported separation of 16 in (41 cm). The account also describes damage to the roots.",
          sourceIds: ["phillips"],
          pattern: {
            label: "Paired rings with equal reported diameter", basis: "dimensions", families: ["ring"],
            details: "Equal nominal diameters give mirror symmetry in the schematic. Each ring’s actual circularity and the distribution of heat within the bands remain unresolved."
          }
        },
        {
          kind: "surface",
          observation: "A white powder described as ash-like was reportedly found on the rings.",
          sourceIds: ["phillips"]
        }
      ],
      diagram: {
        title: "Tucumán nominal plan of two scorch rings",
        basis: "Schematic from ring diameters, band widths and separation",
        note: "Local metres. The drawing interprets 12 ft as the outer diameter and 16 in as the gap between the outer edges. The source gives no compass orientation.",
        viewBox: [-4.35, -2.2, 8.7, 4.4],
        layers: [{
          kind: "scorching", label: "Reported scorch bands",
          note: "Both ring sizes use the shared description. The equal shapes and opposite locations illustrate the nominal symmetry rather than a measured contour.",
          sourceIds: ["phillips"],
          marks: [-tucumanOffset, tucumanOffset].flatMap((x, index) => [
            circle(x, 0, tucumanRadius, "Nominal outer edge, ring " + (index + 1)),
            circle(x, 0, tucumanRadius - inches(14), "Nominal inner edge, ring " + (index + 1))
          ])
        }]
      }
    },
    {
      id: "epping_1963",
      phillipsCaseNumber: 164,
      title: "Epping",
      date: "1963-12-27",
      location: "Epping, Essex, England",
      summary: "A trainee riding instructor reported an object on the ground. The catalog describes marks in mud, two circular features and flattened grass.",
      limits: "An 8-ft square has an 11.31-ft diagonal, slightly larger than the reported 11-ft diameter of the depression said to contain the marks. The dimensions are approximate.",
      sources: phillips(164, 47, "Catalog entry citing Vallée and Eileen Buckle."),
      traces: [
        {
          kind: "impression",
          observation: "Fingerprint-like mud marks were described as forming an 8-ft (2.44 m) square in an 11-ft (3.35 m) circular depression with a 3-ft (0.91 m) circle at its center.",
          sourceIds: ["phillips"],
          pattern: {
            label: "Reported square within a circular depression", basis: "dimensions", families: ["four_point", "ring"],
            details: "The approximate dimensions give a square within about the same span as the circle. The source gives no independently measured sides or mark bearings."
          }
        },
        {
          kind: "deformation",
          observation: "Flattened grass was reported at the site. The catalog gives no distinct footprint for this grass.",
          sourceIds: ["phillips"]
        }
      ],
      diagram: {
        title: "Epping nominal square and circular depression",
        basis: "Schematic from the reported dimensions",
        note: "Local metres. The square is centered for comparison. Its corners extend slightly beyond the nominal outer circle because the printed dimensions do not fit exactly.",
        viewBox: [-2.15, -2.15, 4.3, 4.3],
        layers: [{
          kind: "impression", label: "Ground depression and reported square",
          note: "The smaller circle represents the feature described at the center. The source gives no location or shape for individual mud marks.",
          sourceIds: ["phillips"],
          marks: [circle(0, 0, feet(5.5), "Nominal 11-foot depression"),
            circle(0, 0, feet(1.5), "Nominal 3-foot central circle"), square(feet(8), "Nominal square of mud marks")]
        }]
      }
    },
    {
      id: "glassboro",
      phillipsCaseNumber: 179,
      title: "Glassboro",
      date: "1964-09-04",
      location: "Glassboro, New Jersey, United States",
      summary: "Two boys reportedly saw a red light descend into woods and found a clearing with burned vegetation, soil holes and broken branches.",
      limits: "Phillips cites a magazine account. The three smaller holes were said to be equally distant from the center hole. Their radius and angular positions were unspecified.",
      sources: phillips(179, 50, "Catalog entry citing Fate Magazine."),
      traces: [
        {
          kind: "scorching",
          observation: "The catalog describes scorched soil and burned vegetation in a circular area about 30 ft (9.14 m) across.",
          sourceIds: ["phillips"],
          pattern: {
            label: "Reported circular scorch area", basis: "dimensions", families: ["ring"],
            details: "One diameter describes the boundary. The entry gives no measurements of variation around it."
          }
        },
        {
          kind: "impression",
          observation: "A center hole was reported about 30 in (76 cm) wide and 18 in (46 cm) deep. Three smaller holes about 6 in (15 cm) wide were said to be equally far from it.",
          sourceIds: ["phillips"],
          pattern: {
            label: "Equal reported radius from the center hole", basis: "description", families: ["three_point", "radial"],
            details: "A shared radius permits many arrangements. Equal angular spacing and threefold symmetry remain unknown."
          }
        },
        {
          kind: "deformation",
          observation: "Broken branches on surrounding trees were reportedly hanging downward.",
          sourceIds: ["phillips"]
        }
      ],
      diagram: {
        title: "Glassboro scorch boundary and center hole",
        basis: "Schematic from two reported diameters",
        note: "Local metres. The account places the large hole at the center of the clearing. The three smaller holes have no usable radius or bearings and are omitted.",
        viewBox: [-5.35, -5.35, 10.7, 10.7],
        layers: [
          {
            kind: "scorching", label: "Burned area",
            note: "The outer line depicts the single reported 30-ft diameter.",
            sourceIds: ["phillips"], marks: [circle(0, 0, feet(15), "Nominal burned area")]
          },
          {
            kind: "impression", label: "Reported center hole",
            note: "The circle depicts the nominal 30-in width. The reported depth was 18 in.",
            sourceIds: ["phillips"], marks: [circle(0, 0, inches(15), "Nominal center hole")]
          }
        ]
      }
    },
    {
      id: "custer_snow",
      phillipsCaseNumber: 188,
      title: "Custer snow mark",
      date: "1965-01-12",
      location: "Custer, Washington, United States",
      summary: "The catalog recounts reports of a bright light and a site with a circular snow mark, ground scorching and a line of tracks.",
      limits: "Phillips cites Vallée and UFO-INFO. The catalog gives the snow mark’s diameter and a nominal track interval. The track count and the relative position and extent of the scorching are unspecified.",
      sources: phillips(188, 52, "Catalog entry citing Vallée and UFO-INFO."),
      traces: [
        {
          kind: "surface",
          observation: "A circular mark 12 ft (3.66 m) across was reported in 14–18 in (36–46 cm) of snow. The entry describes snowmelt in this area.",
          sourceIds: ["phillips"],
          pattern: {
            label: "Reported circular snowmelt", basis: "dimensions", families: ["ring"],
            details: "The given diameter describes the visible footprint. The record leaves the relative contributions of melting and mechanical disturbance unresolved."
          }
        },
        {
          kind: "scorching",
          observation: "Ground scorching was reported at the site separately from the description of snowmelt.",
          sourceIds: ["phillips"]
        },
        {
          kind: "impression",
          observation: "Oval tracks roughly 8 in (20 cm) long and about 8 in apart were said to lead away from the site in single file.",
          sourceIds: ["phillips"],
          pattern: {
            label: "Reported single-file tracks", basis: "dimensions", families: ["rows"],
            details: "The catalog gives one approximate interval, with the spacing reference, bearings and number of tracks unspecified."
          }
        }
      ],
      diagram: {
        title: "Custer nominal snow mark",
        basis: "Outline from the reported diameter",
        note: "Local metres. The circle depicts the reported snow mark. The positions of the track line and the scorch boundary are unknown.",
        viewBox: [-2.22, -2.22, 4.44, 4.44],
        layers: [{
          kind: "surface", label: "Reported snow mark",
          note: "The line shows the nominal 12-ft diameter. Scorching and tracks are described in the case record.",
          sourceIds: ["phillips"], marks: [circle(0, 0, feet(6), "Nominal snow mark boundary")]
        }]
      }
    },
    {
      id: "long_prairie",
      phillipsCaseNumber: 684,
      title: "Long Prairie",
      date: "1965-10-23",
      location: "Long Prairie, Minnesota, United States",
      summary: "A driver reported a lighted object on the road. Phillips recounts a sheriff and police officer finding three stripes of an oil-like material at the spot.",
      limits: "The residue composition, line widths, individual endpoint locations and bearings were unspecified. The reported three supports are from the sighting account.",
      sources: phillips(684, 57, "Catalog entry citing The Humanoids."),
      traces: [{
        kind: "surface",
        observation: "Three parallel oil-like stripes were reported about 4 in (10 cm) apart and 1 yd (91 cm) long.",
        sourceIds: ["phillips"],
        pattern: {
          label: "Three parallel residue lines", basis: "dimensions", families: ["rows"],
          details: "The reported separation and length describe the nominal repeated pattern. The record gives no distinct evidence of support impressions."
        }
      }],
      diagram: {
        title: "Long Prairie three residue stripes",
        basis: "Schematic from reported stripe length and spacing",
        note: "Local metres. Aligned ends are illustrative. The source gives parallel lines and approximate spacing, with no measured stripe widths.",
        viewBox: [-0.13, -0.28, 1.17, 0.56],
        layers: [{
          kind: "surface", label: "Reported oil-like stripes",
          note: "The lines show nominal 1-yd lengths and 4-in gaps.",
          sourceIds: ["phillips"],
          marks: [-inches(4), 0, inches(4)].map((y, index) => ({
            type: "path", d: "M 0 " + y + " h " + feet(3), estimated: true,
            label: "Nominal residue stripe " + (index + 1)
          }))
        }]
      }
    },
    {
      id: "corndale",
      phillipsCaseNumber: 221,
      title: "Corndale",
      date: "1966-01",
      location: "Corndale, New South Wales, Australia",
      summary: "Phillips lists a girl’s report of a glowing object and the finding of a broad oval depression.",
      limits: "The catalog supplies one length, width and depth. A separate catalog entry dated May 1969 gives the same oval dimensions for Corndale with conflicting location metadata. The relationship between the two entries is unresolved.",
      sources: phillips(221, 58, "Catalog entry citing UFOs over the Southern Hemisphere."),
      traces: [{
        kind: "impression",
        observation: "An oval depression was reported as 20 × 15 ft (6.10 × 4.57 m) and 1 ft (30 cm) deep.",
        sourceIds: ["phillips"],
        pattern: {
          label: "Reported oval depression", basis: "dimensions", families: ["oval"],
          details: "The two dimensions describe elongation. The entry supplies no field survey for assessing exact mirror symmetry.",
          dimensions: { longM: feet(20), shortM: feet(15) }
        }
      }],
      diagram: {
        title: "Corndale nominal oval depression",
        basis: "Schematic from the reported long and short spans",
        note: "Local metres. An ellipse illustrates the reported oval. Orientation, contour variation and the extent of the reported depth are unknown.",
        viewBox: [-3.65, -2.85, 7.3, 5.7],
        layers: [{
          kind: "impression", label: "Reported depression", note: "The long span is about 1.33 times the short span.",
          sourceIds: ["phillips"],
          marks: [{ type: "ellipse", x: 0, y: 0, rx: feet(10), ry: feet(7.5), estimated: true,
            label: "Nominal 20 by 15 foot oval" }]
        }]
      }
    },
    {
      id: "canada_sumach_ring",
      phillipsCaseNumber: 235,
      title: "Canadian sumac ring",
      date: "1966-05",
      location: "Canada, locality unspecified",
      summary: "Phillips lists a light sighting and a report of an annular band where sumac trees had been knocked down.",
      limits: "The entry attributes the report to Brian Cannon and names the country only. No tree positions, angles or verified link to the light are given.",
      sources: phillips(235, 60, "Catalog entry attributed to Brian Cannon."),
      traces: [{
        kind: "deformation",
        observation: "The reported ring was 35 ft (10.7 m) across and about 3 ft (0.91 m) wide, with normal growth in the center and sumac reportedly knocked down in a clockwise direction within the band.",
        sourceIds: ["phillips"],
        pattern: {
          label: "Reported clockwise damage in a circular band", basis: "dimensions",
          families: ["ring", "swirl"], handedness: "clockwise",
          details: "The diameter and width describe the band. The entry supplies no measurements of the individual tree positions or directions."
        }
      }],
      diagram: {
        title: "Canadian sumac ring nominal boundaries",
        basis: "Schematic from the reported diameter and band width",
        note: "Local metres. The drawing treats 35 ft as the outside diameter. Tree positions and bearings are unknown.",
        viewBox: [-6.3, -6.3, 12.6, 12.6],
        layers: [{
          kind: "deformation", label: "Reported damage band",
          note: "The drawn ring shows the band within which the clockwise direction was reported.",
          sourceIds: ["phillips"],
          marks: [circle(0, 0, feet(17.5), "Nominal outer edge"), circle(0, 0, feet(14.5), "Nominal inner edge")]
        }]
      }
    },
    {
      id: "stirum",
      phillipsCaseNumber: 247,
      evidenceOrigin: "original",
      inventoryIds: ["bluebook:BB-10944"],
      title: "Stirum",
      date: "1966-09-13",
      location: "Stirum, North Dakota, United States",
      summary: "A schoolboy reported an object descending into a field. A North Dakota Air National Guard team documented three impressions in a fallowed field at the indicated spot. Investigators reported no heat effects in the dried stubble.",
      limits: "The field report and Phillips list the same three distances without bearings or measurement uncertainty. The Air Force technical review considered the arrangement compatible with tripod landing gear and found insufficient soil data to estimate the force. The marks’ origin remains undetermined.",
      sources: [
        ...phillips(247, 61, "Catalog entry citing CUFOS from the witness."),
        {
          id: "air_guard", label: "North Dakota Air National Guard field report and USAF technical review",
          url: "https://catalog.archives.gov/id/302555731",
          locator: "T1206 roll 65, frames 0923 (field report p. 3), 0925 (technical review), and 0929–0932 (field photographs)."
        }
      ],
      traces: [{
        kind: "impression",
        observation: "Investigators recorded three rounded depressions about 10 in (25 cm) wide and 7 in (18 cm) deep.",
        sourceIds: ["air_guard", "phillips"],
        pattern: {
          label: "Reported isosceles triangle", basis: "dimensions", families: ["three_point"],
          details: "The listed sides are 26 ft, 21 ft 6 in and 21 ft 6 in. The nominal shape has one mirror axis. The longer side differs from the two reported equal sides.",
          edgesM: [stirumBase, stirumLeg, stirumLeg]
        }
      }],
      diagram: {
        title: "Stirum relative impression positions",
        basis: "Reconstructed from the three reported sides",
        note: "Local metres. The long side is drawn horizontally. Marker positions use the reported distances with no geographic orientation.",
        viewBox: [-5, -6, 10, 7.2],
        layers: [{
          kind: "impression", label: "Three reported depressions",
          note: "The side lengths define a nominal isosceles triangle. The positions and reported sizes do not identify what made the marks.",
          sourceIds: ["air_guard", "phillips"], marks: triangle(stirumBase, stirumLeg, "Reported depression")
        }]
      }
    },
    {
      id: "colorado_wolfe",
      phillipsCaseNumber: 259,
      title: "Colorado four imprints and scorch",
      date: "1967",
      location: "Colorado, United States",
      summary: "Phillips recounts a driver reporting an object briefly landing and then finding a scorched area with four imprints around it.",
      limits: "The catalog cites the National Enquirer and provides only a year and state. It describes the approximate spans without the location of each imprint.",
      sources: phillips(259, 63, "Catalog entry citing the National Enquirer."),
      traces: [
        {
          kind: "impression",
          observation: "Four imprints reportedly lay around the burned area over a space roughly 12 ft (3.66 m) square.",
          sourceIds: ["phillips"],
          pattern: {
            label: "Four imprints within a square envelope", basis: "dimensions", families: ["four_point"],
            details: "The span describes the envelope. The record gives no corner positions or between-mark distances."
          }
        },
        {
          kind: "scorching",
          observation: "The burned area was described as about 4 ft (1.22 m) square.",
          sourceIds: ["phillips"],
          pattern: {
            label: "Reported square scorch patch", basis: "dimensions",
            details: "The approximate outline has no separately measured sides or internal scorch distribution."
          }
        }
      ],
      diagram: {
        title: "Colorado scorch patch and imprint envelope",
        basis: "Schematic comparison of reported spans",
        note: "Local metres. The scorch is drawn centrally for comparison within the reported surrounding imprint span. Relative centers and orientation were unspecified.",
        viewBox: [-2.2, -2.2, 4.4, 4.4],
        layers: [
          {
            kind: "impression", label: "Imprint envelope",
            note: "The larger outline shows the stated extent. It does not locate the four imprints.",
            sourceIds: ["phillips"], marks: [square(feet(12), "Nominal 12-foot imprint envelope")]
          },
          {
            kind: "scorching", label: "Scorched area",
            note: "The smaller square depicts the nominal 4-ft scorch span.",
            sourceIds: ["phillips"], marks: [square(feet(4), "Nominal 4-foot scorched area")]
          }
        ]
      }
    },
    {
      id: "mcgregor_residue",
      phillipsCaseNumber: 264,
      title: "McGregor lawn residue",
      date: "1967-01",
      location: "McGregor, Iowa, United States",
      summary: "The resident reportedly discovered a ring of greasy, soot-like material on a lawn and similar material on the ring-facing side of a nearby bush.",
      limits: "Phillips lists this as a trace discovery. The material’s composition, source and time of deposition are unresolved.",
      sources: phillips(264, 63, "Catalog entry citing the Ohio UFO Reporter."),
      traces: [{
        kind: "surface",
        observation: "The lawn mark was described as a 14-ft (4.27 m) circle with a band 1 ft (30 cm) wide. Greasy material reportedly formed bubbles on grass blades and on the side of a nearby bush facing the ring.",
        sourceIds: ["phillips"],
        pattern: {
          label: "Annular residue with a one-sided nearby deposit", basis: "dimensions", families: ["ring"],
          details: "The ring has nominal circular symmetry. The one-sided deposit on the bush is a separate directional observation."
        }
      }],
      diagram: {
        title: "McGregor nominal lawn residue band",
        basis: "Schematic from the reported diameter and band width",
        note: "Local metres. The drawing treats 14 ft as the outer diameter. The bush position and distance are unspecified.",
        viewBox: [-2.65, -2.65, 5.3, 5.3],
        layers: [{
          kind: "surface", label: "Reported residue band", note: "The two outlines show the nominal ring thickness.",
          sourceIds: ["phillips"],
          marks: [circle(0, 0, feet(7), "Nominal outer edge"), circle(0, 0, feet(6), "Nominal inner edge")]
        }]
      }
    },
    {
      id: "banner_elk",
      phillipsCaseNumber: 269,
      title: "Banner Elk",
      date: "1967-04-08",
      location: "Banner Elk, North Carolina, United States",
      summary: "The catalog recounts four students reporting a light and subsequently finding three impressions.",
      limits: "Phillips attributes the account to George Fawcett. The catalog supplies one nominal shared distance and no site plan or individual measurements.",
      sources: phillips(269, 65, "Catalog entry attributed to George Fawcett."),
      traces: [{
        kind: "impression",
        observation: "Three round imprints were reported as about 6 in (15 cm) wide and 2 in (5 cm) deep, with roughly 3 ft (0.91 m) spacing.",
        sourceIds: ["phillips"],
        pattern: {
          label: "Reported equilateral arrangement", basis: "dimensions", families: ["three_point"],
          details: "The account describes an equilateral triangle and gives a shared distance. Exact symmetry cannot be tested from the summary."
        }
      }],
      diagram: {
        title: "Banner Elk nominal three-imprint layout",
        basis: "Schematic from one shared reported distance",
        note: "Local metres. The shared 3-ft estimate supplies the sides. No bearings or separate measurements are available.",
        viewBox: [-0.66, -1, 1.32, 1.2],
        layers: [{
          kind: "impression", label: "Three reported round imprints",
          note: "The markers represent the nominal vertices of the triangle described by the source.",
          sourceIds: ["phillips"], marks: triangle(feet(3), feet(3), "Reported imprint")
        }]
      }
    },
    {
      id: "bowden_grass_ring",
      phillipsCaseNumber: 291,
      title: "Bowden grass ring",
      date: "1967-09",
      location: "Bowden, Alberta, Canada",
      summary: "The catalog describes a person finding a ring of depressed grass in a secluded corner of a field.",
      limits: "Phillips lists a trace discovery. The entry supplies one diameter and one band width, with no mapped contour, time of formation or cause.",
      sources: phillips(291, 69, "Catalog entry citing Saucers, Space and Science."),
      traces: [{
        kind: "deformation",
        observation: "The reported grass ring measured 32 ft (9.75 m) across with an 8 in (20 cm) band.",
        sourceIds: ["phillips"],
        pattern: {
          label: "Narrow ring of depressed grass", basis: "dimensions", families: ["ring"],
          details: "The source describes a circle. One diameter and one band width provide no estimate of departures from circular symmetry."
        }
      }],
      diagram: {
        title: "Bowden nominal grass ring",
        basis: "Schematic from the reported diameter and band width",
        note: "Local metres. The drawing treats 32 ft as the outer diameter. The reported width is used around the nominal circle.",
        viewBox: [-5.7, -5.7, 11.4, 11.4],
        layers: [{
          kind: "deformation", label: "Reported depressed grass",
          note: "The narrow space between the two outlines represents the reported 8-in band.",
          sourceIds: ["phillips"],
          marks: [circle(0, 0, feet(16), "Nominal outer edge"),
            circle(0, 0, feet(16) - inches(8), "Nominal inner edge")]
        }]
      }
    },
    {
      id: "winsted",
      phillipsCaseNumber: 707,
      title: "Winsted",
      date: "1967-09-20",
      location: "Winsted, Connecticut, United States",
      summary: "Two witnesses reported a glow in woods. The catalog says a forest ranger and a resident found a burned depression and impressions three days later.",
      limits: "The contemporary account gives the nominal spacing of three marks. It does not locate the separate central imprint relative to their triangle or establish that all traces formed at the same time.",
      sources: [
        ...phillips(707, 70, "Catalog entry citing the November–December 1967 APRO Bulletin."),
        {
          id: "apro",
          label: "APRO Bulletin, September Landing in Conn.",
          url: "https://www.openminds.tv/pdf/apro/apro_nov_1967.pdf#page=4",
          locator: "November–December 1967, printed p. 4, report attributed to Larry Fawcett."
        }
      ],
      traces: [
        {
          kind: "impression",
          observation: "Four triangular imprints were reported. One was placed at the center of the depressed area. The other three were described as a 10-ft (3.05 m) equilateral set.",
          sourceIds: ["apro", "phillips"],
          pattern: {
            label: "Three reported equal sides plus a separate imprint", basis: "dimensions", families: ["three_point"],
            details: "The three outer marks use a shared nominal side length. The fourth imprint’s position relative to them remains unknown."
          }
        },
        {
          kind: "scorching",
          observation: "The depressed area was described as burned and teardrop-shaped, about 35 ft (10.7 m) across.",
          sourceIds: ["apro", "phillips"],
          pattern: {
            label: "Reported teardrop-shaped burn", basis: "dimensions", families: ["irregular"],
            details: "One span and a shape description are available. The plan orientation, contour and position relative to the three-point set are unspecified."
          }
        },
        {
          kind: "deformation",
          observation: "Several trees were reportedly broken near their tops and had scraped trunks.",
          sourceIds: ["apro", "phillips"]
        }
      ],
      diagram: {
        title: "Winsted nominal three-imprint layout",
        basis: "Schematic from the reported shared spacing",
        note: "Local metres. The separate fourth imprint and burned boundary cannot be aligned to the triangle from the catalog description.",
        viewBox: [-2.1, -3.2, 4.2, 3.8],
        layers: [{
          kind: "impression", label: "Three reported outer impressions",
          note: "The schematic uses the 10-ft shared side estimate. It gives no indication of geographic orientation.",
          sourceIds: ["apro", "phillips"], marks: triangle(feet(10), feet(10), "Reported outer imprint")
        }]
      }
    }
  ];
});
