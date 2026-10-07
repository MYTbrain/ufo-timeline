(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoFamousCasePresets = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  // Editorial navigation presets, independent of the sighting corpus. Dates are
  // reported calendar dates; centers/radii are approximate exploration areas.
  // A source documents a report or its history, not an extraterrestrial origin.
  const CATALOG_NOTE = "Date and vicinity presets show contextual corpus reports, not verified case membership. Map centers and search radii are approximate. Inclusion records historical interest, not a finding about origin.";
  const records = [];

  function source(title, url, kind) {
    return Object.freeze({ title: title, url: url, kind: kind || "secondary overview" });
  }
  function wiki(slug, title) {
    return source(title || "Historical overview (Wikipedia)", "https://en.wikipedia.org/wiki/" + slug, "secondary overview");
  }
  function nicap(path, title) {
    return source(title || "NICAP case archive", "https://www.nicap.org/" + path, "research archive");
  }
  function add(id, name, startIso, endIso, location, center, zoom, aliases, description, sources, options) {
    const settings = options || {};
    records.push(Object.freeze({
      id: "case_" + id,
      name: name,
      kind: "fixed",
      startIso: startIso,
      endIso: endIso || startIso,
      datePrecision: settings.datePrecision || (endIso && endIso !== startIso ? "range" : "day"),
      dateNote: settings.dateNote || "Reported event date; the preset does not establish a case match.",
      location: location,
      center: Object.freeze(center),
      zoom: zoom,
      radiusKm: settings.radiusKm || 75,
      coordinateStatus: "Approximate navigation center",
      aliases: Object.freeze(aliases),
      description: description,
      sources: Object.freeze(Array.isArray(sources) ? sources : [sources]),
    }));
  }

  add("nuremberg", "Nuremberg sky broadsheet", "1561-04-14", null, "Nuremberg, Germany", [49.45, 11.08], 9,
    ["Nurnberg", "Hans Glaser", "celestial phenomenon"], "A contemporary broadsheet describes unusual celestial forms; later UFO interpretations are distinct from the historical account.",
    wiki("1561_celestial_phenomenon_over_Nuremberg"), { dateNote: "14 April 1561 as given in the broadsheet; no historical calendar conversion applied." });
  add("basel", "Basel sky broadsheet", "1566-07-27", "1566-08-07", "Basel, Switzerland", [47.56, 7.59], 9,
    ["Samuel Coccius", "celestial phenomenon"], "A sixteenth-century pamphlet records unusual solar appearances on three dates; its UFO interpretation is retrospective.",
    wiki("1566_celestial_phenomenon_over_Basel"), { dateNote: "Reported pamphlet dates: 27–28 July and 7 August 1566; the range includes intervening days." });
  add("bonilla", "Bonilla observation", "1883-08-12", "1883-08-13", "Zacatecas, Mexico", [22.77, -102.57], 9,
    ["Jose Bonilla", "solar transit", "Zacatecas observatory"], "Astronomer José Bonilla reported objects crossing the Sun. Proposed natural explanations remain separate from the observation.", wiki("Bonilla_observation"));
  add("aurora", "Aurora airship story", "1897-04-17", null, "Aurora, Texas, United States", [33.06, -97.51], 9,
    ["Aurora crash", "mystery airship", "S E Haydon"], "A nineteenth-century newspaper crash story became local UFO folklore; its physical claims are unverified.", wiki("Aurora,_Texas,_UFO_incident"), { dateNote: "Conventional case date, 17 April 1897; historical retellings differ about the newspaper and alleged event timing." });
  add("los_angeles", "Battle of Los Angeles", "1942-02-24", "1942-02-25", "Los Angeles, California, United States", [34.05, -118.24], 8,
    ["Great Los Angeles Air Raid", "searchlights", "anti aircraft"], "Wartime alarms and an antiaircraft barrage later entered UFO literature; the episode does not establish an alien aircraft.", wiki("Battle_of_Los_Angeles"), { radiusKm: 150 });
  add("kenneth_arnold", "Kenneth Arnold", "1947-06-24", null, "Mount Rainier, Washington, United States", [46.85, -121.76], 8,
    ["flying saucers", "Cascade Mountains", "Mount Rainier"], "Pilot Kenneth Arnold reported nine objects near Mount Rainier, helping popularize the term flying saucer.",
    source("Smithsonian: 1947, Year of the Flying Saucer", "https://airandspace.si.edu/stories/editorial/1947-year-flying-saucer", "museum history"), { radiusKm: 200 });
  add("maury_island", "Maury Island", "1947-06-21", null, "Puget Sound, Washington, United States", [47.37, -122.45], 9,
    ["Harold Dahl", "Fred Crisman", "Maury Island hoax"], "Harold Dahl's claimed debris encounter became a prominent, widely disputed early saucer story.", wiki("Maury_Island_incident"));
  add("flight_105", "United Airlines Flight 105", "1947-07-04", null, "Boise–Pendleton route, United States", [44.75, -117.65], 7,
    ["Emil Smith", "Ralph Stephens", "Marty Morrow"], "An airliner crew reported multiple objects along its Pacific Northwest route during the 1947 sighting wave.", wiki("Flight_105_UFO_sighting"), { radiusKm: 250 });
  add("rhodes", "Rhodes photographs", "1947-07-07", null, "Phoenix, Arizona, United States", [33.45, -112.07], 9,
    ["William Rhodes", "shoe heel photographs"], "William Rhodes photographed a claimed aerial object; the images attracted official investigation and competing interpretations.", wiki("Rhodes_UFO_photographs"));
  add("roswell", "Roswell debris case", "1947-07-07", "1947-07-09", "Roswell region, New Mexico, United States", [33.75, -105.0], 7,
    ["Jesse Marcel", "Mac Brazel", "Mogul", "Roswell crash"], "The Army's July 1947 debris announcements became a major UFO controversy; the Air Force later attributed the debris to Project Mogul.", wiki("Roswell_incident"), { radiusKm: 200, dateNote: "Announcement/recovery-context window around the 8 July press release, not a claimed exact crash date." });
  add("mantell", "Mantell pursuit", "1948-01-07", null, "Fort Knox–Franklin, Kentucky, United States", [37.3, -86.15], 7,
    ["Thomas Mantell", "Godman Field", "Skyhook"], "Pilot Thomas Mantell died during an aerial pursuit; later official analysis considered a high-altitude balloon explanation.", wiki("Mantell_UFO_incident"), { radiusKm: 200 });
  add("chiles_whitted", "Chiles–Whitted", "1948-07-24", null, "Montgomery, Alabama, United States", [32.37, -86.3], 8,
    ["Clarence Chiles", "John Whitted", "Eastern Air Lines"], "Two airline pilots described a bright object near their aircraft; investigation considered a meteor among possible explanations.", wiki("Chiles-Whitted_UFO_encounter"), { radiusKm: 150 });
  add("gorman", "Gorman pursuit", "1948-10-01", null, "Fargo, North Dakota, United States", [46.88, -96.79], 9,
    ["George Gorman", "Gorman dogfight", "Hector Airport"], "A National Guard pilot pursued a light near Fargo. The Air Force ultimately offered a balloon explanation.", wiki("Gorman_dogfight"));
  add("green_fireballs", "New Mexico green fireballs", "1948-12-05", null, "Albuquerque region, New Mexico, United States", [35.08, -106.65], 7,
    ["Captain Goede", "green fireball", "Lincoln LaPaz"], "Early aircraft-crew reports of green fireballs prompted official attention; this preset focuses on the 5 December reports.", wiki("Green_fireballs"), { radiusKm: 250 });
  add("farmington", "Farmington sightings", "1950-03-15", "1950-03-18", "Farmington, New Mexico, United States", [36.73, -108.22], 9,
    ["Farmington armada", "New Mexico 1950"], "Local newspapers reported numerous aerial-object sightings over several days; this is a contextual date window.",
    [nicap("chronos/1950fullrep.htm", "NICAP: 1950 chronology"), source("Farmington Daily Times, 18 March 1950 (transcription)", "https://www.ufology.patrickgross.org/press/farmingtondailytimes18mar1950.htm", "contemporary newspaper transcription")], { dateNote: "Broad 15–18 March context; surviving press coverage is strongest for 17–18 March and the range edges are uncertain." });
  add("mcminnville", "McMinnville photographs", "1950-05-11", null, "Sheridan–McMinnville, Oregon, United States", [45.1, -123.33], 9,
    ["Paul Trent", "Evelyn Trent", "Trent photographs"], "Paul and Evelyn Trent's photographs became famous; analyses have differed over whether they depict a suspended model.", wiki("McMinnville_UFO_photographs"));
  add("mariana", "Mariana film", "1950-08-15", null, "Great Falls, Montana, United States", [47.5, -111.3], 9,
    ["Nick Mariana", "Nicholas Mariana", "Great Falls film"], "Nick Mariana filmed two bright objects; official and independent analyses produced different interpretations.", wiki("Mariana_UFO_incident"));
  add("lubbock", "Lubbock Lights", "1951-08-25", "1951-09-05", "Lubbock, Texas, United States", [33.58, -101.85], 9,
    ["Carl Hart", "Texas Tech", "V formation"], "Witnesses reported formations of lights, and Carl Hart produced photographs. The preset includes the main late-August/early-September accounts.", wiki("Lubbock_Lights"));
  add("tremonton", "Tremonton film", "1952-07-02", null, "Tremonton, Utah, United States", [41.71, -112.17], 9,
    ["Delbert Newhouse", "Utah film", "Newhouse film"], "Navy photographer Delbert Newhouse filmed bright moving points; analysts debated their identification.",
    source("Released CIA record: Tremonton motion pictures", "https://documents2.theblackvault.com/documents/cia/ufos/C05515943.pdf", "archival document mirror"));
  add("nash_fortenberry", "Nash–Fortenberry", "1952-07-14", null, "Norfolk, Virginia, United States", [36.85, -76.29], 8,
    ["William Nash", "William Fortenberry", "Pan American"], "Two Pan American pilots reported glowing objects below their airliner near Norfolk.", wiki("Nash-Fortenberry_UFO_sighting"), { radiusKm: 150 });
  add("washington", "Washington radar sightings", "1952-07-12", "1952-07-29", "Washington, D.C., United States", [38.9, -77.04], 8,
    ["Washington National Airport", "Invasion of Washington", "1952 radar"], "Radar contacts and visual reports around Washington prompted public briefings and debate over atmospheric and other explanations.", wiki("1952_Washington,_D.C.,_UFO_incident"), { radiusKm: 150 });
  add("flatwoods", "Flatwoods encounter", "1952-09-12", null, "Flatwoods, West Virginia, United States", [38.72, -80.65], 9,
    ["Flatwoods monster", "Braxton County monster", "Braxie"], "Witnesses described a frightening figure after seeing a light in the sky; meteor and owl explanations have been proposed.", wiki("Flatwoods_monster"));
  add("oloron", "Oloron angel-hair reports", "1952-10-17", null, "Oloron-Sainte-Marie, France", [43.19, -0.61], 9,
    ["angel hair", "Oloron Sainte Marie", "siliceous cotton"], "Witnesses reported aerial shapes and falling filaments; migrating spider silk is among the proposed explanations.", wiki("UFO_sightings_in_France#1952"));
  add("ellsworth", "Ellsworth radar encounter", "1953-08-05", "1953-08-06", "Rapid City, South Dakota, United States", [44.15, -103.1], 8,
    ["Rapid City", "Ellsworth AFB", "F 84"], "Ground observers, radar operators and pilots reported lights near Rapid City; archival accounts document the investigation.",
    nicap("530805ellsworth_dir.htm", "NICAP: Ellsworth case documents"), { radiusKm: 150 });
  add("quarouble", "Quarouble / Marius Dewilde", "1954-09-10", null, "Quarouble, France", [50.39, 3.62], 9,
    ["Marius Dewilde", "railway encounter", "Quarouble landing"], "Marius Dewilde described figures and a vehicle beside railway tracks; his account helped shape French UFO literature.", wiki("Marius_Dewilde"));
  add("florence", "Florence stadium sighting", "1954-10-27", null, "Florence, Italy", [43.78, 11.28], 9,
    ["Fiorentina", "Pistoiese", "Stadio Artemio Franchi", "angel hair"], "A football crowd reported unusual aerial objects and falling filaments; witnesses and later commentators offered differing interpretations.",
    [wiki("Stadio_Artemio_Franchi"), source("BBC: The day UFOs stopped play", "https://www.bbc.com/news/magazine-29342407", "news history")] );
  add("kelly_hopkinsville", "Kelly–Hopkinsville", "1955-08-21", "1955-08-22", "Kelly, Kentucky, United States", [36.98, -87.46], 9,
    ["Hopkinsville goblins", "Kelly green men", "Sutton family"], "A family reported small figures around a farmhouse. Police found no beings; natural and hoax interpretations remain part of the history.", wiki("Kelly%E2%80%93Hopkinsville_encounter"));
  add("lakenheath", "Lakenheath–Bentwaters", "1956-08-13", "1956-08-14", "Suffolk, England, United Kingdom", [52.2, 0.95], 8,
    ["RAF Lakenheath", "RAF Bentwaters", "Forrest Perkins", "Venom"], "Radar and visual reports at two air bases became a prominent investigation case; later reconstructions disagree on parts of the sequence.", wiki("Lakenheath-Bentwaters_incident"), { radiusKm: 150 });
  add("rb47", "RB-47 encounter", "1957-07-17", null, "Mississippi–Texas route, United States", [32.75, -96.8], 6,
    ["RB 47", "RB47", "electronic intelligence", "McClure", "Chase"], "An RB-47 crew reported light sightings and electronic signals during a multi-state flight; their relationship is contested.",
    source("Project Blue Book: RB-47 case records", "https://www.theblackvault.com/documentarchive/project-blue-book-the-rb-47-ufo-incident-july-17-1957/", "archival document mirror"), { radiusKm: 600 });
  add("vilas_boas", "Antônio Vilas-Boas", "1957-10-15", "1957-10-16", "São Francisco de Sales, Brazil", [-19.86, -49.77], 9,
    ["Antonio Villas Boas", "Vilas Boas", "Brazil abduction"], "Vilas-Boas described an alleged abduction while farming at night; the account is testimony rather than demonstrated extraterrestrial contact.", wiki("Antonio_Vilas-Boas"), { dateNote: "Night spanning 15–16 October 1957; summaries use either date." });
  add("levelland", "Levelland vehicle reports", "1957-11-02", "1957-11-03", "Levelland, Texas, United States", [33.59, -102.38], 9,
    ["Levelland lights", "engine interference", "Pedro Saucedo"], "Drivers reported lights and stalled engines around Levelland; reported coincidence does not establish an electromagnetic cause.", wiki("Levelland_UFO_case"));
  add("kirtland", "Kirtland tower sighting", "1957-11-04", null, "Albuquerque, New Mexico, United States", [35.05, -106.59], 9,
    ["Kirtland AFB", "Kaser", "Brink"], "Two airfield controllers described a light and dark object; radar and visual observations were investigated.", wiki("Kirtland_AFB_UFO_sighting"));
  add("trindade", "Trindade Island photographs", "1958-01-16", null, "Trindade Island, Brazil", [-20.51, -29.33], 8,
    ["Almiro Barauna", "Almirante Saldanha", "Trinidad island photographs"], "Photographs attributed to Almiro Baraúna became a celebrated and disputed Brazilian UFO case.", nicap("580116trindade_dir.htm", "NICAP: Trindade case directory"), { radiusKm: 150 });
  add("red_bluff", "Red Bluff police sighting", "1960-08-13", null, "Red Bluff, California, United States", [40.18, -122.24], 9,
    ["Charles Carson", "Stanley Scott", "California Highway Patrol"], "Highway patrol officers described a lighted object; their account and official explanations were contested.",
    source("Red Bluff: contemporary reports and chronology", "https://www.saturdaynightuforia.com/html/articles/articlehtml/redbluff-1960.html", "research archive"));
  add("eagle_river", "Eagle River / Joe Simonton", "1961-04-18", null, "Eagle River, Wisconsin, United States", [45.92, -89.24], 9,
    ["Joe Simonton", "pancakes", "Eagle River encounter"], "Joe Simonton described exchanging water for food with alleged craft occupants; an analyzed fragment was ordinary terrestrial food.", wiki("Eagle_River_encounter"));
  add("betty_barney_hill", "Betty and Barney Hill", "1961-09-19", "1961-09-20", "White Mountains, New Hampshire, United States", [44.04, -71.68], 8,
    ["Barney and Betty Hill", "Hill abduction", "Indian Head", "Route 3", "Interrupted Journey"], "The Hills reported a roadside sighting and missing time; later abduction recollections and interpretations require separate assessment.",
    [source("UNH: Betty and Barney Hill collection", "https://library.unh.edu/find/archives/collections/using-materials/using-betty-barney-hill-collection", "university archive"), wiki("Barney_and_Betty_Hill_incident")], { radiusKm: 150 });
  add("socorro", "Socorro / Lonnie Zamora", "1964-04-24", null, "Socorro, New Mexico, United States", [34.06, -106.89], 9,
    ["Lonnie Zamora", "Socorro landing", "Sam Chavez"], "Police officer Lonnie Zamora reported an object rising from an arroyo; official investigators examined the account and site.", wiki("Lonnie_Zamora_incident"));
  add("valensole", "Valensole / Maurice Massé", "1965-07-01", null, "Valensole, France", [43.84, 5.99], 9,
    ["Maurice Masse", "lavender field", "Valensole landing"], "Farmer Maurice Massé described a landed vehicle and small figures; this preset navigates the reported date and area.", wiki("UFO_sightings_in_France#1965"));
  add("exeter", "Exeter / Kensington", "1965-09-03", null, "Kensington, New Hampshire, United States", [42.95, -70.96], 9,
    ["Norman Muscarello", "Eugene Bertrand", "David Hunt", "Incident at Exeter"], "A teenager and police officers reported lights near Kensington; the account became the subject of Incident at Exeter.", wiki("Exeter_incident"));
  add("kecksburg", "Kecksburg", "1965-12-09", null, "Kecksburg, Pennsylvania, United States", [40.18, -79.46], 9,
    ["Kecksberg", "acorn", "Pennsylvania fireball"], "A widely seen fireball became associated with local recovery claims. NASA's released records document later records inquiries, not a confirmed spacecraft recovery.",
    [source("NASA: released Kecksburg records", "https://www.hq.nasa.gov/office/pao/FOIA/Kecksberg-UFO.pdf", "government records"), wiki("Kecksburg_UFO_incident")] );
  add("michigan_1966", "Michigan swamp-gas controversy", "1966-03-20", "1966-03-21", "Dexter–Hillsdale, Michigan, United States", [42.15, -84.05], 8,
    ["Dexter", "Hillsdale", "Frank Mannor", "J Allen Hynek", "swamp gas"], "Michigan sighting reports and Hynek's swamp-gas suggestion generated public controversy and congressional attention.", wiki("Michigan_%22swamp_gas%22_UFO_reports"), { radiusKm: 150 });
  add("westall", "Westall school", "1966-04-06", null, "Clayton South, Melbourne, Australia", [-37.95, 145.13], 9,
    ["Westall High School", "Grange Reserve", "Melbourne school"], "Students and a teacher reported an aerial object near their school; descriptions and proposed explanations vary.", wiki("Westall_UFO"));
  add("portage", "Portage County police pursuit", "1966-04-17", null, "Portage County, Ohio–Pennsylvania, United States", [40.95, -80.72], 8,
    ["Dale Spaur", "Wilbur Neff", "Ravenna", "Conway"], "Police officers pursued a light from Ohio toward Pennsylvania; the official identification and witness account differed.",
    nicap("newsclippings/1966/1966_04_17_US_OH_Ravenna.pdf", "NICAP: Portage County report"), { radiusKm: 200 });
  add("malmstrom", "Malmstrom missile controversy", "1967-03-16", null, "Malmstrom missile region, Montana, United States", [47.25, -109.4], 7,
    ["Echo Flight", "Robert Salas", "Malmstrom AFB", "missile shutdown"], "Missile outages and later UFO testimony became linked in public accounts; a causal connection is disputed.",
    nicap("chronos/1967fullrep.htm", "NICAP: 1967 chronology"), { radiusKm: 250, dateNote: "16 March Echo Flight outage context; later accounts also discuss distinct events and dates." });
  add("falcon_lake", "Falcon Lake", "1967-05-20", null, "Falcon Lake, Manitoba, Canada", [49.74, -95.2], 9,
    ["Stefan Michalak", "Stephen Michalak", "Whiteshell Provincial Park"], "Prospector Stefan Michalak reported a close encounter and injuries. Canadian archival records document reports and investigation, with unresolved interpretation.",
    source("Library and Archives Canada: Falcon Lake", "https://www.canada.ca/en/library-archives/collection/engage-learn/podcasts/discover/episode-053.html", "government archive history"));
  add("cussac", "Cussac encounter", "1967-08-29", null, "Cussac, Cantal, France", [44.99, 2.93], 9,
    ["Cussac children", "Cantal", "Close encounter of Cussac"], "Two children described a bright sphere and figures while herding cattle; the account was examined by French investigators.", wiki("UFO_sightings_in_France#1967"));
  add("shag_harbour", "Shag Harbour", "1967-10-04", null, "Shag Harbour, Nova Scotia, Canada", [43.5, -65.74], 9,
    ["Shag Harbor", "Nova Scotia", "water impact"], "Witnesses reported a lighted object entering the water. Canadian agencies searched but did not establish its identity.", wiki("Shag_Harbour_UFO_incident"));
  add("minot", "Minot radar and visual reports", "1968-10-24", null, "Minot region, North Dakota, United States", [48.6, -101.6], 8,
    ["Minot AFB", "B 52", "Minot radar"], "Ground personnel and a B-52 crew reported observations near Minot; the archived investigation contains differing identification proposals.", nicap("681024minot_dir.htm", "NICAP: Minot case documents"), { radiusKm: 200 });
  add("jimmy_carter", "Jimmy Carter sighting", "1969-01-01", "1969-12-31", "Leary, Georgia, United States", [31.49, -84.51], 9,
    ["Leary", "Carter UFO report", "Lions Club"], "Jimmy Carter reported a luminous object before a Lions Club meeting. Published accounts differ on the exact event date.", wiki("Jimmy_Carter_UFO_incident"), { datePrecision: "year", dateNote: "Year-only exploration window because the report date and reconstructed event date differ." });
  add("berkshire", "Berkshire County / Labor Day", "1969-09-01", null, "Sheffield–Great Barrington, Massachusetts, United States", [42.17, -73.36], 9,
    ["Berkshires", "Thomas Reed", "Labor Day 1969", "Sheffield"], "Several families later described unusual experiences in the Berkshires; local commemoration recognizes the accounts without establishing their origin.", wiki("Labor_Day_1969_UFO_Incident"));
  add("delphos", "Delphos ground-ring report", "1971-11-02", null, "Delphos, Kansas, United States", [39.28, -97.77], 9,
    ["Ronald Johnson", "glowing ring", "Delphos ring"], "A teenager reported a luminous object and a ring on the ground; subsequent soil interpretations remain contested.",
    nicap("NSID/NSID_DBListingbyStateCountry.pdf", "NICAP sighting index: Delphos 711102"));
  add("pascagoula", "Pascagoula", "1973-10-11", null, "Pascagoula, Mississippi, United States", [30.37, -88.56], 9,
    ["Charles Hickson", "Calvin Parker", "Pascagoula abduction"], "Charles Hickson and Calvin Parker reported an abduction while fishing; the case rests principally on their accounts and later testimony.", wiki("Pascagoula_Abduction"));
  add("coyne", "Coyne helicopter encounter", "1973-10-18", null, "Mansfield, Ohio, United States", [40.76, -82.51], 8,
    ["Lawrence Coyne", "Army Reserve helicopter", "Mansfield helicopter"], "An Army Reserve helicopter crew described a nearby object and green light; reported vehicle effects require independent assessment.", nicap("chronos/1973fullrep.htm", "NICAP: Coyne encounter chronology"), { radiusKm: 150 });
  add("berwyn", "Berwyn Mountains", "1974-01-23", null, "Llandrillo, Wales, United Kingdom", [52.92, -3.43], 9,
    ["Welsh Roswell", "Bala earthquake", "Berwyn Mountain"], "Lights and a tremor developed into a UFO-crash story; an earthquake and meteor are documented parts of the explanation.", wiki("Berwyn_Mountain_UFO_incident"));
  add("john_lennon", "John Lennon and May Pang", "1974-08-23", null, "Manhattan, New York, United States", [40.74, -73.97], 9,
    ["May Pang", "Lennon UFO", "Nobody Told Me"], "John Lennon and May Pang described an unusual object seen from a New York apartment; this is a reported witness account.", wiki("John_Lennon_UFO_incident"));
  add("travis_walton", "Travis Walton", "1975-11-05", "1975-11-10", "Heber region, Arizona, United States", [34.38, -110.55], 8,
    ["Fire in the Sky", "Turkey Springs", "Mike Rogers", "Walton abduction"], "Walton disappeared after a logging crew reported a light; his later abduction account remains disputed.", wiki("Travis_Walton_incident"), { radiusKm: 150, dateNote: "Initial reported encounter through Walton's return; includes intervening days." });
  add("tehran", "Tehran intercept", "1976-09-19", null, "Tehran, Iran", [35.72, 51.42], 8,
    ["Iran F 4", "Parviz Jafari", "Tehran radar"], "Iranian pilots and controllers reported a bright object and instrument problems; official records preserve the reports without proving an extraterrestrial cause.", wiki("1976_Tehran_UFO_incident"), { radiusKm: 200 });
  add("broad_haven", "Broad Haven school", "1977-02-04", null, "Broad Haven, Wales, United Kingdom", [51.78, -5.1], 9,
    ["Broad Haven Primary School", "Welsh triangle", "Dyfed", "David Davies"], "Schoolchildren described an object in a field; the episode became part of the wider Welsh Triangle reports.",
    source("BBC: Broad Haven school witnesses", "https://www.bbc.com/news/uk-wales-south-west-wales-38723643", "news history"));
  add("colares", "Colares / Operation Saucer", "1977-01-01", "1977-12-31", "Colares, Pará, Brazil", [-0.94, -48.28], 8,
    ["Operacao Prato", "Operação Prato", "Operation Saucer", "Chupa Chupa", "Brazil lights"], "Reports of lights and alleged injuries prompted a Brazilian military investigation; this year window provides regional context.", wiki("Opera%C3%A7%C3%A3o_Prato"), { radiusKm: 200, datePrecision: "year", dateNote: "Broad 1977 context window for a series of reports and the military investigation." });
  add("petrozavodsk", "Petrozavodsk lights", "1977-09-20", null, "Petrozavodsk, Russia", [61.79, 34.35], 7,
    ["Petrozavodsk phenomenon", "jellyfish", "Kosmos 955"], "A widespread luminous display prompted Soviet study; rocket-launch effects became a principal explanation.", wiki("Petrozavodsk_phenomenon"), { radiusKm: 300 });
  add("valentich", "Frederick Valentich", "1978-10-21", null, "Bass Strait, Australia", [-39.0, 144.1], 7,
    ["Valentich disappearance", "King Island", "Cape Otway", "Delta Sierra Juliet"], "Pilot Frederick Valentich disappeared after reporting an unusual aircraft; his radio account does not establish what caused the disappearance.", wiki("Frederick_Valentich"), { radiusKm: 250 });
  add("kaikoura", "Kaikōura lights", "1978-12-21", "1978-12-31", "Kaikōura coast, New Zealand", [-42.4, 173.68], 8,
    ["Kaikoura", "Quentin Fogarty", "Safe Air", "New Zealand lights"], "Aircraft crews and a television team recorded lights near Kaikōura; radar, film and proposed identifications were debated.", wiki("Kaikoura_lights"), { radiusKm: 200, dateNote: "Reports on 21 December and the night of 30–31 December; includes intervening days." });
  add("robert_taylor", "Robert Taylor / Livingston", "1979-11-09", null, "Dechmont Law, Livingston, Scotland", [55.9, -3.55], 9,
    ["Bob Taylor", "Dechmont Woods", "Livingston incident"], "Forestry worker Robert Taylor described an encounter in woodland; physical traces and possible medical explanations were examined.", wiki("Robert_Taylor_incident"));
  add("rendlesham", "Rendlesham Forest", "1980-12-26", "1980-12-28", "Rendlesham, Suffolk, England", [52.09, 1.43], 9,
    ["RAF Woodbridge", "RAF Bentwaters", "Charles Halt", "Jim Penniston", "John Burroughs"], "US Air Force personnel reported lights near Woodbridge; the Halt memorandum and later accounts differ in details and interpretation.", wiki("Rendlesham_Forest_incident"));
  add("cash_landrum", "Cash–Landrum", "1980-12-29", null, "Dayton–Huffman, Texas, United States", [30.08, -95.1], 9,
    ["Betty Cash", "Vickie Landrum", "Colby Landrum", "Texas diamond"], "Three witnesses attributed illness to an encounter with a bright object; their lawsuit and reported health effects did not establish the object's identity.", wiki("Cash%E2%80%93Landrum_incident"));
  add("trans_provence", "Trans-en-Provence", "1981-01-08", null, "Trans-en-Provence, France", [43.5, 6.49], 9,
    ["Renato Nicolai", "GEPAN", "landing trace"], "A witness described a landed object, and GEPAN examined ground and plant samples; the cause of the traces remains debated.", wiki("Trans-en-Provence_case"));
  add("nancy", "Nancy / amaranth case", "1982-10-21", null, "Nancy, France", [48.69, 6.18], 9,
    ["amaranth", "amarante", "Laxou", "GEPAN"], "A witness described an object near garden plants; investigators considered the reported observation and subsequent plant changes.", wiki("UFO_sightings_in_France#1982"));
  add("jal_1628", "Japan Air Lines Flight 1628", "1986-11-17", null, "Alaska flight route, United States", [64.3, -147.0], 6,
    ["JAL 1628", "Kenju Terauchi", "Kenji Terauchi", "Alaska cargo flight"], "A cargo-flight captain reported objects during an Alaska flight; FAA records and proposed identifications were later disputed.", wiki("Japan_Air_Lines_Cargo_Flight_1628_incident"), { radiusKm: 500 });
  add("gulf_breeze", "Gulf Breeze photographs", "1987-11-11", "1988-05-01", "Gulf Breeze, Florida, United States", [30.36, -87.16], 9,
    ["Ed Walters", "Gulf Breeze UFO", "Polaroid"], "Ed Walters publicized alleged UFO photographs; discovery of a model and photographic recreations became central to the hoax controversy.", wiki("Gulf_Breeze_UFO_incident"), { dateNote: "Window of the principal published Walters reports, including intervening days." });
  add("voronezh", "Voronezh park reports", "1989-09-27", null, "Voronezh, Russia", [51.67, 39.21], 9,
    ["Voronezh UFO", "Levoberezhny", "TASS"], "Children described a vehicle and figures in a park; news coverage and skeptical examinations helped spread the disputed story.", wiki("Voronezh_UFO_incident"));
  add("belgian_triangle", "Eupen / Belgian triangle reports", "1989-11-29", "1989-11-30", "Eupen, Belgium", [50.63, 6.03], 8,
    ["Belgium triangle", "Belgian wave", "Eupen gendarmes", "SOBEPS"], "Police and civilian accounts of lights near Eupen marked the opening of the Belgian wave; this window focuses on those reports.", wiki("Belgian_UFO_wave"), { radiusKm: 150 });
  add("calvine", "Calvine photograph", "1990-08-04", null, "Calvine, Perthshire, Scotland", [56.77, -3.98], 9,
    ["Calvine diamond", "Calvine UFO", "Craig Lindsay"], "A photograph attributed to a Perthshire sighting became public decades later; its subject and original account remain disputed.", wiki("Calvine_UFO"));
  add("montreal", "Montreal / Place Bonaventure", "1990-11-07", null, "Montreal, Quebec, Canada", [45.5, -73.57], 9,
    ["Montreal lights", "Place Bonaventure", "Hotel Bonaventure"], "Witnesses reported a formation of lights above Montreal; investigators considered atmospheric and reflected-light explanations.", wiki("UFO_sightings_in_Canada#Montreal"));
  add("michigan_1994", "Lake Michigan radar reports", "1994-03-08", null, "West Michigan, United States", [42.6, -86.1], 7,
    ["Michigan 1994", "Jack Bushong", "Holland", "weather radar"], "Residents and a weather-radar operator reported observations along western Michigan; the reports require comparison without assuming a single cause.", wiki("1994_Michigan_UFO_event"), { radiusKm: 250 });
  add("ariel_school", "Ariel School", "1994-09-16", null, "Ruwa, Zimbabwe", [-17.89, 31.24], 9,
    ["Ariel school children", "Ruwa school", "Cynthia Hind", "John Mack", "Zimbabwe school"], "Pupils reported an object and figures near their school. Interviews document their accounts, while explanations and interview influences remain debated.", wiki("Ariel_School_UFO_incident"));
  add("varginha", "Varginha", "1996-01-20", null, "Varginha, Minas Gerais, Brazil", [-21.55, -45.43], 9,
    ["Varginha incident", "Brazil creature", "Varginha UFO"], "Residents described strange figures and related UFO claims; military explanations and later witness accounts are contested.", wiki("Varginha_UFO_incident"));
  add("phoenix", "Phoenix Lights", "1997-03-13", null, "Phoenix region, Arizona, United States", [33.45, -112.07], 7,
    ["Lights over Phoenix", "Arizona V lights", "Fife Symington"], "Reports included moving formations and later stationary lights; distinct events and the flare explanation should be evaluated separately.", wiki("Phoenix_Lights"), { radiusKm: 300 });
  add("illinois_triangle", "Southern Illinois police sightings", "2000-01-05", null, "St. Clair–Madison counties, Illinois, United States", [38.6, -89.9], 8,
    ["Illinois triangle", "Highland", "Lebanon", "Millstadt", "Shiloh", "St Clair"], "Police officers and civilians described a large lighted shape across several towns; a submitted officer account preserves part of the chronology.",
    source("NUFORC report 11578: Lebanon officer account", "https://nuforc.org/sighting/?id=11578", "submitted witness report"), { radiusKm: 150 });
  add("nimitz", "USS Nimitz / Tic Tac", "2004-11-14", null, "Off southern California, United States", [31.5, -117.5], 7,
    ["Tic Tac", "David Fravor", "Alex Dietrich", "USS Princeton", "FLIR1"], "Navy pilots reported a visual encounter offshore. Congressional testimony records their account; released video alone does not establish origin.",
    [source("Congressional hearing: Fravor testimony", "https://www.govinfo.gov/content/pkg/CHRG-118hhrg53022/html/CHRG-118hhrg53022.htm", "official witness testimony"), wiki("USS_Nimitz_UFO_incident")], { radiusKm: 300 });
  add("ohare", "Chicago O’Hare", "2006-11-07", null, "O’Hare Airport, Chicago, United States", [41.98, -87.9], 9,
    ["O Hare", "O'Hare", "Chicago airport", "Gate C17", "United Airlines"], "Airport personnel reported an object over a terminal; the FAA treated the reports as a weather phenomenon.", wiki("2006_O%27Hare_International_Airport_UFO_sighting"));
  add("alderney", "Alderney pilot sightings", "2007-04-23", null, "Alderney and Channel Islands", [49.72, -2.2], 8,
    ["Ray Bowyer", "Aurigny", "Channel Islands UFO"], "Pilots and passengers reported bright objects near Alderney; a civil aviation report documented the encounter.", wiki("2007_Alderney_UFO_sighting"), { radiusKm: 150 });
  add("stephenville", "Stephenville lights", "2008-01-08", null, "Stephenville–Dublin, Texas, United States", [32.22, -98.2], 8,
    ["Erath County", "Dublin Texas", "Angelia Joiner", "Stephenville UFO"], "Witnesses reported unusual lights around Stephenville. Radar analyses and military flight information prompted competing interpretations.",
    source("MUFON Journal: February 2008 reports", "https://documents.theblackvault.com/documents/MUFON/Journals/2008/February_2008.pdf", "research publication mirror"), { radiusKm: 150 });
  add("norway_spiral", "Norway spiral", "2009-12-09", null, "Tromsø region, Norway", [69.65, 18.96], 7,
    ["Norwegian spiral", "Bulava", "Tromso"], "A spectacular spiral prompted UFO speculation; Russia acknowledged a failed missile test associated with the display.", wiki("2009_Norwegian_spiral_anomaly"), { radiusKm: 300 });
  add("harbour_mille", "Harbour Mille lights", "2010-01-25", null, "Harbour Mille, Newfoundland, Canada", [47.57, -54.85], 9,
    ["Newfoundland lights", "Harbor Mille", "missile shaped"], "Residents described objects over coastal Newfoundland; public photographs and later explanations are distinct evidence types.", wiki("UFO_sightings_in_Canada#Harbour_Mille_incident"));
  add("hangzhou", "Hangzhou Xiaoshan Airport", "2010-07-07", null, "Hangzhou, Zhejiang, China", [30.23, 120.43], 9,
    ["Xiaoshan", "Hangzhou airport", "China airport closure"], "A reported unidentified object accompanied an airport closure. Widely circulated photographs should not be assumed to depict the reported object.", wiki("UFO_sightings_in_China#2010"));

  function normalizeCaseOrder(order) {
    return String(order || "").trim().toLowerCase() === "chronological" ? "chronological" : "alphabetical";
  }
  function sortCases(items, order) {
    const chronological = normalizeCaseOrder(order) === "chronological";
    return (Array.isArray(items) ? items.slice() : []).sort(function (a, b) {
      const byName = a.name.localeCompare(b.name, "en");
      const byDate = a.startIso.localeCompare(b.startIso, "en");
      const byId = a.id.localeCompare(b.id, "en");
      return chronological ? byDate || byName || byId : byName || byDate || byId;
    });
  }
  const CASES = Object.freeze(sortCases(records, "alphabetical"));
  const BY_ID = new Map(CASES.map(function (item) { return [item.id, item]; }));

  function normalizeSearch(value) {
    return String(value == null ? "" : value).normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .toLowerCase().replace(/[’'`]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
  }
  const SEARCH_TEXT = new Map(CASES.map(function (item) {
    return [item.id, normalizeSearch([item.name, item.location, item.startIso, item.endIso, item.description].concat(item.aliases).join(" "))];
  }));

  function getCase(id) {
    return BY_ID.get(String(id || "")) || null;
  }
  function filterCases(query, order) {
    const tokens = normalizeSearch(query).split(/\s+/).filter(Boolean);
    if (!tokens.length) return sortCases(CASES, order);
    const matching = CASES.filter(function (item) {
      const haystack = SEARCH_TEXT.get(item.id);
      return tokens.every(function (token) { return haystack.indexOf(token) !== -1; });
    });
    return sortCases(matching, order);
  }
  function resolveCase(value) {
    return typeof value === "string" ? getCase(value) : value && getCase(value.id);
  }
  function formatCaseLabel(value, order) {
    const item = resolveCase(value);
    if (!item) return "";
    const firstYear = item.startIso.slice(0, 4);
    const lastYear = item.endIso.slice(0, 4);
    const years = firstYear + (lastYear !== firstYear ? "–" + lastYear : "");
    return normalizeCaseOrder(order) === "chronological"
      ? years + " · " + item.name
      : item.name + " · " + years;
  }
  function formatCaseDate(value) {
    const item = resolveCase(value);
    if (!item) return "";
    if (item.datePrecision === "year") return item.startIso.slice(0, 4) + " (year context)";
    if (item.datePrecision === "month") return item.startIso.slice(0, 7) + " (month context)";
    return item.startIso === item.endIso ? item.startIso : item.startIso + " to " + item.endIso;
  }
  function shiftIsoDay(iso, days) {
    if (typeof iso !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(iso) || !Number.isInteger(days)) return null;
    const date = new Date(iso + "T00:00:00.000Z");
    if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== iso) return null;
    date.setUTCDate(date.getUTCDate() + days);
    return Number.isFinite(date.getTime()) ? date.toISOString().slice(0, 10) : null;
  }
  function buildSelectionWindow(value) {
    const item = resolveCase(value);
    if (!item) return null;
    return Object.freeze({
      startIso: shiftIsoDay(item.startIso, -1), endIso: shiftIsoDay(item.endIso, 1), center: item.center,
      zoom: item.zoom, radiusKm: item.radiusKm, datePrecision: item.datePrecision,
    });
  }

  return Object.freeze({
    VERSION: 1, CATALOG_NOTE: CATALOG_NOTE, CASES: CASES,
    getCase: getCase, filterCases: filterCases, normalizeSearch: normalizeSearch,
    sortCases: sortCases, normalizeCaseOrder: normalizeCaseOrder,
    formatCaseLabel: formatCaseLabel, formatCaseDate: formatCaseDate,
    buildSelectionWindow: buildSelectionWindow,
  });
});
