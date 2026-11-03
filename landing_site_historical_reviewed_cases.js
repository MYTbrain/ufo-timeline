(function (root, factory) {
  "use strict";

  const cases = factory();
  if (typeof module === "object" && module.exports) module.exports = cases;
  if (root) root.UfoLandingSiteHistoricalReviewedCases = cases;
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";

  const olmos = "https://cufos.org/PDFs/books/Catalogue_of_200_Type_I_UFO_Events_in_Spain_and_Portugal.pdf";
  const gatReport = "https://cufos.org/PDFs/IUR%20issues/IUR%20Vol.%202%20No.%205%20May%201977.pdf";
  const gatCloseout = "https://cufos.org/PDFs/IUR%20issues/IUR%20Vol.%203%20No.%203%20March%201978.pdf";
  const gatDimensions = "https://electronicsandbooks.com/edt/manual/Magazine/M/MUFON%20UFO%20Journal/MUFON%20UFO%20Journal%20-%20September%201977.pdf";
  const joinville = "https://files.afu.se/Downloads/Magazines/Brazil/SBEDV/SBEDV%20-%20No%20094-98%20-%201973-1974.pdf";
  const stara = "https://files.afu.se/Downloads/Magazines/Canada/Canadian%20UFO%20Report%20%28Magor%29/Canadian%20UFO%20Report%20-%20vol%204%20no%204%20-%201977.pdf";
  const linke = "https://upload.wikimedia.org/wikipedia/commons/7/76/Flying_Saucers_in_East_Germany%2C_CIA_Report.pdf";
  const ngatea = "https://ignaciodarnaude.es/wp-content/uploads/2025/08/FultonCrop-Circles-1969N.Zealand-1FSR70V16N2.pdf#page=1";
  const haukeli = "https://www.ufo.se/index.php/utlaednska-rapporter/1329-norge-1991-farkost-svarade-pa-blinkningar";
  const baldwin = "https://cufos.org/PDFs/IUR%20issues/IUR%20Vol.%204%20No.%206%20Dec.%201979.pdf#page=11";
  const campestre = "https://ufo.com.br/movimentacao-de-ufos-no-litoral-do-rio-grande-do-norte/";
  const gt = [1.8288, 1.3716, 1.3208];
  const gtThirdX = (gt[0] ** 2 + gt[1] ** 2 - gt[2] ** 2) / (2 * gt[0]);
  const gtThirdY = Math.sqrt(gt[1] ** 2 - gtThirdX ** 2);

  return [
    {
      id: "baldwin_hay_1979",
      title: "Baldwin hayfield patch",
      date: "1979-10-20",
      location: "Baldwin, Wisconsin, United States",
      inventoryIds: ["hatch:Hatch_UDB_13788"],
      evidenceOrigin: "original",
      summary: "A family reported a brown, dried patch in a hayfield after a teenager saw lights from their farmhouse. The contemporary CUFOS account includes a field photograph.",
      limits: "The family found the patch three days after the light report. The record gives two approximate spans and a general shape without a plan, third side, bearings or an established connection to the lights.",
      sources: [
        { id: "iur", label: "CUFOS report 4-6-30, Wisconsin CE II?", url: baldwin,
          locator: "International UFO Reporter 4(6), December 1979, printed and PDF p. 11." }
      ],
      traces: [
        {
          kind: "surface",
          observation: "The reported patch of hay was brown and dried, triangular in outline, with dimensions of about 45 ft by 30 ft.",
          pattern: { label: "Triangular dried vegetation patch", basis: "dimensions",
            dimensions: { longM: 13.716, shortM: 9.144 },
            details: "The source supplies two spans without identifying individual sides. No direct heat measurement or scorch analysis was reported." },
          sourceIds: ["iur"]
        }
      ]
    },
    {
      id: "sao_jose_campestre_1989",
      title: "São José do Campestre",
      date: "1989",
      location: "Near São José do Campestre, Rio Grande do Norte, Brazil",
      inventoryIds: ["hatch:Hatch_UDB_15381"],
      evidenceOrigin: "catalog",
      summary: "Revista UFO's account of a CEUA field visit describes an affected vegetation patch and paired holes outside it. Bob Pratt also published an account attributed to a local investigator, Jackson Felix Pereira.",
      limits: "The published dates differ. Revista UFO dates a nearby light report to October 17 and gives no exact date for the inspection. Pratt dates the trace report to November. The accounts match on the locality and unusual nine-pair arrangement. The witnesses quoted by Revista UFO saw a light near a tree about 200 m from the marks and did not see the marks form.",
      sources: [
        { id: "ceua", label: "Revista UFO summary of CEUA interviews and inspection", url: campestre,
          locator: "Movimentação de UFOs no litoral do Rio Grande do Norte, paragraphs beginning with October 17, 1989." },
        { id: "pratt", label: "Bob Pratt, UFO Danger Zone", url: "https://www.scribd.com/document/766772600/UFO-Danger-Zone-Bob-Pratt",
          locator: "November 1989 entry naming Jackson Felix Pereira." }
      ],
      traces: [
        {
          kind: "impression",
          observation: "Both accounts describe nine pairs of holes arranged around the patch. Pratt gives a depth of about 6 in and describes four additional depressions in a line between two pairs.",
          pattern: { label: "Reported ring of paired holes", families: ["ring"], basis: "description",
            details: "Revista UFO describes repeated triangular holes and a 1.4 m separation, without defining the measurement endpoints. The individual pair positions and angles were not published." },
          sourceIds: ["ceua", "pratt"]
        },
        {
          kind: "scorching",
          observation: "Revista UFO reports that a 5.4 m by 5.2 m patch appeared burned. It describes a small intact area about 0.5 m across within it.",
          pattern: { label: "Nearly circular reported burn boundary", families: ["ring", "oval"], basis: "dimensions",
            dimensions: { longM: 5.4, shortM: 5.2 }, details: "The spans give the nominal outline. The publication does not specify an orientation, an offset for the intact area, or a heat source." },
          sourceIds: ["ceua"]
        },
        {
          kind: "deformation",
          observation: "Revista UFO also describes flattened vegetation in the affected area.",
          sourceIds: ["ceua"],
          context: "The flattened area has no separately measured boundary or recorded direction of lay."
        }
      ],
      diagram: {
        title: "São José do Campestre nominal affected boundary",
        basis: "Reported outer spans",
        note: "Local metres. Only the approximate outer boundary has usable paired dimensions. The unregistered intact patch, paired holes, additional holes and flattened vegetation are described separately.",
        viewBox: [-3.2, -3.2, 6.4, 6.4],
        layers: [
          { kind: "scorching", label: "Reported affected vegetation boundary",
            note: "Nominal 5.4 m by 5.2 m ellipse. The source describes apparent burning, without a test of heating.", sourceIds: ["ceua"],
            marks: [{ type: "ellipse", x: 0, y: 0, rx: 2.7, ry: 2.6, estimated: true, label: "Approximate reported outer boundary" }] }
        ]
      }
    },
    {
      id: "ngatea_manuka_1969",
      title: "Ngātea mānuka patch",
      date: "1969-09-04",
      location: "Ngātea, Waikato, New Zealand",
      inventoryIds: ["hatch:Hatch_UDB_9410", "specialist:Eberhart_4722", "specialist:Johnson_5631"],
      evidenceOrigin: "original",
      summary: "Bert O’Neil examined a pale patch of standing mānuka on his farm and found three depressions near its middle. A university group recorded the site dimensions and separate ground marks.",
      limits: "September 4 is the date of close inspection. O’Neil noticed bleaching from a distance several weeks earlier. The field account does not establish a witnessed landing. Early visitors had already trampled the site and removed vegetation.",
      controls: "Field radiation checks and a gamma-spectrum test on a plant sample were reported as negative. Investigators disagreed about how the plants died and how the depressions formed.",
      sources: [
        { id: "fulton", label: "Harold H. Fulton, The Ngatea Mystery Circle, part 1", url: ngatea,
          locator: "Flying Saucer Review 16(2), pp. 27–28. Reproduces the university team's measurement report, ground sketch and photographs." },
        { id: "nzbc", label: "New Zealand Broadcasting Corporation, 1969 interviews",
          url: "https://www.ngataonga.org.nz/search-use-collection/search/31841/",
          locator: "Ngā Taonga Sound & Vision catalog record 31841. Archive lists interviews about the site." }
      ],
      traces: [
        {
          kind: "impression",
          observation: "Three shallow ground depressions near the middle of the affected plants formed a triangle with sides of 10 ft, 10 ft and 9 ft. A sketch also shows furrows around the depressions.",
          pattern: { label: "Measured isosceles outline with distinct furrows", families: ["three_point"], basis: "dimensions",
            edgesM: [3.048, 3.048, 2.7432], details: "The equal lengths are two reported spacings. The individual marks and furrows differ in shape and depth." },
          sourceIds: ["fulton"]
        },
        {
          kind: "surface",
          observation: "About 56 ft across, the main patch contained dead, bleached mānuka that remained standing. A separate taller stand nearby was also bleached.",
          pattern: { label: "Circular patch of standing discolored mānuka", families: ["ring"], basis: "dimensions",
            details: "The investigators described an affected circle and gave its approximate diameter. They did not measure a heat source or record a bearing from the ground marks to the boundary." },
          sourceIds: ["fulton"]
        }
      ],
      diagram: {
        title: "Ngātea ground triangle and estimated vegetation outline",
        basis: "Measured ground triangle with separate approximate vegetation boundary",
        note: "Local metres. The sketch gives the triangle’s sides, and the account places it near the middle of the bleached patch. The circle's alignment to the triangle is schematic. The furrows and taller bleached stand are omitted.",
        viewBox: [-10, -10, 20, 20],
        layers: [
          { kind: "surface", label: "Reported 56 ft vegetation patch",
            note: "Approximate diameter. The outline illustrates the near-center relationship, with no surveyed center offset.", sourceIds: ["fulton"],
            marks: [{ type: "ellipse", x: 0, y: 0, rx: 8.5344, ry: 8.5344, estimated: true, label: "Approximate circular patch of standing bleached plants" }] },
          { kind: "impression", label: "Reported ground depressions",
            note: "The three centers follow the reported 10 ft, 10 ft and 9 ft spacing. The source sketch gives distinct mark shapes and furrows.", sourceIds: ["fulton"],
            marks: [
              { type: "point", x: 0, y: -1.815, tag: "A", estimated: true, label: "Reconstructed depression A" },
              { type: "point", x: -1.3716, y: 0.907, tag: "B", estimated: true, label: "Reconstructed depression B" },
              { type: "point", x: 1.3716, y: 0.907, tag: "C", estimated: true, label: "Reconstructed depression C" }
            ] }
        ]
      }
    },
    {
      id: "oydeskyvatn_snow_1991",
      title: "Øydeskyvatn snow impressions",
      date: "1991-03-26",
      location: "Øydeskyvatn, Setesdalsheiene, Norway",
      inventoryIds: ["hatch:Hatch_UDB_15824"],
      evidenceOrigin: "original",
      summary: "Witnesses found three spiral-shaped snow impressions after several nights of light reports. Torfrid Urdal of UFO-Norge documented their dimensions, the witness account and a later visit to the site.",
      limits: "Witnesses found and photographed the traces on March 28. Urdal associates the marks with March 26. Snow and thaws altered the site before investigators arrived. The account gives no individual bearings or spiral directions.",
      controls: "A later visit reported ordinary pH and no radiation detected by the field instrument. The investigators collected samples from the center, an impression and outside the site. These checks did not establish a formation mechanism.",
      sources: [
        { id: "urdal", label: "Torfrid Urdal, UFO-Norge investigation", url: haukeli,
          locator: "UFO-Sverige reproduction. Paragraphs beginning with the March 28 discovery and April 9 visit." }
      ],
      traces: [
        {
          kind: "impression",
          observation: "Three spiral-shaped impressions in snow were described as 50–60 cm across, with about 3 m between them.",
          pattern: { label: "Three spiral impressions in a triangle", families: ["three_point", "swirl"], basis: "dimensions",
            details: "The account gives a single approximate spacing. It does not report three individually measured sides, the spirals' pitch or their handedness." },
          sourceIds: ["urdal"]
        },
        {
          kind: "surface",
          observation: "The witnesses described a brown-yellow depression between the circles and slight discoloration within them.",
          sourceIds: ["urdal"],
          context: "The account does not give the discolored area's boundary or identify heating as the cause."
        }
      ],
      diagram: {
        title: "Øydeskyvatn nominal snow impression spacing",
        basis: "Schematic from the reported nominal spacing and diameter range",
        note: "Local metres, with arbitrary orientation. Identical outlines use the 55 cm midpoint of the reported range. The circles show extents, without drawing unrecorded spiral directions. The discolored depression is described separately.",
        viewBox: [-0.5, -0.5, 4, 3.7],
        layers: [
          { kind: "impression", label: "Three reported spiral impression extents",
            note: "Three nominal 3 m separations illustrate the reported arrangement. Equality of the actual spacings was not measured in the source.", sourceIds: ["urdal"],
            marks: [
              { type: "ellipse", x: 0, y: 0, rx: 0.275, ry: 0.275, estimated: true, label: "Nominal extent of the first snow impression" },
              { type: "ellipse", x: 3, y: 0, rx: 0.275, ry: 0.275, estimated: true, label: "Nominal extent of the second snow impression" },
              { type: "ellipse", x: 1.5, y: 1.5 * Math.sqrt(3), rx: 0.275, ry: 0.275, estimated: true, label: "Nominal extent of the third snow impression" }
            ] }
        ]
      }
    },
    {
      id: "haselbach_linke",
      title: "Haselbach",
      date: "1950-06-17",
      location: "Near Haselbach, Thuringia, Germany",
      evidenceOrigin: "original",
      inventoryIds: ["specialist:Johnson_3525"],
      summary: "A CIA information report relays a Greek newspaper account of Oskar Linke's statement. He said he found a fresh-looking circular opening where the object had been.",
      limits: "The government document is an unevaluated press translation. The incident date is from the chronology. There is no survey of the opening, and the account describes flames in the air without recording scorched ground.",
      sources: [
        { id: "cia", label: "CIA information report 00-W-23682, archived scan", url: linke + "#page=3", locator: "DOC_0000015464, PDF p. 3, Linke's account of the opening." },
        { id: "johnson", label: "Johnson case chronology in UFO Data", url: "https://www.ufo-search.com/timeline/timeline_part2.html#440B3B95", locator: "Johnson_3525, dates the account to June 17, 1950." }
      ],
      traces: [
        {
          kind: "impression",
          observation: "The witness described a circular opening that appeared recently dug.",
          sourceIds: ["cia"],
          pattern: { label: "Single circular opening", families: ["ring", "isolated"], basis: "description", details: "Diameter and depth were unspecified." }
        }
      ]
    },
    {
      id: "montornes_la_roca",
      title: "Montornès–La Roca",
      date: "1955-03",
      location: "Near Montornès del Vallès and La Roca, Barcelona, Spain",
      evidenceOrigin: "catalog",
      inventoryIds: ["hatch:Hatch_UDB_4564"],
      summary: "The cited Spanish catalog reproduces a report of a low object near a cultivated field and records scorched grass and apparent tripod marks at the reported site.",
      limits: "The catalog describes the year as approximate. It cites Antonio Ribera as its firsthand source. Mark sizes, count, positions, and the outline of the scorched grass are unspecified.",
      sources: [
        { id: "olmos", label: "Vicente-Juan Ballester Olmos, A Catalogue of 200 Type-I UFO Events", url: olmos + "#page=16", locator: "Case 19, printed p. 4, source listed as Antonio Ribera." }
      ],
      traces: [
        { kind: "impression", observation: "The catalog described ground marks as resembling those of a tripod.", sourceIds: ["olmos"] },
        { kind: "scorching", observation: "Scorched grass was reported at the site.", sourceIds: ["olmos"] }
      ]
    },
    {
      id: "santa_monica_madrid",
      title: "Santa Mónica",
      date: "1967-06-01",
      location: "Santa Mónica, Madrid, Spain",
      evidenceOrigin: "catalog",
      inventoryIds: ["specialist:NICAP_DB_3582", "specialist:Johnson_3201"],
      summary: "The cited Ballester Olmos catalog describes three rectangular holes, burned grass and powder at a reported landing site. Its account associates the case with the separate San José de Valderas photograph.",
      limits: "The plotted triangle is a nominal reconstruction from a catalog description. The cited comparison photograph was taken elsewhere, and an International UFO Reporter analysis described it as a small model. That analysis does not resolve the origin of the ground marks.",
      sources: [
        { id: "olmos", label: "Vicente-Juan Ballester Olmos, A Catalogue of 200 Type-I UFO Events", url: olmos + "#page=23", locator: "Case 47, printed p. 11." },
        { id: "iur-photo", label: "International UFO Reporter, May 1977", url: gatReport + "#page=1", locator: "Newsfront, More on the Ummo Affair, concerning the separate San José de Valderas photograph." }
      ],
      traces: [
        {
          kind: "impression", observation: "The catalog gives three rectangular holes, each 15 × 30 cm, and describes an equilateral triangle 6 m on a side.",
          sourceIds: ["olmos"],
          pattern: { label: "Reported equilateral layout", families: ["three_point"], basis: "description", details: "Six metres is the reported nominal side length. The catalog does not give three independent measurements or orientation." }
        },
        { kind: "scorching", observation: "The catalog reports burned grass without locating or measuring its boundary.", sourceIds: ["olmos"] },
        { kind: "surface", observation: "Aluminum-colored powder was described in the middle of the triangle.", sourceIds: ["olmos"] }
      ],
      diagram: {
        title: "Santa Mónica nominal three-hole layout and reported central powder",
        basis: "Nominal geometry from catalog text",
        note: "Local metres. The nominal triangle and center point follow the catalog description. The orientation and boundary of burned grass are unknown.",
        viewBox: [-1, -1, 8, 7.2],
        layers: [
          {
            kind: "impression", label: "Reported hole centers",
            note: "Six-metre nominal triangle, with marks shown as point locations. Individual hole orientations are unspecified.", sourceIds: ["olmos"],
            marks: [
              { type: "point", x: 0, y: 0, tag: "A", label: "Nominal hole A", estimated: true },
              { type: "point", x: 6, y: 0, tag: "B", label: "Nominal hole B", estimated: true },
              { type: "point", x: 3, y: 5.196, tag: "C", label: "Nominal hole C", estimated: true }
            ]
          },
          {
            kind: "surface", label: "Reported central powder",
            note: "A point represents the report's center location. The deposit's extent is unknown.", sourceIds: ["olmos"],
            marks: [{ type: "point", x: 3, y: 1.732, label: "Reported central powder", estimated: true }]
          }
        ]
      }
    },
    {
      id: "joinville_vila_baumer",
      title: "Vila Baumer, Joinville",
      date: "1968-09",
      location: "Vila Baumer, Joinville, Santa Catarina, Brazil",
      evidenceOrigin: "original",
      inventoryIds: ["specialist:Eberhart_4623"],
      summary: "Carlos Varassin's published field account records a reported overnight encounter at a pottery yard, followed by a circular burn, a central soil depression, and separate tripod-like marks.",
      limits: "The article gives September 26 or 27, so the case uses month precision. The investigator arrived in 1971. The article gives a burn diameter and depression depth, without the inner diameter or the locations of the three marks.",
      controls: "The source describes an operating kiln and burning tires at the property. The burn and compression descriptions do not identify a cause.",
      sources: [
        { id: "sbedv", label: "Carlos Varassin field investigation in SBEDV Boletim 94–98", url: joinville + "#page=51", locator: "Printed pp. 41–44, PDF pp. 49–52. Trace description on printed p. 43." }
      ],
      traces: [
        {
          kind: "scorching", observation: "The account describes a patch of burned grass about 65 cm across.",
          sourceIds: ["sbedv"],
          pattern: { label: "Circular burn", families: ["ring"], basis: "dimensions", details: "One approximate diameter. The source does not give a width for the affected band." }
        },
        {
          kind: "impression", observation: "The soil in a smaller concentric area was described as compacted and depressed about 10 cm.",
          sourceIds: ["sbedv"],
          pattern: { label: "Central depression inside the burn", families: ["ring"], basis: "description", details: "The stated 10 cm is depth. The account does not give the depression's diameter." }
        },
        {
          kind: "impression", observation: "Separate marks attributed to a tripod were described as about 10 cm in diameter each.",
          sourceIds: ["sbedv"],
          context: "Their spacing and positions relative to the burn and central depression are unspecified."
        }
      ],
      diagram: {
        title: "Vila Baumer burn and central depression",
        basis: "Partial reconstruction from a field account",
        note: "The burn uses the reported 65 cm diameter. The inner outline illustrates concentric placement only. The three reported tripod-like marks have no recorded coordinates and cannot be plotted here.",
        viewBox: [-0.44, -0.44, 0.88, 0.88],
        layers: [
          {
            kind: "scorching", label: "Reported burn outline", sourceIds: ["sbedv"],
            note: "Approximate circular outline, 65 cm across.",
            marks: [{ type: "ellipse", x: 0, y: 0, rx: 0.325, ry: 0.325, label: "Reported 65 cm burn outline", estimated: true }]
          },
          {
            kind: "impression", label: "Central compacted depression", sourceIds: ["sbedv"],
            note: "The inner diameter is schematic. The stated depth is about 10 cm.",
            marks: [{ type: "ellipse", x: 0, y: 0, rx: 0.15, ry: 0.15, label: "Smaller concentric depression, diameter unknown", estimated: true }]
          }
        ]
      }
    },
    {
      id: "redding_mine_1969",
      title: "Redding mine, 1969",
      date: "1969-10-30",
      location: "Near Redding, California, United States",
      evidenceOrigin: "original",
      inventoryIds: ["specialist:Johnson_7306"],
      summary: "A field investigation published in 1978 describes a couple's 1969 report from a mining site. They reported an oval depression and recovered material after the observation.",
      limits: "The account gives one approximate width for the depression. It does not register the collected material to measured positions within it. The 1976 report from the same area is a separate event with no reported landing marks.",
      controls: "Samples remained with the witnesses for years. The report acknowledges the lack of site controls and discusses a possible lightning origin for some material.",
      sources: [
        { id: "iur", label: "International UFO Reporter, The Redding, California CE II Case", url: gatCloseout + "#page=7", locator: "March 1978, PDF pp. 7–8, Paul Cerny's investigation and laboratory summary." }
      ],
      traces: [
        {
          kind: "impression", observation: "The witnesses described a shallow oval depression, about 10 ft across and less than 2 in deep, in mine tailings.",
          sourceIds: ["iur"],
          pattern: { label: "Oval depression", families: ["oval"], basis: "dimensions", details: "One approximate width, with the second horizontal axis unspecified." }
        },
        { kind: "surface", observation: "They collected a sand pile and later recovered a metal lump nearby.", sourceIds: ["iur"] }
      ]
    },
    {
      id: "stara_cerkev",
      title: "Stara Cerkev",
      date: "1971-05",
      location: "Stara Cerkev near Kočevje, Slovenia",
      evidenceOrigin: "original",
      inventoryIds: ["specialist:Eberhart_4803"],
      summary: "Milos Kremelj published a witness interview describing a May 1971 observation of an object on the ground, followed by reports of pointed holes and burned grass.",
      limits: "The witness described three legs on the object and an unspecified number of holes. The publication reconstructs the object's departure but does not give a ground-trace plan or measure the burn perimeter.",
      sources: [
        { id: "kremelj", label: "Milos Kremelj, Close View of Landed Craft", url: stara + "#page=11", locator: "Canadian UFO Report 4(4), summer 1977, printed pp. 9–10, PDF pp. 11–12." }
      ],
      traces: [
        { kind: "impression", observation: "The witness described several pointed holes roughly 15–20 cm across and of similar depth.", sourceIds: ["kremelj"], context: "No exact number of holes, depths, spacing or bearings are given." },
        { kind: "scorching", observation: "The witness separately described grass as burned.", sourceIds: ["kremelj"] }
      ]
    },
    {
      id: "gaberke",
      title: "Gaberke",
      date: "1977-02-11",
      location: "Gaberke near Šoštanj, Slovenia",
      evidenceOrigin: "original",
      inventoryIds: ["hatch:Hatch_UDB_12530"],
      summary: "Milos Krmelj's field report describes five groups of ground marks, with three smaller tubular imprints in each group. Silvery dust was reported near the marks.",
      limits: "The article describes a pentagon with an average edge length of 2.4 m and does not give individual edge lengths or positions. A typical local mark can be illustrated from the stated dimensions, while the overall symmetry is undetermined.",
      controls: "The investigation identified glittering particles as ordinary mica. Investigators reported inconclusive plant tests and no positive radiation detection with their field instrument.",
      sources: [
        { id: "krmelj", label: "Milos Krmelj, UFO Landing in Yugoslavia", url: gatDimensions + "#page=6", locator: "MUFON UFO Journal 118, September 1977, printed pp. 6–8." }
      ],
      traces: [
        {
          kind: "impression", observation: "The report gives five mark groups in a pentagonal layout. Four groups were described as a nominal 13.7 cm triangle of tube marks about 5.4 cm across. The fifth group was tighter.",
          sourceIds: ["krmelj"],
          pattern: { label: "Pentagonal array with triangular subgroups", basis: "dimensions", details: "The 2.4 m value is a mean edge length. The array's other dimensions and absolute orientation are unspecified." }
        },
        { kind: "surface", observation: "Silvery dust was described as more concentrated around the mark groups.", sourceIds: ["krmelj"], context: "The laboratory interpretation was ordinary mica." }
      ],
      diagram: {
        title: "Gaberke nominal detail of one typical three-segment mark",
        basis: "Nominal mark detail from reported dimensions",
        note: "Local centimetres. The drawing illustrates the typical grouping described in the article. It omits the tighter fifth group and the pentagon of five groups, whose vertex positions were not reported.",
        viewBox: [-4, -4, 22, 20],
        layers: [
          {
            kind: "impression", label: "Three tubular imprint positions", sourceIds: ["krmelj"],
            note: "Diameter about 5.4 cm. The nominal triangular grouping uses 13.7 cm side lengths to illustrate the description. These are not independently measured sides.",
            marks: [
              { type: "ellipse", x: 0, y: 0, rx: 2.7, ry: 2.7, label: "First typical tube mark", estimated: true },
              { type: "ellipse", x: 13.7, y: 0, rx: 2.7, ry: 2.7, label: "Second typical tube mark", estimated: true },
              { type: "ellipse", x: 6.85, y: 11.86, rx: 2.7, ry: 2.7, label: "Third typical tube mark", estimated: true }
            ]
          }
        ]
      }
    },
    {
      id: "gatchellville",
      title: "Gatchellville",
      date: "1977-03-08",
      location: "Gatchellville, Pennsylvania, United States",
      evidenceOrigin: "original",
      inventoryIds: ["hatch:Hatch_UDB_12558", "specialist:NICAP_DB_4754", "specialist:Johnson_1384", "ufocat:93741"],
      summary: "John Lutz's field investigation documented a grass fire after witnesses reported a descending red light. It described three holes at the corners of an unburned triangle within the larger burn.",
      limits: "The field report gives March 8, while the NICAP-derived index says March 7. The observed light, holes and fire are associated by time and place in the reports. The relative positions leave the origin and number of sources unresolved.",
      controls: "A later lab comparison found normal background radioactivity in the site samples relative to controls. No petroleum residues were detected in sampled material, though the study could not rule out ignition elsewhere in the burn area. The investigators discussed ball lightning without concluding it was the cause.",
      sources: [
        { id: "report", label: "International UFO Reporter, case 2-4-44", url: gatReport + "#page=7", locator: "May 1977, PDF pp. 7–8. John Lutz's field investigation." },
        { id: "closeout", label: "International UFO Reporter, Gatchellville close-out", url: gatCloseout + "#page=6", locator: "March 1978, PDF p. 6, photos and laboratory controls." },
        { id: "phillips", label: "Ted Phillips, Quarterly Report—Physical Trace Cases", url: gatDimensions + "#page=7", locator: "MUFON UFO Journal, September 1977, case 1024. Three lengths of the unburned triangle, based on Lutz's report." }
      ],
      traces: [
        {
          kind: "impression", observation: "Three holes about 1 in across and 2¼ in deep were reported at the corners of the unburned triangle.",
          sourceIds: ["report", "phillips"],
          pattern: { label: "Three-point triangle", families: ["three_point"], basis: "dimensions", details: "The triangle was reported as 72 × 54 × 52 in. The source does not record the three vertices' bearings.", edgesM: gt }
        },
        {
          kind: "scorching", observation: "The report describes about 100 × 30 ft of burned grass, with an unburned triangle inside. It also describes a smaller affected area about 132 ft away.",
          sourceIds: ["report", "closeout"],
          pattern: { label: "Large burn with an unburned island", families: ["irregular"], basis: "dimensions", details: "The spans describe the main burn extent. Its boundary and orientation relative to the holes were not recorded precisely.", dimensions: { longM: 30.48, shortM: 9.144 } }
        }
      ],
      diagram: {
        title: "Gatchellville local three-hole geometry",
        basis: "Reconstruction from reported triangle lengths",
        note: "Local metres. The holes mark vertices of the unburned island. The substantially larger surrounding burn is described separately because its perimeter and orientation were not surveyed in this frame.",
        viewBox: [-0.3, -0.3, 2.45, 1.75],
        layers: [
          {
            kind: "impression", label: "Reported holes at the unburned triangle",
            note: "The three point positions are derived from the reported triangle lengths. Their orientation is arbitrary.", sourceIds: ["report", "phillips"],
            marks: [
              { type: "point", x: 0, y: 0, tag: "A", label: "Reconstructed hole A", estimated: true },
              { type: "point", x: gt[0], y: 0, tag: "B", label: "Reconstructed hole B", estimated: true },
              { type: "point", x: gtThirdX, y: gtThirdY, tag: "C", label: "Reconstructed hole C", estimated: true }
            ]
          }
        ]
      }
    },
    {
      id: "lanaria_trenches",
      title: "Lanaria",
      date: "1977-06-21",
      location: "Near Lanaria, Alberta, Canada",
      evidenceOrigin: "original",
      inventoryIds: ["hatch:Hatch_UDB_11745"],
      summary: "John Brent Musgrave's field account describes three trenches forming a Y and a separate narrow hole in a barley field. A report of a shiny object in the area three days earlier does not establish a landing.",
      limits: "Hatch dates this entry to 1975. The 1977 report calls it a recent June 21 discovery and identifies June 18 as Saturday, which agrees with 1977. The author visited after sightseers had disturbed the area.",
      controls: "The author reported later plant yellowing and considered uprooting by visitors as an explanation. The field report gives no evidence of scorching.",
      sources: [
        { id: "musgrave", label: "John Brent Musgrave, Strange Markings in Alberta", url: gatDimensions + "#page=9", locator: "MUFON UFO Journal 118, September 1977, printed p. 9." },
        { id: "hatch", label: "Larry Hatch case retained in UFO Data", url: "https://www.ufo-search.com/timeline/timeline_part4.html#AB463D3E", locator: "Hatch_UDB_11745, dates the marks to June 21, 1975." }
      ],
      traces: [
        {
          kind: "impression", observation: "Three slightly curving trenches radiated from a central junction. Each was about 56 in long and 2–4 in wide, sloping into the soil toward the end.",
          sourceIds: ["musgrave"],
          pattern: { label: "Three radiating trenches", families: ["three_point", "radial"], basis: "dimensions", details: "The reported arms were at right angles to each other and the base pointed 5° south of east. The angles from the base to each arm were unspecified." }
        },
        { kind: "impression", observation: "A separate hole about 4 in across and 18 in deep was reported northeast of the junction.", sourceIds: ["musgrave"], context: "Its distance from the junction was unspecified." }
      ],
      diagram: {
        title: "Lanaria nominal three-branch trench layout",
        basis: "Schematic from reported lengths and one included angle",
        note: "Local metres, with north toward the top. Each branch shows the nominal 1.42 m extent. The paired arms' 90° angle is preserved while their shared alignment relative to the base is schematic. Curvature, varying widths and the separately reported hole are unplotted.",
        viewBox: [-1.4, -1.35, 3.1, 2.65],
        layers: [
          {
            kind: "impression", label: "Three reported trenches", sourceIds: ["musgrave"],
            note: "The east-pointing base is 5° south of east. The paired arms are shown in one possible orientation consistent with their reported angle.",
            marks: [
              { type: "path", d: "M 0 0 L 1.417 0.124", label: "Base trench pointing 5° south of east", estimated: true },
              { type: "path", d: "M 0 0 L -1.095 -0.918", label: "One schematic arm of the reported Y", estimated: true },
              { type: "path", d: "M 0 0 L -0.918 1.095", label: "Other schematic arm of the reported Y", estimated: true }
            ]
          }
        ]
      }
    }
  ];
});
