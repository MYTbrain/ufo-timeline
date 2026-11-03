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
    }
  ];
});
