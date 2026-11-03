(function (root, factory) {
  "use strict";

  const cases = factory();
  if (typeof module === "object" && module.exports) module.exports = cases;
  if (root) root.UfoLandingSiteUfocatReviewedCases = cases;
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";

  const tucsonFile = "https://upload.wikimedia.org/wikipedia/commons/4/4a/Project_Blue_Book_report_-_1967-10-7282590-Tucson-Arizona.pdf";
  const tucsonRadius = 13 * 0.0254 / 2;
  const tucsonHalfSpacing = (42 + 13) * 0.0254 / 2;

  return [
    {
      id: "tucson_wash_1967",
      title: "Tucson wash",
      date: "1967-10-09",
      location: "Tucson, Arizona, United States",
      evidenceOrigin: "original",
      inventoryIds: ["ufocat:56902", "hatch:Hatch_UDB_8478"],
      summary: "A family photographed two depressions in sandy ground after a reported encounter. The APRO account and the Air Force field report give different widths. Army engineers examined the photographs and sand, then tested whether they could reproduce the marks.",
      limits: "The APRO dimensions give a nominal paired outline. The Air Force field correspondence estimated each hole at about two feet across, one slightly smaller. The documents do not reconcile that difference or give a surveyed bearing. No matched comparison of the two individual outlines or internal ridge orientations is available.",
      controls: "Army engineers made depressions in loose sand by rotating a plate, reproducing the sharp rim and forming an interior ridge. They judged the sharp profile inconsistent with the static or dynamic footing loads they considered. The Air Force evaluated the report as a hoax based on the examination.",
      sources: [
        {
          id: "nara",
          label: "U.S. National Archives, Tucson Project Blue Book folder",
          url: "https://catalog.archives.gov/id/302571064",
          locator: "National Archives identifier 302571064, October 1967 Tucson folder."
        },
        {
          id: "apro",
          label: "APRO Bulletin, contemporary investigation and photograph",
          url: "https://www.openminds.tv/pdf/apro/apro_sep_1967.pdf#page=4",
          locator: "September–October 1967, Landing at Tucson, pp. 1 and 4. Page 4 gives dimensions and shows the impressions."
        },
        {
          id: "field",
          label: "Project Blue Book case file, Air Force field correspondence",
          url: tucsonFile + "#page=28",
          locator: "PDF p. 28, reply to the 19 October 1967 request for dimensions."
        },
        {
          id: "army",
          label: "U.S. Army Ohio River Division Laboratories, sand examination",
          url: tucsonFile + "#page=2",
          locator: "17 January 1968, printed pp. 2–6, photograph assessment, tests and conclusions."
        },
        {
          id: "closeout",
          label: "Project Blue Book closeout correspondence",
          url: tucsonFile + "#page=57",
          locator: "PDF pp. 57–58, Air Force assessment of the case."
        }
      ],
      traces: [
        {
          kind: "impression",
          observation: "The APRO report gives two depressions about 13 inches (33 cm) across with about 42 inches (107 cm) between the edges. Air Force investigators separately estimated approximately two feet (61 cm) across, one slightly smaller.",
          sourceIds: ["apro", "field"],
          pattern: {
            label: "Two roughly circular depressions",
            basis: "dimensions",
            details: "The nominal pair has a midpoint, with circles of equal size drawn from the APRO dimensions. The source estimates differ, so measured mirror symmetry is unresolved."
          }
        },
        {
          kind: "surface",
          observation: "Army engineers distinguished a sharply peaked outer lip and curved, divided ridges inside the depressions. Rotation of a plate in sand reproduced key features. The photographs did not establish a site-wide twist direction.",
          sourceIds: ["apro", "army"],
          pattern: {
            label: "Curved internal ridges and raised lips",
            basis: "description",
            details: "These are local features of the depressions. The report inferred a rotational action for one interior ridge, and did not give surveyed ridge coordinates or paired orientations."
          }
        }
      ],
      diagram: {
        title: "Nominal outline of the Tucson pair",
        basis: "Approximate APRO dimensions",
        note: "Local metres with arbitrary orientation. The reported 42 inches is read as the gap between the nearest edges. Circle outlines represent reported widths. The Air Force field estimate is larger, and ridge positions are unplotted.",
        viewBox: [-1.05, -0.45, 2.1, 0.9],
        layers: [
          {
            kind: "impression",
            label: "Nominal depression outlines",
            note: "The equal-size circles make the plotted pair mirror-symmetric. The agreement of actual depression sizes and outlines remains unresolved.",
            sourceIds: ["apro"],
            marks: [
              { type: "ellipse", x: -tucsonHalfSpacing, y: 0, rx: tucsonRadius, ry: tucsonRadius, tag: "A", label: "Approximate depression A", estimated: true },
              { type: "ellipse", x: tucsonHalfSpacing, y: 0, rx: tucsonRadius, ry: tucsonRadius, tag: "B", label: "Approximate depression B", estimated: true }
            ]
          }
        ]
      }
    },
    {
      id: "douvrin_1993",
      title: "Douvrin garden",
      date: "1993-10-30",
      location: "Douvrin, Pas-de-Calais, France",
      evidenceOrigin: "original",
      inventoryIds: ["ufocat:203341"],
      summary: "GEIPAN's reassessment identifies the former Nœux-les-Mines catalog entry as a Douvrin garden case. Residents reported finding flattened grass on three occasions over roughly two weeks in early November. October 30 is the archive's date label.",
      limits: "The published account gives approximate strip lengths and places the circle at their junction. Bearings, the angle between strips and circle diameter are unspecified. The successive discoveries leave their formation times unresolved.",
      controls: "GEIPAN found the reported light appeared after the initial trace discovery and could not place it over the garden. The agency reclassified the case as outside the scope of its aerial-phenomena analysis. The gendarmes visited on November 17.",
      sources: [
        {
          id: "geipan",
          label: "CNES GEIPAN case reassessment",
          url: "https://www.cnes-geipan.fr/cas/1993-10-01663",
          locator: "Case 1993-10-01663, reassessment published 23 June 2021, site description and classification."
        }
      ],
      traces: [
        {
          kind: "deformation",
          observation: "The first patch was described as a sinuous strip about 8 m long and 40 cm wide. A second strip was about 10 m long. A circular patch was later found at the junction of the strips.",
          sourceIds: ["geipan"],
          pattern: {
            label: "Two flattened strips and a circular patch",
            basis: "description",
            details: "The reports describe a circular feature at a junction. The measured lengths do not establish alignment, mirror symmetry or a radial arrangement."
          }
        }
      ]
    },
    {
      id: "tyneham_1969",
      title: "Tyneham range",
      date: "1969-08",
      location: "Tyneham, Dorset, England",
      evidenceOrigin: "original",
      inventoryIds: ["ufocat:50452"],
      summary: "An APRO follow-up reproduced a local investigator’s account of nine holes arranged around a center on the Tyneham military range. The initial press account described a smaller span. The follow-up reports two distances from the central hole.",
      limits: "The reported date is August 19 in the APRO follow-up and UFOCAT, and August 29 in the earlier APRO issue and BUFORA report. The underlying field drawing was mentioned but was unavailable for review. The follow-up says the marks were nearly symmetrical and gives no bearings or individual separations.",
      controls: "APRO’s investigator could not reach the witness or obtain range access. BUFORA retained the case as a probable hoax after its enquiries. The APRO follow-up also records shell holes elsewhere on the range and a separate group of impressions at Badbury.",
      sources: [
        { id: "followup", label: "APRO Bulletin, Follow-Ups", url: "https://www.openminds.tv/pdf/apro/apro_nov_1969.pdf#page=7", locator: "November–December 1969, p. 7. Right column reproduces the local investigator’s measurements." },
        { id: "initial", label: "APRO Bulletin, first published Tyneham account", url: "https://www.openminds.tv/pdf/apro/apro_jul_1969.pdf#page=8", locator: "July–August 1969, p. 8. Gives August 29 and a 24-foot diameter, which differs from the later reported 24-foot outer radius." },
        { id: "bufora", label: "BUFORA Director of Research, contemporary case assessment", url: "https://www.bufora.org.uk/_files/ugd/4719c2_9072a71750cb4fd0a85600435a361def.pdf", locator: "Research Report, October 25, 1969. Records the probable-hoax disposition." }
      ],
      traces: [
        {
          kind: "impression",
          observation: "The follow-up describes a central hole, four at a 4 ft radius, and four at a 24 ft radius. It gives a typical hole diameter of 6 in and a depth of 3 in, with a narrower central shaft about 5 in deep.",
          sourceIds: ["followup"],
          pattern: { label: "Central hole with two groups of four", basis: "dimensions", families: ["radial"], details: "The approximate reported radii were 1.22 m and 7.32 m. The four positions in each group and their relative orientations are unspecified. Rotational symmetry cannot be measured." }
        }
      ],
      diagram: {
        title: "Reported distances from the Tyneham central hole",
        basis: "Reported radius measurements",
        note: "Local metres. Dashed circles mark the reported distances of two groups of holes. The circles are distance guides. Eight individual holes are unplaced because their bearings were unreported.",
        viewBox: [-8.2, -8.2, 16.4, 16.4],
        layers: [{
          kind: "impression", label: "Central hole and distance guides",
          note: "The account describes four marks near each guide. Their positions, angular spacing and alignment across guides are unknown.", sourceIds: ["followup"],
          marks: [
            { type: "point", x: 0, y: 0, label: "Reported central hole", estimated: true },
            { type: "ellipse", x: 0, y: 0, rx: 1.2192, ry: 1.2192, label: "Four reported holes around a 1.22 m radius", estimated: true },
            { type: "ellipse", x: 0, y: 0, rx: 7.3152, ry: 7.3152, label: "Four reported holes around a 7.32 m radius", estimated: true }
          ]
        }]
      }
    },
    {
      id: "clyde_wheat_1967",
      title: "Clyde wheat field",
      date: "1967-08-04",
      location: "Clyde, near Milton-Freewater, Oregon, United States",
      evidenceOrigin: "catalog",
      inventoryIds: ["ufocat:90086"],
      summary: "A contemporary APRO report describes a farmer finding a roughly circular area of flattened wheat the day after he and his wife saw a ring of light in the area.",
      limits: "The article gives a single approximate diameter. It does not show a site plan, the direction of stalk lay or the exact outline. The flattened patch cannot be registered to the reported light.",
      controls: "The article says firefighters responded and found no fire. The farmer reported seeing no animal tracks in the patch. The same article covers a separate December blast and depression, which occurred at a different time and site.",
      sources: [
        { id: "apro", label: "APRO Bulletin, Strange Lights, Blast, Seem Connected", url: "https://www.openminds.tv/pdf/apro/apro_jan_1968.pdf#page=3", locator: "January–February 1968, p. 3, left column, August 4 account." }
      ],
      traces: [
        {
          kind: "deformation",
          observation: "The farmer described an area of wheat pressed down in a roughly circular patch about 200 ft across.",
          sourceIds: ["apro"],
          pattern: { label: "Single circular patch of flattened wheat", basis: "dimensions", families: ["ring", "isolated"], details: "Approximately 61 m across. One diameter does not establish the actual circularity, center or stalk orientation." }
        }
      ],
      diagram: {
        title: "Nominal outline of the Clyde wheat patch",
        basis: "Approximate reported diameter",
        note: "Local metres. The outline models the reported 200 ft span as a circle. Its exact shape and orientation are unknown.",
        viewBox: [-35, -35, 70, 70],
        layers: [{
          kind: "deformation", label: "Approximate flattened-wheat boundary",
          note: "A single reported span fixes the nominal diameter. Exact rotational or reflection symmetry cannot be tested.", sourceIds: ["apro"],
          marks: [{ type: "ellipse", x: 0, y: 0, rx: 30.48, ry: 30.48, label: "Nominal boundary, about 61 m across", estimated: true }]
        }]
      }
    },
    {
      id: "elk_grove_lawn",
      title: "Elk Grove lawn",
      date: "1968",
      location: "Elk Grove, California, United States",
      evidenceOrigin: "original",
      inventoryIds: ["ufocat:313671", "nuforc:154178"],
      summary: "A NUFORC submitter recalled finding a circular discolored area they described as burned and a separate trail of material near a relative’s house. The submitter arrived after the alleged sighting.",
      limits: "The source header gives 1968 and the witness narrative gives 1970. Both inventory records reproduce the same submission. Width, extent and alignment of the traces are unknown.",
      controls: "The submitter reported collecting material and giving it to the Air Force. The account supplies no lab result, photo or independent site measurements.",
      sources: [
        { id: "nuforc", label: "NUFORC submission 154178", url: "https://nuforc.org/sighting/?id=154178", locator: "Witness narrative, posted April 9, 2020. The narrative identifies Elk Grove, California." }
      ],
      traces: [
        {
          kind: "scorching",
          observation: "The submitter described a round area of lawn that appeared burned.",
          context: "Witness characterization without testing or documented signs of combustion.",
          sourceIds: ["nuforc"],
          pattern: { label: "Reported circular lawn patch", basis: "description", families: ["ring", "isolated"], details: "No diameter, boundary measurements or center position." }
        },
        {
          kind: "surface",
          observation: "The submitter also recalled a separate trail of green material spattered toward a barn.",
          sourceIds: ["nuforc"],
          pattern: { label: "Spattered material along a reported route", basis: "description", details: "The route was described only by its destination. Its origin and position relative to the round patch are unspecified." }
        }
      ]
    },
    {
      id: "plain_snow_1973",
      title: "Plain snow impressions",
      date: "1973-03-12",
      location: "Plain, Washington, United States",
      evidenceOrigin: "original",
      inventoryIds: ["ufocat:315049", "nuforc:45849"],
      summary: "A witness submission describes repeated pairs of three-pronged impressions in hard snow beside a road, plus a separate impression on a river bank. The report was filed in 2005, more than three decades after the stated observation.",
      limits: "The witness reported approximate sizes and a depth for one depression. The account supplies no positions, orientations, pairwise spacings, photographs or independent survey. The impressions were described near the bridge and road, with no demonstrated contact point for the reported objects.",
      controls: "The witness described both compression and melting as possibilities for the depressions. No temperature, retained snow sample or independent formation test was recorded.",
      sources: [
        { id: "nuforc", label: "NUFORC submission 45849", url: "https://nuforc.org/sighting/?id=45849", locator: "Firsthand retrospective account, posted September 2, 2005. See the snow-impression description." }
      ],
      traces: [
        {
          kind: "impression",
          observation: "The witness described three toe-like projections and a heel in individual depressions. Roadside impressions appeared in pairs scattered without a clear pattern.",
          sourceIds: ["nuforc"],
          pattern: { label: "Repeated pairs of three-pronged depressions", basis: "description", families: ["irregular"], details: "Three prongs describe individual marks. Pair orientation, distances, site-wide symmetry and cause remain unmeasured." }
        }
      ]
    }
  ];
});
