(function (root, factory) {
  "use strict";
  const common = typeof module === "object" && module.exports;
  if (!common && !root.UfoSearchQuery && typeof root.importScripts === "function") {
    const queryUrl = new URL("search_query.js", root.location.href);
    queryUrl.search = root.location.search;
    root.importScripts(queryUrl.href);
  }
  const api = factory(common ? require("./search_query.js") : root.UfoSearchQuery, root);
  if (common) module.exports = api;
  else {
    root.UfoSearchWorkerCore = api;
    if (typeof root.importScripts === "function" && typeof root.postMessage === "function") {
      let engine = null;
      const requests = new Map();
      root.addEventListener("message", async function (event) {
        const data = event.data || {};
        if (data.type === "cancel") { const controller = requests.get(data.requestId); if (controller) controller.abort(); return; }
        if (data.type === "destroy") { if (engine) engine.destroy(); requests.forEach(function (controller) { controller.abort(); }); return; }
        if (data.type !== "search" && data.type !== "excerpt") return;
        const controller = new AbortController();
        requests.set(data.requestId, controller);
        try {
          if (!engine) engine = api.create(data.config);
          const options = Object.assign({}, data.options, { signal: controller.signal,
            onProgress: function (progress) { root.postMessage({ type: "progress", requestId: data.requestId, progress: progress }); } });
          const result = data.type === "search" ? await engine.search(data.plan, options) : await engine.getExcerpt(data.id, data.plan, options);
          if (!controller.signal.aborted) root.postMessage({ type: "result", requestId: data.requestId, result: result });
        } catch (error) {
          root.postMessage({ type: "error", requestId: data.requestId,
            error: { name: error.name || "Error", message: error.message || String(error), code: error.code } });
        } finally { requests.delete(data.requestId); }
      });
    }
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (Query, root) {
  "use strict";
  function abortError() { const error = new Error("Search was cancelled."); error.name = "AbortError"; return error; }
  function check(signal) { if (signal && signal.aborted) throw abortError(); }
  function waiting(promise, signal) {
    if (!signal) return promise;
    check(signal);
    return new Promise(function (resolve, reject) {
      const abort = function () { reject(abortError()); };
      signal.addEventListener("abort", abort, { once: true });
      promise.then(function (value) { signal.removeEventListener("abort", abort); resolve(value); },
        function (error) { signal.removeEventListener("abort", abort); reject(error); });
    });
  }
  function lru(maxBytes) {
    const entries = new Map(); let used = 0;
    return { get: function (key) { const value = entries.get(key); if (!value) return null; entries.delete(key); entries.set(key,value); return value; },
      set: function (key,value) {
        if (value.byteLength > maxBytes) return;
        if (entries.has(key)) { used -= entries.get(key).byteLength; entries.delete(key); }
        entries.set(key,value); used += value.byteLength;
        while (used > maxBytes) { const first = entries.keys().next().value; used -= entries.get(first).byteLength; entries.delete(first); }
      }, clear: function () { entries.clear(); used = 0; } };
  }
  async function mapLimit(values, limit, action) {
    let cursor = 0;
    await Promise.all(Array.from({length:Math.min(limit,values.length)}, async function () {
      while (cursor < values.length) { const index = cursor++; await action(values[index],index); }
    }));
  }
  function limiter(limit) {
    let running = 0; const queue = [];
    function next() {
      while (running < limit && queue.length) {
        const task = queue.shift(); running += 1;
        Promise.resolve().then(task.action).then(task.resolve,task.reject).finally(function () { running -= 1; next(); });
      }
    }
    return function (action) { return new Promise(function (resolve,reject) { queue.push({action:action,resolve:resolve,reject:reject}); next(); }); };
  }
  async function unzip(bytes) {
    if (bytes[0] !== 31 || bytes[1] !== 139) throw new Error("The compressed search member is not a gzip stream.");
    if (typeof DecompressionStream !== "function") throw new Error("This browser cannot read the compressed search index.");
    return new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).arrayBuffer());
  }
  function decodeVarints(bytes, count, recordCount) {
    const ordinals = new Uint32Array(count);
    let length = 0, previous = 0, value = 0, multiplier = 1;
    for (const byte of bytes) {
      value += (byte & 127) * multiplier;
      if (!Number.isSafeInteger(value) || multiplier > 0x10000000) throw new Error("Invalid search posting integer.");
      if (byte & 128) multiplier *= 128;
      else {
        const ordinal = previous + value;
        if (length >= count || ordinal >= recordCount || (length && ordinal <= previous)) throw new Error("Search postings have invalid ordering or coverage.");
        ordinals[length++] = ordinal; previous = ordinal; value = 0; multiplier = 1;
      }
    }
    if (multiplier !== 1 || length !== count) throw new Error("Truncated search posting list.");
    return ordinals;
  }
  function intersect(a,b) {
    if (a === null) return new Set(b);
    if (b === null) return new Set(a);
    const smaller = a.size <= b.size ? a : b, larger = smaller === a ? b : a;
    return new Set(Array.from(smaller).filter(function (value) { return larger.has(value); }));
  }
  function union(a,b) { b.forEach(function (value) { a.add(value); }); return a; }
  function evaluate(node, leaves, count) {
    if (!node) return new Set(Array.from({length:count},function (_,index) { return index; }));
    if (node.type === "term") return leaves.get(node.value) || new Set();
    const children = node.children.map(function (child) { return evaluate(child,leaves,count); });
    return node.type === "and" ? children.reduce(intersect) : children.reduce(union,new Set());
  }
  function safeInteger(value) { return Number.isSafeInteger(value) && value >= 0; }

  function create(config) {
    config = config || {};
    if (!Query) throw new Error("The search query module is unavailable.");
    if (!config.manifestUrl) throw new Error("A search index manifest URL is required.");
    const fetcher = config.fetch || root.fetch.bind(root);
    const manifestUrl = String(config.manifestUrl);
    const concurrency = Math.min(16,Math.max(1,Number(config.concurrency) || 12));
    const network = limiter(concurrency), lifetime = new AbortController();
    const cache = lru(Math.min(32*1024*1024,Math.max(1024*1024,Number(config.cacheBytes)||12*1024*1024)));
    const recordOrdinals = new Map();
    let readyPromise = null, metadata = null, activeSearch = null, destroyed = false;
    function progress(options, value) { if (options.onProgress && !(options.signal && options.signal.aborted)) options.onProgress(value); }
    async function resource(descriptor) {
      const response = await network(function () { check(lifetime.signal); return fetcher(new URL(descriptor.file,manifestUrl).href,{signal:lifetime.signal}); });
      if (!response.ok) throw new Error("Search metadata request failed (HTTP " + response.status + ").");
      const bytes = new Uint8Array(await response.arrayBuffer());
      if (descriptor.bytes != null && bytes.byteLength !== descriptor.bytes) throw new Error("Search metadata byte length does not match its manifest.");
      if (descriptor.sha256 && root.crypto && root.crypto.subtle) {
        const digest = Array.from(new Uint8Array(await root.crypto.subtle.digest("SHA-256",bytes))).map(function (byte) { return byte.toString(16).padStart(2,"0"); }).join("");
        if (digest !== descriptor.sha256) throw new Error("Search metadata checksum does not match its manifest.");
      }
      return JSON.parse(new TextDecoder().decode(await unzip(bytes)));
    }
    async function load() {
      if (destroyed) throw abortError();
      const response = await network(function () { return fetcher(manifestUrl,{signal:lifetime.signal}); });
      if (!response.ok) throw new Error("Search index is unavailable (HTTP " + response.status + ").");
      const manifestBytes = new Uint8Array(await response.arrayBuffer());
      if (config.manifestSha256) {
        if (!root.crypto || !root.crypto.subtle) throw new Error("This browser cannot verify the pinned search manifest.");
        const digest = Array.from(new Uint8Array(await root.crypto.subtle.digest("SHA-256",manifestBytes))).map(function (byte) { return byte.toString(16).padStart(2,"0"); }).join("");
        if (digest !== String(config.manifestSha256).toLowerCase()) throw new Error("The search manifest does not match this site release.");
      }
      const manifest = JSON.parse(new TextDecoder().decode(manifestBytes));
      if (manifest.schemaVersion !== 1 || manifest.serializerVersion !== Query.VERSION || !safeInteger(manifest.recordCount) ||
        !Number.isInteger(manifest.pageSize) || manifest.pageSize < 1 || !manifest.coverage || !manifest.coverage.complete ||
        manifest.coverage.indexedIdSetSha256 !== manifest.coverage.currentCatalogIdSetSha256) throw new Error("Search index schema or corpus coverage is invalid.");
      const values = await Promise.all([resource(manifest.ids),resource(manifest.pages),resource(manifest.lexicon)]);
      const ids = values[0], pages = values[1], rows = values[2];
      if (!Array.isArray(ids) || ids.length !== manifest.recordCount || !Array.isArray(rows) || !Array.isArray(pages) ||
        pages.length !== Math.ceil(ids.length/manifest.pageSize)) throw new Error("Search metadata record counts do not match.");
      for (let index=0;index<ids.length;index+=1) if (typeof ids[index] !== "string") throw new Error("Search IDs must preserve exact string identities.");
      function packsValid(packs) {
        if (!Array.isArray(packs)) throw new Error("Search pack metadata is missing.");
        let previousEnd = 0;
        packs.forEach(function (pack) {
          if (!pack || !safeInteger(pack.start) || !safeInteger(pack.bytes) || !pack.bytes || pack.start < previousEnd || typeof pack.file !== "string") throw new Error("Invalid search pack boundaries.");
          previousEnd = pack.start + pack.bytes;
        });
      }
      packsValid(manifest.textPacks); packsValid(manifest.postingPacks);
      const fragments=new Map();
      if(manifest.fragments){
        if(!Array.isArray(manifest.fragments))throw new Error("Invalid common-fragment metadata.");
        packsValid(manifest.fragmentPacks);
        manifest.fragments.forEach(function(row){
          if(!Array.isArray(row)||typeof row[0]!=="string"||!Query.isWordFragment(row[0])||row[0]!==row[0].toLowerCase()||
            !safeInteger(row[1])||!safeInteger(row[2])||!safeInteger(row[3])||row[3]>ids.length||Boolean(row[2])!==Boolean(row[3])||fragments.has(row[0]))throw new Error("Invalid common-fragment coverage.");
          fragments.set(row[0],{offset:row[1],length:row[2],df:row[3]});
        });
      }
      const tokens = new Array(rows.length), offsets = new Uint32Array(rows.length), lengths = new Uint32Array(rows.length), frequencies = new Uint32Array(rows.length);
      rows.forEach(function (row,index) {
        if (!Array.isArray(row) || typeof row[0] !== "string" || !safeInteger(row[1]) || row[1]>0xffffffff || !safeInteger(row[2]) ||
          !row[2] || row[2]>0xffffffff || !safeInteger(row[3]) || row[3]<1 || row[3]>ids.length) throw new Error("Invalid search vocabulary row.");
        tokens[index]=row[0]; offsets[index]=row[1]; lengths[index]=row[2]; frequencies[index]=row[3]; rows[index]=null;
      });
      pages.forEach(function (page,index) {
        if (!Array.isArray(page) || !safeInteger(page[0]) || !safeInteger(page[1]) || !page[1] || page[2]!==index*manifest.pageSize ||
          page[3]!==Math.min(manifest.pageSize,ids.length-page[2])) throw new Error("Invalid search text page coverage.");
      });
      metadata = {manifest:manifest,ids:ids,pages:pages,tokens:tokens,offsets:offsets,lengths:lengths,frequencies:frequencies,fragments:fragments};
      return metadata;
    }
    function ready(signal) {
      if (!readyPromise) readyPromise = load().catch(function (error) { readyPromise=null; throw error; });
      return waiting(readyPromise,signal);
    }
    async function range(pack, start, length, signal) {
      check(signal); check(lifetime.signal);
      if (length > 16*1024*1024) throw new Error("A search member exceeds the bounded range size.");
      const end = start+length-1;
      return network(async function () {
        check(signal); check(lifetime.signal);
        const combined = typeof AbortSignal.any === "function" ? AbortSignal.any([lifetime.signal,signal].filter(Boolean)) : signal || lifetime.signal;
        const response = await fetcher(new URL(pack.file,manifestUrl).href,{headers:{Range:"bytes="+start+"-"+end},signal:combined});
        if (response.status !== 206) {
          if (response.body && response.body.cancel) { try { await response.body.cancel(); } catch (_) {} }
          throw new Error("The search host must honor byte ranges (expected HTTP206, received " + response.status + ").");
        }
        const contentRange = response.headers.get("Content-Range") || "";
        const match = /^bytes (\d+)-(\d+)\/(\d+)$/.exec(contentRange);
        if (!match || Number(match[1])!==start || Number(match[2])!==end || Number(match[3])!==pack.bytes) {
          if (response.body && response.body.cancel) { try { await response.body.cancel(); } catch (_) {} }
          throw new Error("Search range response has an invalid Content-Range.");
        }
        const bytes = new Uint8Array(await response.arrayBuffer());
        check(signal); check(lifetime.signal);
        if (bytes.byteLength !== length) throw new Error("Search range response is truncated.");
        return bytes;
      });
    }
    function packFor(packs,offset,length) {
      let low=0, high=packs.length-1;
      while (low<=high) { const mid=(low+high)>>1, pack=packs[mid];
        if (offset<pack.start) high=mid-1;
        else if (offset>=pack.start+pack.bytes) low=mid+1;
        else if (offset+length<=pack.start+pack.bytes) return pack;
        else break;
      }
      throw new Error("Search member crosses a pack boundary.");
    }
    async function members(list,packs,kind,onMember,signal,errors) {
      const missing=[];
      for (const item of list) {
        check(signal);
        item.key=kind+":"+item.offset+":"+item.length;
        const saved=cache.get(item.key);
        if (saved) await onMember(item,saved);
        else { item.pack=packFor(packs,item.offset,item.length); missing.push(item); }
      }
      missing.sort(function(a,b){return a.offset-b.offset;});
      const groups=[];
      missing.forEach(function(item){
        const last=groups[groups.length-1], local=item.offset-item.pack.start;
        if (last && last.pack===item.pack && local-last.end<=2048 && local+item.length-last.start<=256*1024) {
          last.end=local+item.length; last.items.push(item);
        } else groups.push({pack:item.pack,start:local,end:local+item.length,items:[item]});
      });
      await mapLimit(groups,concurrency,async function(group){
        check(signal);
        let bytes;
        try { bytes=await range(group.pack,group.start,group.end-group.start,signal); }
        catch(error) { if(error.name==="AbortError")throw error; errors.push({phase:kind,message:error.message,failedMembers:group.items.length}); return; }
        for (const item of group.items) {
          check(signal);
          const start=item.offset-item.pack.start-group.start;
          const value=bytes.slice(start,start+item.length);
          try { await onMember(item,value); cache.set(item.key,value); }
          catch(error) { if(error.name==="AbortError")throw error; errors.push({phase:kind,message:error.message,failedMembers:1}); }
        }
      });
    }
    async function fragment(meta,term,options,errors) {
      const list=[];
      const accelerated=meta.fragments.get(term);
      if(accelerated){if(accelerated.df)list.push(accelerated);}
      else for(let index=0;index<meta.tokens.length;index+=1) {
        if((index&16383)===0)check(options.signal);
        if(meta.tokens[index].includes(term))list.push({offset:meta.offsets[index],length:meta.lengths[index],df:meta.frequencies[index]});
      }
      const output=new Set(); let completed=0;
      progress(options,{phase:"postings",term:term,completed:0,total:list.length});
      await members(list,accelerated?meta.manifest.fragmentPacks:meta.manifest.postingPacks,accelerated?"fragments":"postings",function(item,bytes){
        const values=decodeVarints(bytes,item.df,meta.ids.length);
        for(const value of values)output.add(value);
        completed+=1;
        if(completed===list.length || completed%25===0)progress(options,{phase:"postings",term:term,completed:completed,total:list.length});
      },options.signal,errors);
      return output;
    }
    async function verify(meta,term,candidates,options,errors) {
      const pageNumbers=new Set();
      if(candidates===null)for(let index=0;index<meta.pages.length;index+=1)pageNumbers.add(index);
      else candidates.forEach(function(ordinal){pageNumbers.add(Math.floor(ordinal/meta.manifest.pageSize));});
      const list=Array.from(pageNumbers).map(function(number){const page=meta.pages[number];return{offset:page[0],length:page[1],first:page[2],count:page[3]};});
      const output=new Set();let completed=0;
      progress(options,{phase:"verification",term:term,completed:0,total:list.length});
      await members(list,meta.manifest.textPacks,"text",async function(item,bytes){
        const texts=JSON.parse(new TextDecoder().decode(await unzip(bytes)));
        if(!Array.isArray(texts)||texts.length!==item.count||texts.some(function(text){return typeof text!=="string";}))throw new Error("Search text page has invalid record coverage.");
        texts.forEach(function(text,index){const ordinal=item.first+index;if((candidates===null||candidates.has(ordinal))&&text.includes(term))output.add(ordinal);});
        completed+=1;
        if(completed===list.length||completed%25===0)progress(options,{phase:"verification",term:term,completed:completed,total:list.length});
      },options.signal,errors);
      return output;
    }
    async function search(plan,options) {
      options=options||{};
      if(!plan||plan.version!==Query.VERSION||!Array.isArray(plan.terms))throw new Error("Compile the search query before searching.");
      if(activeSearch)activeSearch.abort();
      const controller=new AbortController();activeSearch=controller;
      const callerSignal=options.signal, abort=function(){controller.abort();};
      if(callerSignal){check(callerSignal);callerSignal.addEventListener("abort",abort,{once:true});}
      options=Object.assign({},options,{signal:controller.signal});
      const errors=[],leaves=new Map();let meta=null;
      try {
        progress(options,{phase:"index",completed:0,total:1});
        meta=await ready(options.signal);check(options.signal);
        if(options.expectedRecordCount!=null&&Number(options.expectedRecordCount)!==meta.ids.length)throw new Error("The search index covers a different catalog size. Retry after the catalog finishes loading.");
        const expectedIdSetSha256=options.expectedIdSetSha256||config.expectedIdSetSha256;
        if(expectedIdSetSha256&&expectedIdSetSha256!==meta.manifest.coverage.currentCatalogIdSetSha256)throw new Error("The search index belongs to a different catalog release.");
        progress(options,{phase:"index",completed:1,total:1});
        const fragmentCache=new Map();
        for(const term of plan.terms){
          check(options.signal);
          const parts=Array.from(new Set(Query.wordParts(term)));
          let candidates=null;
          for(const part of parts){
            if(!fragmentCache.has(part))fragmentCache.set(part,await fragment(meta,part,options,errors));
            candidates=intersect(candidates,fragmentCache.get(part));
            if(!candidates.size)break;
          }
          const result=Query.isWordFragment(term)?candidates:await verify(meta,term,candidates,options,errors);
          leaves.set(term,result||new Set());
        }
        const supplemental=options.supplementalMatches;
        let metadataComplete=options.metadataComplete===true&&supplemental&&typeof supplemental==="object";
        if(meta.manifest.coverage.currentMetadataOverlayMustBeUnioned&&!metadataComplete)errors.push({phase:"metadata",message:"Current catalog metadata was not included; preserved-text results are partial."});
        if(supplemental){
          for(const term of plan.terms){
            check(options.signal);
            const raw=supplemental[term];
            if(!Array.isArray(raw)){metadataComplete=false;errors.push({phase:"metadata",message:"A query term is missing its current metadata match set."});continue;}
            const pending=new Set(raw.map(String));
            const leaf=leaves.get(term);
            for(let ordinal=0;ordinal<meta.ids.length&&pending.size;ordinal+=1){
              if((ordinal&16383)===0)check(options.signal);
              if(pending.delete(meta.ids[ordinal]))leaf.add(ordinal);
            }
            if(pending.size){metadataComplete=false;errors.push({phase:"metadata",message:"Some current metadata reports are absent from the indexed catalog.",unindexedReports:pending.size});}
          }
        }
        check(options.signal);
        const ordinals=Array.from(evaluate(plan.ast,leaves,meta.ids.length)).sort(function(a,b){return a-b;});
        const result={ids:ordinals.map(function(ordinal){return meta.ids[ordinal];}),complete:errors.length===0,planKey:plan.cacheKey,
          coverage:{rawPreservedText:errors.every(function(error){return error.phase==="metadata";}),metadataOverlay:Boolean(metadataComplete),
            includesUnmapped:Boolean(meta.manifest.coverage.includesUnmapped),indexedReports:meta.ids.length,
            expectedReports:options.expectedRecordCount==null?meta.manifest.recordCount:Number(options.expectedRecordCount),
            corpusIdSetSha256:meta.manifest.coverage.currentCatalogIdSetSha256},errors:errors};
        progress(options,{phase:result.complete?"complete":"partial",completed:result.ids.length,total:result.ids.length});
        return result;
      } catch(error){
        if(error.name==="AbortError"||controller.signal.aborted)throw abortError();
        return{ids:[],complete:false,planKey:plan.cacheKey,coverage:{rawPreservedText:false,metadataOverlay:false,includesUnmapped:false,
          indexedReports:meta?meta.ids.length:0,expectedReports:options.expectedRecordCount||null},errors:[{phase:"index",message:error.message}]};
      } finally {if(callerSignal)callerSignal.removeEventListener("abort",abort);if(activeSearch===controller)activeSearch=null;}
    }
    async function getExcerpt(id,plan,options) {
      options=options||{};check(options.signal);
      const meta=await ready(options.signal), key=String(id);
      let ordinal=recordOrdinals.get(key);
      if(ordinal==null){ordinal=meta.ids.indexOf(key);if(ordinal<0)return null;recordOrdinals.set(key,ordinal);}
      const page=meta.pages[Math.floor(ordinal/meta.manifest.pageSize)], errors=[];let result=null;
      await members([{offset:page[0],length:page[1],first:page[2],count:page[3]}],meta.manifest.textPacks,"text",async function(item,bytes){
        const texts=JSON.parse(new TextDecoder().decode(await unzip(bytes)));
        if(!Array.isArray(texts)||texts.length!==item.count||typeof texts[ordinal-item.first]!=="string")throw new Error("Search excerpt page has invalid coverage.");
        result=Object.assign({recordId:key,preservedText:true,normalized:true,normalization:"JavaScript String.toLowerCase"},Query.excerpt(plan,texts[ordinal-item.first],options));
      },options.signal,errors);
      if(errors.length)throw new Error(errors[0].message);
      return result;
    }
    function destroy(){destroyed=true;lifetime.abort();if(activeSearch)activeSearch.abort();cache.clear();recordOrdinals.clear();metadata=null;readyPromise=null;}
    return{search:search,getExcerpt:getExcerpt,destroy:destroy};
  }
  return{create:create,decodeVarints:decodeVarints};
});
