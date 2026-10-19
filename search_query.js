(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.UfoSearchQuery = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  // Exact case-insensitive substrings, not words: "soil" also matches "topsoil".
  // Plain queries retain the original contiguous-substring behavior. Uppercase
  // AND/OR or a double quote opt into expressions; AND binds before OR. Bare
  // words between operators remain one substring, including interior spacing.
  // Parentheses have meaning only in expressions. No stemming, accent folding,
  // implicit Boolean operators, regular expressions, or executable query text.
  const VERSION = 1;
  const LIMITS = Object.freeze({ maxLength: 512, maxClauses: 32, maxDepth: 12 });
  const MODES = new Set(["auto", "literal", "all", "any", "expression"]);

  class QueryError extends Error {
    constructor(message, position, code) {
      super(message);
      this.name = "SearchQueryError";
      this.code = code || "invalid_query";
      this.position = Math.max(0, position || 0);
    }
  }

  function freeze(value) {
    if (value && typeof value === "object" && !Object.isFrozen(value)) {
      Object.keys(value).forEach(function (key) { freeze(value[key]); });
      Object.freeze(value);
    }
    return value;
  }

  function lexicalTokens(input, splitWords) {
    const tokens = [];
    let index = 0;
    let bareStart = -1;
    let bareEnd = -1;
    function flush() {
      if (bareStart >= 0) tokens.push({ type: "term", value: input.slice(bareStart, bareEnd), position: bareStart });
      bareStart = bareEnd = -1;
    }
    while (index < input.length) {
      if (/\s/.test(input[index])) { index += 1; continue; }
      const start = index;
      const character = input[index];
      if (character === '"') {
        flush();
        index += 1;
        let value = "";
        let closed = false;
        while (index < input.length) {
          const next = input[index++];
          if (next === '"') { closed = true; break; }
          if (next === "\\") {
            const escaped = input[index++];
            if (escaped !== '"' && escaped !== "\\") {
              throw new QueryError('Inside quotes, use \\" for a quote or \\\\ for a backslash.', index - 2, "invalid_escape");
            }
            value += escaped;
          } else value += next;
        }
        if (!closed) throw new QueryError("Close the quoted phrase with a double quote.", start, "unclosed_quote");
        if (!value.trim()) throw new QueryError("Enter some text inside the quoted phrase.", start, "empty_phrase");
        tokens.push({ type: "term", value: value, position: start, quoted: true });
        continue;
      }
      if (!splitWords && (character === "(" || character === ")")) {
        flush();
        tokens.push({ type: character, position: index++ });
        continue;
      }
      while (index < input.length && !/\s/.test(input[index]) && input[index] !== '"' &&
        (splitWords || (input[index] !== "(" && input[index] !== ")"))) index += 1;
      const value = input.slice(start, index);
      if (!splitWords && (value === "AND" || value === "OR")) {
        flush();
        tokens.push({ type: value.toLowerCase(), position: start });
      } else if (splitWords) tokens.push({ type: "term", value: value, position: start });
      else {
        if (bareStart < 0) bareStart = start;
        bareEnd = index;
      }
    }
    flush();
    return tokens;
  }

  function join(type, nodes) {
    if (nodes.length === 1) return nodes[0];
    const children = [];
    nodes.forEach(function (node) {
      if (node.type === type) children.push.apply(children, node.children);
      else children.push(node);
    });
    return { type: type, children: children };
  }

  function parseExpression(tokens, length) {
    let cursor = 0;
    let clauses = 0;
    function primary(depth) {
      const token = tokens[cursor];
      if (!token) throw new QueryError("Add a search term after the operator.", length, "missing_term");
      if (token.type === "(") {
        if (depth >= LIMITS.maxDepth) throw new QueryError("Use no more than " + LIMITS.maxDepth + " nested groups.", token.position, "too_deep");
        cursor += 1;
        const node = either(depth + 1);
        if (!tokens[cursor] || tokens[cursor].type !== ")") {
          throw new QueryError("Close the group with a right parenthesis.", token.position, "unclosed_group");
        }
        cursor += 1;
        return node;
      }
      if (token.type !== "term") throw new QueryError("Add a search term before this operator or closing parenthesis.", token.position, "missing_term");
      cursor += 1;
      clauses += 1;
      if (clauses > LIMITS.maxClauses) throw new QueryError("Use no more than " + LIMITS.maxClauses + " search terms.", token.position, "too_many_clauses");
      return { type: "term", value: token.value.toLowerCase() };
    }
    function both(depth) {
      const nodes = [primary(depth)];
      while (tokens[cursor] && tokens[cursor].type === "and") {
        cursor += 1;
        nodes.push(primary(depth));
      }
      return join("and", nodes);
    }
    function either(depth) {
      const nodes = [both(depth)];
      while (tokens[cursor] && tokens[cursor].type === "or") {
        cursor += 1;
        nodes.push(both(depth));
      }
      return join("or", nodes);
    }
    const ast = either(0);
    if (cursor !== tokens.length) {
      const token = tokens[cursor];
      throw new QueryError(token.type === ")" ? "Remove the unmatched closing parenthesis." :
        "Put AND or OR between these search terms.", token.position, token.type === ")" ? "unmatched_group" : "missing_operator");
    }
    return ast;
  }

  function grams(value, gramSize) {
    const result = [];
    const seen = new Set();
    for (let index = 0; index + gramSize <= value.length; index += 1) {
      const gram = value.slice(index, index + gramSize);
      if (!seen.has(gram)) { seen.add(gram); result.push(gram); }
    }
    return result;
  }

  function candidateNode(node) {
    if (!node) return null;
    if (node.type === "term") return { type: "term", value: node.value, grams: grams(node.value, 3) };
    return { type: node.type, children: node.children.map(candidateNode) };
  }

  function compile(query, options) {
    const supplied = query == null ? "" : String(query);
    if (supplied.length > LIMITS.maxLength) throw new QueryError("Keep the search within " + LIMITS.maxLength + " characters.", LIMITS.maxLength, "too_long");
    const input = supplied.trim();
    const requestedMode = options && options.mode || "auto";
    if (!MODES.has(requestedMode)) throw new QueryError("Choose a supported search mode.", 0, "invalid_mode");
    let mode = requestedMode;
    if (mode === "auto") {
      mode = input.indexOf('"') >= 0 || /(^|[\s(])(?:AND|OR)(?=$|[\s()"])/.test(input) ? "expression" : "literal";
    }
    let ast = null;
    if (input) {
      if (mode === "literal") ast = { type: "term", value: input.toLowerCase() };
      else if (mode === "all" || mode === "any") {
        const tokens = lexicalTokens(input, true);
        if (tokens.length > LIMITS.maxClauses) throw new QueryError("Use no more than " + LIMITS.maxClauses + " search terms.", 0, "too_many_clauses");
        ast = join(mode === "all" ? "and" : "or", tokens.map(function (token) { return { type: "term", value: token.value.toLowerCase() }; }));
      } else ast = parseExpression(lexicalTokens(input, false), input.length);
    }
    const terms = [];
    function visit(node) {
      if (!node) return;
      if (node.type === "term") { if (!terms.includes(node.value)) terms.push(node.value); }
      else node.children.forEach(visit);
    }
    visit(ast);
    return freeze({ version: VERSION, query: input, mode: mode, requestedMode: requestedMode, ast: ast,
      terms: terms, isEmpty: !ast, cacheKey: JSON.stringify([VERSION, ast]), candidate: candidateNode(ast),
      semantics: "case-insensitive substring", limits: LIMITS });
  }

  function matchesNode(node, text) {
    if (!node) return true;
    if (node.type === "term") return text.includes(node.value);
    if (node.type === "and") return node.children.every(function (child) { return matchesNode(child, text); });
    return node.children.some(function (child) { return matchesNode(child, text); });
  }

  function matches(plan, text) {
    return matchesNode(plan && plan.ast, String(text == null ? "" : text).toLowerCase());
  }

  // Keep this field order and separators identical to the legacy corpus scan.
  function serializeEvent(event) {
    const record = event || {};
    return [record.raw_event_block || "", record.description || "", record.time_display || "",
      record.location_display || "", record.location_raw || "", record.duration_display || "",
      (record.references || []).join("\n"), record.source || "", record.mapping_notes || "",
      JSON.stringify(record.extra_data || {}), JSON.stringify(record.parse_warnings || [])].join("\n").toLowerCase();
  }

  function matchEvent(plan, event) { return matchesNode(plan && plan.ast, serializeEvent(event)); }

  function normalizedOffsets(text) {
    const starts = [], ends = [];
    let offset = 0;
    // Lowercase can expand a character (for example capital dotted I). Keep
    // highlights attached to the original characters rather than folded offsets.
    for (const point of text) {
      const length = point.toLowerCase().length;
      for (let index = 0; index < length; index += 1) { starts.push(offset); ends.push(offset + point.length); }
      offset += point.length;
    }
    return { starts: starts, ends: ends };
  }

  function matchingRanges(plan, text, options) {
    const terms = plan && plan.terms || [];
    if (!text || !terms.length) return [];
    const lower = text.toLowerCase();
    const mapping = normalizedOffsets(text);
    const maxMatches = Math.min(256, Math.max(1, Number(options && options.maxMatches) || 128));
    const ranges = [];
    let count = 0;
    terms.forEach(function (term) {
      let start = 0, index;
      while (count < maxMatches && (index = lower.indexOf(term, start)) >= 0) {
        ranges.push([mapping.starts[index], mapping.ends[index + term.length - 1]]);
        count += 1;
        start = index + 1;
      }
    });
    ranges.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
    const merged = [];
    ranges.forEach(function (range) {
      const previous = merged[merged.length - 1];
      if (previous && range[0] <= previous[1]) previous[1] = Math.max(previous[1], range[1]);
      else merged.push(range.slice());
    });
    return merged;
  }

  function segmentsInRange(text, ranges, start, end) {
    const segments = [];
    let cursor = start;
    ranges.forEach(function (range) {
      const from = Math.max(start, range[0]), to = Math.min(end, range[1]);
      if (from >= to) return;
      if (from > cursor) segments.push({ text: text.slice(cursor, from), match: false });
      segments.push({ text: text.slice(from, to), match: true });
      cursor = to;
    });
    if (cursor < end || !segments.length) segments.push({ text: text.slice(cursor, end), match: false });
    return segments;
  }

  function highlightSegments(plan, value, options) {
    const text = String(value == null ? "" : value);
    return segmentsInRange(text, matchingRanges(plan, text, options), 0, text.length);
  }

  function excerpt(plan, value, options) {
    const text = String(value == null ? "" : value);
    const maxLength = Math.min(2000, Math.max(40, Number(options && options.maxLength) || 240));
    const lower = text.toLowerCase();
    let first = -1;
    (plan && plan.terms || []).forEach(function (term) {
      const found = lower.indexOf(term);
      if (found >= 0 && (first < 0 || found < first)) first = found;
    });
    const mapping = first >= 0 ? normalizedOffsets(text) : null;
    const firstOriginal = mapping ? mapping.starts[first] : 0;
    let start = text.length > maxLength ? Math.max(0, firstOriginal - Math.floor(maxLength / 3)) : 0;
    start = Math.min(start, Math.max(0, text.length - maxLength));
    let end = Math.min(text.length, start + maxLength);
    // Avoid cutting a UTF-16 surrogate pair when selecting the visible snippet.
    if (start > 0 && /[\uDC00-\uDFFF]/.test(text[start])) start -= 1;
    if (end < text.length && /[\uDC00-\uDFFF]/.test(text[end])) end -= 1;
    const snippet = text.slice(start, end);
    // Clip original match ranges, not a second search of the shortened text:
    // a long matching phrase may legitimately continue beyond the excerpt.
    const segments = segmentsInRange(text, matchingRanges(plan, text), start, end);
    return { text: snippet, segments: segments, start: start, end: end,
      leadingEllipsis: start > 0, trailingEllipsis: end < text.length,
      matched: segments.some(function (segment) { return segment.match; }) };
  }

  function candidateTokens(plan) {
    // Every emitted trigram is necessary for its term, but not necessarily for
    // the full Boolean query. Consumers must preserve candidate AND/OR structure.
    return plan && plan.candidate || null;
  }

  function wordParts(value) {
    return String(value == null ? "" : value).toLowerCase().match(/[\p{L}\p{M}\p{N}_]+/gu) || [];
  }

  function tokenize(value) { return Array.from(new Set(wordParts(value))); }

  function isWordFragment(value) {
    const text = String(value == null ? "" : value).toLowerCase();
    const parts = wordParts(text);
    return parts.length === 1 && parts[0] === text;
  }

  return Object.freeze({ VERSION: VERSION, LIMITS: LIMITS, QueryError: QueryError, compile: compile,
    matches: matches, match: matches, matchEvent: matchEvent, serializeEvent: serializeEvent,
    serializeSearchableEvent: serializeEvent, excerpt: excerpt, highlightSegments: highlightSegments,
    candidateTokens: candidateTokens, tokenize: tokenize, wordParts: wordParts, isWordFragment: isWordFragment });
});
