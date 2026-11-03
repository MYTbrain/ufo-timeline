(function (root) {
  "use strict";

  function nuforc(id, values) {
    return {
      inventoryIds: ["nuforc:" + id],
      evidenceOrigin: "original",
      sources: [{
        id: "report", label: "NUFORC witness submission " + id,
        url: "https://nuforc.org/sighting/?id=" + id,
        locator: "Native report ID " + id + ". The retained NUFORC export carries the original submission text."
      }],
      ...values
    };
  }

  const cases = [
    {
      id: "donnybrook_north_dakota", title: "Donnybrook", date: "1966-08-19",
      location: "Donnybrook, North Dakota, United States", inventoryIds: ["bluebook:BB-10872"], evidenceOrigin: "original",
      summary: "The Air Force field report records two groups of three shallow depressions and displaced rocks. The witness reported a low hover.",
      limits: "The report provides a pooled spacing range, without individual lengths or positions for either group. Its sketch of three underside spots depicts the reported object.",
      controls: "The reporting officer considered wildlife a probable source of the marks and displaced rocks, citing grouse nesting and the behavior of coyotes and badgers.",
      sources: [
        { id: "file", label: "National Archives, Project Blue Book case 10872",
          url: "https://catalog.archives.gov/id/302554913", locator: "Donnybrook, North Dakota, August 19, 1966." },
        { id: "scan", label: "USAF Minot AFB report, reproduced scans",
          url: "https://www.theufochronicles.com/2013/01/ufo-lands-near-nuke-missile-sites.html",
          locator: "USAF report dated August 26, 1966, p. 3, preparing officer’s comments." }
      ],
      traces: [
        { kind: "impression", observation: "The field officer recorded two sets of three depressions arranged in triangles, with distances of about 9½ to 12½ ft.",
          sourceIds: ["scan"], pattern: { label: "Two reported three-mark groups", families: ["three_point"], basis: "dimensions",
            details: "The range covers the two groups. It supplies neither three distances for one group nor registration between them." } },
        { kind: "surface", observation: "The officer reported a swath of displaced rocks downslope.", sourceIds: ["scan"] }
      ]
    },
    {
      id: "porcieu_amblagnieu", title: "Porcieu-Amblagnieu", date: "1979-11-27",
      location: "Porcieu-Amblagnieu, Isère, France", inventoryIds: ["geipan:79-06"], evidenceOrigin: "original",
      summary: "GEPAN recorded a roughly sole-shaped area of flattened grass on a slope and a small clockwise spiral near its rounded tip.",
      limits: "The survey documents blade lay and local geometry. It leaves formation and any relationship to the reported light uncertain. The investigators considered a local vortex among the explanations.",
      sources: [{
        id: "report", label: "GEPAN Technical Note 8, investigation 79/06",
        url: "https://www.geipan.fr/sites/default/files/note_tech_8.pdf#page=82",
        locator: "PDF pp. 78–83, photographs and drawings 4.5–4.7. Chapter 4 describes the trace."
      }],
      traces: [
        {
          kind: "deformation", observation: "Investigators recorded grass laid generally from the tip toward the base, with maximum spans of 2.80 by 1.80 m.",
          context: "They reported no visible scorching or tearing of the flattened grass.",
          sourceIds: ["report"],
          pattern: { label: "Elongated patch with a rounded tip", families: ["oval"], basis: "dimensions",
            dimensions: { longM: 2.8, shortM: 1.8 }, details: "The patch outline is broadly elongated, with a distinct upper and lower end." }
        },
        {
          kind: "deformation", observation: "Within a small circle near the tip, investigators described blades laid clockwise from the center outward.",
          sourceIds: ["report"],
          pattern: { label: "Clockwise swirl near the tip", families: ["swirl"], handedness: "clockwise", basis: "dimensions",
            details: "Drawing 4.5 gives about 20 cm from the swirl center to the tip. A local swirl and the full patch are separate features." }
        }
      ],
      diagram: {
        title: "Porcieu flattened grass outline and local clockwise swirl",
        basis: "Redrawn from GEPAN drawings 4.5 and 4.6",
        note: "Positions follow the published plan. The dashed circle marks the recorded swirl zone. The short curves summarize the reported blade lay.",
        viewBox: [180, 255, 400, 445],
        layers: [
          { kind: "deformation", channel: "deformation", label: "Main flattened patch", note: "The maximum recorded spans were 2.80 and 1.80 m.", sourceIds: ["report"],
            marks: [{ type: "path", d: "M 237 641 Q 240 502 302 381 Q 333 311 366 311 Q 405 306 445 374 Q 515 485 523 655 Q 404 663 237 641 Z", label: "Outline of main flattened grass patch" }] },
          { kind: "deformation", channel: "twist", label: "Clockwise swirl near tip", note: "The field notes report clockwise lay from the center outward.", sourceIds: ["report"],
            marks: [
              { type: "ellipse", x: 369, y: 341, rx: 25, ry: 25, estimated: true, label: "Approximate local swirl zone" },
              { type: "path", d: "M 368 339 Q 378 345 369 354 Q 354 363 347 346 Q 337 323 362 316", label: "Schematic clockwise curve in the recorded swirl zone" }
            ] }
        ]
      }
    },
    {
      id: "le_guery_maize", title: "Le Guéry maize field", date: "1981-06-12",
      location: "France (site anonymized in GEPAN report)", inventoryIds: ["geipan:81-07"], evidenceOrigin: "original",
      summary: "A farm worker discovered damaged maize around disturbed soil. GEPAN mapped five angled holes and several zones of soil disturbance.",
      limits: "June 12 is the reported discovery day. GEPAN concluded that a lightning strike was a plausible and sufficient explanation for the main features. No direct detection established a strike at that spot.",
      controls: "GEPAN compared soil and plant samples and investigated local storms, eyewitness reports and potential ordinary mechanisms.",
      sources: [{
        id: "report", label: "GEPAN Technical Note 12, investigation 81/07",
        url: "https://www.geipan.fr/sites/default/files/note_tech_12.pdf#page=19",
        locator: "PDF pp. 5, 18–29 and 57–58. Figures 5–7 map holes and soil. The conclusion assesses lightning."
      }],
      traces: [
        {
          kind: "impression", observation: "The survey drew five holes with different axes and depths. The gendarmerie described two on one side and three roughly aligned on the other.",
          context: "The diagram follows the later GEPAN plan. The earlier gendarmerie distance description is approximate.",
          sourceIds: ["report"],
          pattern: { label: "Five holes on either side of a crop row", families: ["rows", "irregular"], basis: "dimensions",
            details: "The hole centers form two unequal groups. The source gives varied penetration axes and depths." }
        },
        {
          kind: "surface", observation: "Investigators drew disturbed and cracked soil near the holes. The gendarmerie described an approximately 18 m zone of drying or retarded maize growth farther out.",
          context: "The large crop zone is described separately from the close-up plan. Drying alone leaves the heat source uncertain.",
          sourceIds: ["report"],
          pattern: { label: "Broad drying zone and local soil disturbance", families: ["ring", "irregular"], basis: "dimensions",
            details: "The broad circular description applies to vegetation condition. The center soil boundary is visibly uneven." }
        }
      ],
      diagram: {
        title: "Le Guéry close-up of five holes and disturbed soil",
        basis: "Redrawn from GEPAN figure 5",
        note: "The plan shows the small central area, following the figure's north-up orientation. The roughly 18 m maize zone lies beyond this close-up.",
        viewBox: [95, 465, 390, 300],
        layers: [
          { kind: "surface", label: "Disturbed soil boundary", note: "The published close-up outlines the disturbed soil. The broad maize drying zone is at a different scale.", sourceIds: ["report"],
            marks: [{ type: "path", d: "M 132 679 Q 145 621 191 578 Q 218 543 281 535 Q 335 490 360 501 Q 380 507 400 558 L 437 659 Q 435 680 403 692 Q 360 710 288 716 L 232 722 Q 202 722 194 710 Q 172 719 149 704 Z", estimated: true, label: "Approximate disturbed soil boundary" }] },
          { kind: "impression", label: "Five surveyed holes", note: "Numbering and relative center positions come from the source figure.", sourceIds: ["report"],
            marks: [[366, 662], [262, 679], [250, 637], [248, 602], [342, 562]].map(([x, y], index) =>
              ({ type: "point", x, y, tag: String(index + 1), label: "Surveyed hole " + (index + 1) })) }
        ]
      }
    },
    nuforc(62115, {
      id: "titusville_yard_ring", title: "Titusville yard ring", date: "1973", location: "Titusville, Pennsylvania, United States",
      summary: "A later submission recounts seeing a circular groove in a relative’s yard as a child. The submitter places it in the summer of 1973 or 1974.",
      limits: "The source is a childhood recollection submitted in 2008. The catalog year is approximate. No contemporaneous measurement, photographs or formation mechanism were recovered.",
      traces: [{
        kind: "impression", observation: "The submitter estimated the groove at 10–15 ft across and perhaps 2–3 in deep, with broken grass.",
        context: "The submitter explicitly described the grass as unscorched.",
        sourceIds: ["report"], pattern: { label: "Reported circular groove", families: ["ring"], basis: "dimensions",
          details: "The diameter range is a recollection. It describes one groove." }
      }],
      diagram: {
        title: "Titusville estimated range of one groove",
        basis: "Nominal bounds from the witness’s diameter range",
        note: "Dashed circles show the low and high estimates of a single feature. The source gives no measured boundary or orientation.",
        viewBox: [-2.8, -2.8, 5.6, 5.6],
        layers: [{ kind: "impression", label: "Diameter bounds", note: "The recalled outside diameter is about 10–15 ft.", sourceIds: ["report"],
          marks: [1.524, 2.286].map((radius, index) => ({ type: "ellipse", x: 0, y: 0, rx: radius, ry: radius, estimated: true,
            label: index ? "Upper estimate of the one groove’s diameter" : "Lower estimate of the one groove’s diameter" })) }]
      }
    }),
    nuforc(32479, {
      id: "yermo_reed_swirl", title: "Yermo reed swirl", date: "2003-10", location: "Near Yermo, California, United States",
      summary: "The submitter examined a roughly oval area of flattened cattails and reported clockwise lay. The owner reported marks beneath the reeds.",
      limits: "The submission dates the alleged formation approximately October 10–11, with inspection later. No formation was witnessed. Positions of the brown reeds and possible bottom depressions were unmeasured.",
      traces: [
        {
          kind: "deformation", observation: "The observer estimated the flattened reed area at 20 by 15 ft and described clockwise lay.",
          sourceIds: ["report"], pattern: { label: "Oval with clockwise reed lay", families: ["oval", "swirl"], handedness: "clockwise",
            basis: "dimensions", dimensions: { longM: 6.096, shortM: 4.572 }, details: "The extent is an estimate from a dock. Local stem directions were not mapped." }
        },
        {
          kind: "impression", observation: "The submitter thought they could see bottom depressions. The owner described three or four roughly equidistant marks.",
          context: "These two accounts differ. The soft bottom was obscured and the mark positions remain uncertain.", sourceIds: ["report"]
        },
        { kind: "surface", observation: "The observer described a small area of brown reeds. The report provides no evidence of charring.", sourceIds: ["report"] }
      ],
      diagram: {
        title: "Yermo approximate flattened reed envelope",
        basis: "Nominal outline from the reported spans",
        note: "The approximate ellipse gives the 20 by 15 ft extent. Individual reed paths, brown vegetation and possible depressions have no plotted positions.",
        viewBox: [-3.8, -3, 7.6, 6],
        layers: [{ kind: "deformation", channel: "twist", label: "Clockwise reed lay envelope", note: "The observer described clockwise flattening.", sourceIds: ["report"],
          marks: [{ type: "ellipse", x: 0, y: 0, rx: 3.048, ry: 2.286, estimated: true, label: "Nominal extent of flattened cattails" }] }]
      }
    }),
    nuforc(157583, {
      id: "louisburg_grass_depression", title: "Louisburg grass depression", date: "2020-07-11",
      location: "Louisburg, North Carolina, United States",
      summary: "A witness reported seeing a descending light during a thunderstorm. The next morning the witness found an area of depressed high grass.",
      limits: "The witness submitted the report two days later. The text gives two approximate spans. Boundary shape and alignment were unavailable.",
      traces: [{
        kind: "deformation", observation: "The witness estimated the affected grass at about 12 by 12 ft.",
        sourceIds: ["report"], pattern: { label: "Two approximate grass spans", basis: "dimensions",
          dimensions: { longM: 3.6576, shortM: 3.6576 }, details: "Equal estimated spans are compatible with several outlines. The report supplies no perimeter shape." }
      }],
      diagram: {
        title: "Louisburg reported grass spans",
        basis: "Extent schematic",
        note: "Two lines encode the two estimated spans. Their intersection and display orientation are illustrative.",
        viewBox: [-2.4, -2.4, 4.8, 4.8],
        layers: [{ kind: "deformation", label: "Reported extents", note: "Two approximate 12 ft spans.", sourceIds: ["report"],
          marks: [{ type: "path", d: "M -1.8288 0 H 1.8288 M 0 -1.8288 V 1.8288", estimated: true, label: "Reported spans without a perimeter" }] }]
      }
    }),
    nuforc(90093, {
      id: "milton_grass_traces", title: "Milton grass traces", date: "2012-02-15", location: "Milton, Vermont, United States",
      summary: "A submitter described burnt spots, pressed grass in the middle and an unidentified white substance after a reported observation.",
      limits: "The report associates the burn spots with apparent legs. It gives no positions, distances or independently recovered photographs.",
      traces: [
        { kind: "scorching", observation: "The witness reported grass burnt where they believed the legs had been.", sourceIds: ["report"] },
        { kind: "deformation", observation: "The witness described pressed grass in the center.", sourceIds: ["report"] },
        { kind: "surface", observation: "The submitter also described a white substance on the pressed grass, with composition unknown.", sourceIds: ["report"] }
      ]
    }),
    nuforc(97103, {
      id: "cerrillos_reported_traces", title: "Cerrillos reported traces", date: "1977-07-24", location: "Cerrillos, New Mexico (catalog locality), United States",
      summary: "A retrospective report describes possible leg indentations and burnt grass near a reported encounter.",
      limits: "The submission dates to 2013. Its coordinates conflict with the catalog locality. The text gives no measured ground layout and associates the marks with the sighting by witness interpretation.",
      traces: [
        { kind: "impression", observation: "The submitter attributed indentations to three apparent legs.", sourceIds: ["report"],
          pattern: { label: "Reported possible support positions", families: ["three_point"], basis: "description", details: "The three-position reading comes from the witness account. Inter-mark measurements were unavailable." } },
        { kind: "scorching", observation: "The submitter reported burnt grass in an area they associated with light from the object.", sourceIds: ["report"] }
      ]
    }),
    nuforc(182042, {
      id: "arlington_radial_grass", title: "Arlington bent grass", date: "2024-06-02", location: "Arlington, Washington, United States",
      summary: "The submitter described seeing bent grass in a field the day after an observation. The description includes several apparent focal points.",
      limits: "The report describes the submitter’s interpretation of the grass lay. The source gives no dimensions, registered focal positions or attached video.",
      traces: [{
        kind: "deformation", observation: "The submitter described blades bending outward around focal points.",
        sourceIds: ["report"], pattern: { label: "Reported radial grass lay", families: ["radial"], basis: "description",
          details: "The report gives neither focal point coordinates nor measured local directions." }
      }]
    })
  ];

  if (typeof module === "object" && module.exports) module.exports = cases;
  root.UfoLandingSiteDirectReviewedCases = cases;
})(globalThis);
