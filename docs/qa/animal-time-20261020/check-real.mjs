import {readFileSync,writeFileSync} from 'node:fs';
import {gunzipSync} from 'node:zlib';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),Stats=require('../../../analysis_stats.js'),Spatial=require('../../../analysis_spatial.js');
const manifest=JSON.parse(readFileSync('data/analysis_v1/manifest.json','utf8'));
const animalRows=JSON.parse(gunzipSync(readFileSync('data/analysis_v1/animal_reports_temporal.json.gz')));
const frozen='D:/UFO-Timeline-Context-Evidence/releases/context-recovery-20261019-v1';
const before=JSON.parse(gunzipSync(readFileSync(frozen+'/projections/analysis_v1/animal_reports.json.gz')));
if (JSON.stringify(animalRows.map(r=>r.slice(0,9)))!==JSON.stringify(before)) throw Error('Original fields drifted');
const data=Stats.normalizeContextProjections({manifest,animalReports:animalRows});
const animals=Stats.computeAnalysis({rows:[],quickMode:true,selectedDomains:['context'],contextProjections:data,fullTimeRange:true}).context.animals;
const summary={dateWindow:'All time',cohort:'all animal descriptive records; craft probe includes all neighbor UFO IDs and is broader than default UI filters',reportCount:animals.activeCount,sourceFieldsUnchanged:true,temporal:{}};
for(const name of ['species','locations']){summary.temporal[name]={};for(const period of ['yearly','decadal']){const p=animals.temporal[name][period];summary.temporal[name][period]={rows:p.rows,columns:p.columns,metadata:p.metadata};if(p.cells.some(c=>c.inferenceEligible||c.patternFinderEligible))throw Error('Inference promoted');}}
const neighbors=JSON.parse(gunzipSync(readFileSync(frozen+'/projections/analysis_v2/context_ufo_neighbors_v1.json.gz')));
const book=JSON.parse(readFileSync('data/analysis_v2/manifest.json','utf8')).codes.contextUfoNeighbors;
const association=Spatial.computeContextAssociations({neighbors,codebook:book,includeAllWhenNoActiveRows:true,permutationCount:0,bootstrapCount:0,inferenceEnabled:false});
const craft=association.lanes.find(l=>l.lane==='animal_public_marker').temporal.craft;
summary.temporal.craft={};for(const period of ['yearly','decadal']){const p=craft[period];summary.temporal.craft[period]={rows:p.rows,columns:p.columns,metadata:p.metadata};}
writeFileSync('docs/qa/animal-time-20261020/real-data.json',JSON.stringify(summary,null,2)+'\n');
console.log(JSON.stringify({reports:animals.activeCount,species:animals.temporal.species.decadal.metadata,countries:animals.temporal.locations.decadal.metadata,craft:craft.yearly.metadata},null,2));
