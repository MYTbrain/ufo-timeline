(function(root,factory){
  "use strict";
  const common=typeof module==="object"&&module.exports;
  const base=root.document&&root.document.currentScript?root.document.currentScript.src:(root.location&&root.location.href);
  const api=factory(root,common?require("./search_worker.js"):null,base);
  if(common)module.exports=api;else root.UfoSearchRuntime=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(root,Core,base){
  "use strict";
  function abortError(){const error=new Error("Search was cancelled.");error.name="AbortError";return error;}
  function create(config){
    config=config||{};
    let worker=null,inline=null,destroyed=false,nextId=0,activeSearch=null;
    const pending=new Map();
    function start(){
      if(destroyed)throw abortError();
      if(worker||inline)return;
      if(Core&&(config.fetch||typeof root.Worker!=="function")){inline=Core.create(config);return;}
      if(typeof root.Worker!=="function")throw new Error("Background search is unavailable in this browser.");
      let workerUrl=config.workerUrl;
      if(!workerUrl){const url=new URL("search_worker.js",base||config.manifestUrl);if(base)url.search=new URL(base).search;workerUrl=url.href;}
      worker=new root.Worker(workerUrl);
      const currentWorker=worker;
      worker.addEventListener("message",function(event){
        const data=event.data||{},request=pending.get(data.requestId);if(!request)return;
        if(data.type==="progress"){if(request.onProgress)request.onProgress(data.progress);return;}
        pending.delete(data.requestId);request.cleanup();
        if(data.type==="result")request.resolve(data.result);
        else{const error=new Error(data.error&&data.error.message||"Search worker failed.");error.name=data.error&&data.error.name||"Error";request.reject(error);}
      });
      worker.addEventListener("error",function(){
        if(worker!==currentWorker)return;
        const error=new Error("Background search stopped unexpectedly. Retry the search.");
        pending.forEach(function(request){request.cleanup();request.reject(error);});pending.clear();currentWorker.terminate();worker=null;
      });
    }
    function request(type,plan,options,id){
      options=options||{};
      if(options.signal&&options.signal.aborted)return Promise.reject(abortError());
      try{start();}catch(error){return Promise.reject(error);}
      if(inline)return type==="search"?inline.search(plan,options):inline.getExcerpt(id,plan,options);
      return new Promise(function(resolve,reject){
        const requestId=++nextId,signal=options.signal;
        const abort=function(){if(!pending.has(requestId))return;pending.delete(requestId);cleanup();worker.postMessage({type:"cancel",requestId:requestId});reject(abortError());};
        const cleanup=function(){if(signal)signal.removeEventListener("abort",abort);};
        pending.set(requestId,{resolve:resolve,reject:reject,cleanup:cleanup,onProgress:options.onProgress});
        if(signal)signal.addEventListener("abort",abort,{once:true});
        const forwarded=Object.assign({},options);delete forwarded.signal;delete forwarded.onProgress;
        try{worker.postMessage({type:type,requestId:requestId,plan:plan,id:id,options:forwarded,
          config:{manifestUrl:config.manifestUrl,manifestSha256:config.manifestSha256,expectedIdSetSha256:config.expectedIdSetSha256,
            concurrency:config.concurrency,cacheBytes:config.cacheBytes}});}
        catch(error){pending.delete(requestId);cleanup();reject(error);}
      });
    }
    async function search(plan,options){
      if(activeSearch)activeSearch.abort();
      const controller=new AbortController(),signal=options&&options.signal;
      const abort=function(){controller.abort();};
      if(signal){if(signal.aborted)throw abortError();signal.addEventListener("abort",abort,{once:true});}
      activeSearch=controller;
      try{return await request("search",plan,Object.assign({},options,{signal:controller.signal}));}
      finally{if(signal)signal.removeEventListener("abort",abort);if(activeSearch===controller)activeSearch=null;}
    }
    return{search:search,getExcerpt:function(id,plan,options){return request("excerpt",plan,options,id);},
      destroy:function(){destroyed=true;if(activeSearch)activeSearch.abort();if(inline)inline.destroy();if(worker){worker.postMessage({type:"destroy"});worker.terminate();worker=null;}
        pending.forEach(function(item){item.cleanup();item.reject(abortError());});pending.clear();}};
  }
  return Object.freeze({create:create});
});
