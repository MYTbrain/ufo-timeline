(function (root, factory) {
  "use strict";

  const cases = factory();
  if (typeof module === "object" && module && module.exports) module.exports = cases;
  if (root) root.UfoLandingSitePhillipsLateCases = cases;
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";

  const phillipsBook = "https://cufos.org/PDFs/books/Physical_Traces.pdf";

  function phillipsEntry(caseNumber, page) {
    return {
      id: "phillips",
      label: "Ted Phillips, Physical Traces Associated with UFO Sightings",
      url: phillipsBook + "#page=" + page,
      locator: "CUFOS 1975, case " + caseNumber + ", printed p. " + (page - 18) + "."
    };
  }

  return [
    {
      id: "ibiuna",
      phillipsCaseNumber: 386,
      title: "Ibiúna",
      date: "1969-06-07",
      location: "Ibiúna, São Paulo, Brazil",
      summary: "Nobutoshi and Kyoko Kaneko described a sustained bright light near a baseball field. A flattened patch was found the following day. Field investigator Hans Bemelmans published a sketch of six marks and curved grass.",
      limits: "The Brazilian aviation record gives June 7. Bemelmans and Phillips give June 17 for the same reported episode. Visitors had trampled the area before precise measurements were considered.",
      sources: [
        phillipsEntry(386, 83),
        {
          id: "bemelmans",
          label: "Hans Bemelmans, Reports from Ibiuna",
          url: "https://oldcropcircles.weebly.com/uploads/6/8/2/6/6826365/7651523_orig.jpg",
          locator: "Flying Saucer Review 16(1), Jan–Feb 1970, pp. 15–19, reproduced field sketch of the first formation."
        },
        {
          id: "bemelmans-text",
          label: "Hans Bemelmans, first formation field report",
          url: "https://oldcropcircles.weebly.com/uploads/6/8/2/6/6826365/9255394_orig.jpg",
          locator: "Reproduced passage on size, curved grass, site trampling and inspection for scorching."
        },
        {
          id: "sioani",
          label: "Brazilian Air Force witness report, National Archives",
          url: "https://ovnis.area404.com.br/narracao-de-comerciante-sobre-duas-observacoes-de-trafego-hotel-em-ibiuna-estado/",
          locator: "Arquivo Nacional reference BR DFANBSB ARX.0.0.49, date and observation."
        },
        {
          id: "ribeiro",
          label: "Edison Boaventura Júnior, account of the SIOANI investigation",
          url: "https://ufo.com.br/a-aeronautica-pesquisou-casos-ufologicos-no-interior-de-sao-paulo/",
          locator: "Ibiúna case no. 50, reporting Ribeiro's annotations on mark dimensions and grass condition."
        }
      ],
      traces: [
        {
          kind: "impression",
          observation: "Bemelmans drew six numbered marks. Boaventura's account of the military file describes six furrows about 20 cm long and 5–10 cm deep.",
          context: "The report's support interpretation is one possibility. The published sketch gives relative positions without surveyed angles or inter-mark distances.",
          sourceIds: ["bemelmans", "ribeiro"],
          pattern: {
            label: "Six marks in an uneven cluster",
            families: ["irregular"],
            basis: "description",
            details: "The sketch separates the six marks from the surrounding vegetation. The reported dimensions describe individual marks."
          }
        },
        {
          kind: "deformation",
          observation: "The grass lay counterclockwise across a patch recalled as approximately 8 m in diameter, with smaller local swirls.",
          context: "The overall direction and local changes were drawn by the investigator. The first formation is distinct from another formation discussed in the same article.",
          sourceIds: ["bemelmans", "bemelmans-text", "ribeiro"],
          pattern: {
            label: "Counterclockwise lay with local swirls",
            families: ["swirl"],
            handedness: "counterclockwise",
            basis: "description",
            details: "The sketch shows curved vegetation around several marks and across the wider patch. Individual stem angles and the positions of any causal sources are undetermined."
          }
        },
        {
          kind: "surface",
          observation: "Boaventura reports a frost-like, roughly star-shaped grass discoloration described in the military file, about 10 m across.",
          context: "A newspaper described possible scorching. Bemelmans examined stems and roots and reported seeing none. The size and cause of any thermally affected area remain uncertain.",
          sourceIds: ["ribeiro", "bemelmans-text"]
        }
      ],
      diagram: {
        title: "Ibiúna six marks and curved vegetation",
        viewBox: [0, 0, 255, 250],
        basis: "Approximate positions from the published field sketch",
        note: "East is up and north is left, as marked by Bemelmans. The sketch shows an approximate grass boundary and selected strand directions. It gives no surveyed positions for the marks or separate scorching.",
        layers: [
          {
            kind: "deformation",
            label: "Curved grass",
            note: "Selected curves summarize the drawn grass lay, including smaller turns beside numbered marks. The reported span was about 8 m.",
            sourceIds: ["bemelmans", "bemelmans-text"],
            marks: [
              { type: "path", d: "M 106 114 C 99 91 71 94 58 112 C 37 143 51 191 87 214", estimated: true, label: "Curved grass at the upper and left side" },
              { type: "path", d: "M 130 112 C 137 88 129 67 108 60 C 74 50 45 78 34 105", estimated: true, label: "Curved grass around the upper-left side" },
              { type: "path", d: "M 153 117 C 177 114 182 90 166 70 C 151 49 129 43 108 46", estimated: true, label: "Curved grass along the upper-right side" },
              { type: "path", d: "M 154 148 C 178 154 203 140 206 115 C 208 89 188 69 171 61", estimated: true, label: "Curved grass along the right side" },
              { type: "path", d: "M 132 161 C 129 182 145 196 170 191 C 202 181 219 150 219 121", estimated: true, label: "Curved grass around the lower-right side" },
              { type: "path", d: "M 99 154 C 78 159 76 182 96 197 C 119 217 151 215 173 205", estimated: true, label: "Curved grass around the lower-left side" },
              { type: "path", d: "M 100 140 C 88 138 84 151 89 161 M 144 152 C 134 148 122 151 121 162 M 165 148 C 170 140 162 133 154 135", estimated: true, label: "Examples of the smaller turns sketched beside numbered marks" }
            ]
          },
          {
            kind: "impression",
            label: "Numbered soil marks",
            note: "Marker centers follow the numbers on the sketch. Symbol size does not represent mark width.",
            sourceIds: ["bemelmans", "ribeiro"],
            marks: [[99, 153], [132, 162], [154, 148], [152, 120], [130, 112], [110, 113]]
              .map(([x, y], index) => ({
                type: "point", x, y, tag: String(index + 1), label: "Mark " + (index + 1), estimated: true
              }))
          }
        ]
      }
    },
    {
      id: "lynchford",
      phillipsCaseNumber: 476,
      title: "Lynchford",
      date: "1971-05-25",
      location: "Lynchford, Tasmania, Australia",
      summary: "A resident heard a humming noise overnight and saw no object. The following day a flattened patch of grass and blackberry was reported. More patches were found after visitors had been through the area.",
      limits: "The first patch and the later patches have different discovery dates. The contemporary report gives a 15 ft width for the first patch, whereas Phillips lists 5 ft. The record gives no plan of their relative positions.",
      controls: "Heavy dew and downdrafts were proposed as ordinary explanations. The report gives local weather context and no matched reconstruction.",
      sources: [
        phillipsEntry(476, 95),
        {
          id: "roberts",
          label: "W. K. Roberts, Burst of UFO activity in Tasmania",
          url: "https://noufors.com/Documents/Books%2C%20Manuals%20and%20Published%20Papers/Specialty%20UFO%20Publications/Flying%20Saucer%20Review%20-%20Case%20Histories/FSR-CH%201971%20N%207.pdf#page=15",
          locator: "Flying Saucer Review Case Histories no. 7, Oct 1971, printed p. 13, entry 3."
        }
      ],
      traces: [
        {
          kind: "deformation",
          observation: "Roberts reports an initial flattened patch about 30 × 15 ft (9.1 × 4.6 m), with a spiral in the middle. A similar larger patch and four smaller ones were reported later.",
          sourceIds: ["roberts"],
          pattern: {
            label: "Reported spiral within flattened vegetation",
            basis: "description",
            families: ["swirl"],
            handedness: "uncertain",
            details: "The account gives the overall size, but no curve positions or direction of rotation."
          }
        },
        {
          kind: "impression",
          observation: "Six indentations in the first patch were described as irregularly placed. The four smaller patches each reportedly contained three depressions, with a base of about 3 ft and a distance to the apex of about 9 ft.",
          sourceIds: ["roberts", "phillips"],
          pattern: {
            label: "Irregular marks and later rough triangles",
            basis: "description",
            families: ["irregular", "three_point"],
            details: "The later triangles have rough dimensions but lack individually recorded angles, positions and separate side lengths."
          }
        }
      ]
    },
    {
      id: "la_spezia",
      phillipsCaseNumber: 665,
      title: "Ponzano Magra Inferiore",
      date: "1973-07-04",
      location: "Near La Spezia, Liguria, Italy",
      summary: "Witnesses reported a light disappearing behind a hill and later rising. Two investigators found four impressions near a paving-tile waste pile on separate visits.",
      limits: "The hill screened the site from the witnesses. Stelio Asso showed Marco Mariani the first two impressions. Mariani found the other two about a month after the sighting.",
      sources: [
        phillipsEntry(665, 109),
        {
          id: "mariani",
          label: "Marco Mariani, Did ball of fire leave traces?",
          url: "https://electronicsandbooks.com/edt/manual/Magazine/M/MUFON%20UFO%20Journal/Skylook%20MUFON%20UFO%20Journal%20-%20March%201975.pdf#page=11",
          locator: "Skylook, March 1975, printed pp. 10–11, cast photograph and annotated four-mark plan."
        }
      ],
      traces: [
        {
          kind: "impression",
          observation: "Three impressions in discarded paving tiles measured about 40 cm across and 22 cm deep. A fourth, in soil roughly 70–80 cm lower, measured about 30 cm across and 15 cm deep.",
          sourceIds: ["mariani", "phillips"],
          pattern: {
            label: "Two short sides and two long sides",
            basis: "dimensions",
            families: ["four_point"],
            details: "The plan gives A–B as 5.90 m, B–D as 13.10 m, D–C as 6.20 m and C–A as 13.30 m. Opposite sides are close in length. Unknown diagonals and the change in ground level leave exact mirror and half-turn symmetry unresolved.",
            edgesM: [5.90, 13.10, 6.20, 13.30]
          }
        }
      ],
      diagram: {
        title: "Ponzano Magra Inferiore schematic of four impressions",
        viewBox: [-2.5, -1.6, 11, 17.5],
        basis: "Four recorded side lengths with schematic angles",
        note: "The two side pairs set the layout. No surveyed diagonal, angles or horizontal correction for the lower mark were reported.",
        layers: [
          {
            kind: "impression",
            label: "Four impressions",
            note: "D was on a lower slope. The dashed perimeter connects marks for comparison and does not represent a physical trace.",
            sourceIds: ["mariani"],
            marks: [
              { type: "path", d: "M 0 0 L 5.9 0 L 6.05 13.1 L -0.15 13.3 Z", estimated: true, label: "Schematic perimeter" },
              ...[[0, 0, "A"], [5.9, 0, "B"], [-0.15, 13.3, "C"], [6.05, 13.1, "D"]]
                .map(([x, y, tag]) => ({ type: "point", x, y, tag, label: "Impression " + tag, estimated: true }))
            ]
          }
        ]
      }
    }
  ];
});
