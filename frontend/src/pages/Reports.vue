<script setup lang="ts">
import {ref,computed,onMounted} from 'vue';
import {reviews} from '../stores/reviews';
import {reports} from '../stores/reports';
import {corrections,loadCorrections,createCorrection,decideCorrection} from '../stores/corrections';
import {runs} from '../stores/runs';
import {isAdmin,canWrite} from '../stores/auth';
import {request,downloadCsv} from '../api/client';
import {useTask} from '../hooks/useTask';
import PageHeading from '../components/common/PageHeading.vue';
import Notice from '../components/common/Notice.vue';
import StatusPill from '../components/common/StatusPill.vue';
import BudgetStrip from '../components/BudgetStrip.vue';
import type {Report,CorrectionRequest} from '../types/domain';

const expanded=ref('');
const formReport=ref('');
const replacementRun=ref('');
const reason=ref('');
const {error,busy,act}=useTask();

onMounted(()=>Promise.all([reviews.load(),reports.load(),loadCorrections(),runs.load()]));

const chains=computed(()=>{
 const map=new Map<string,Report[]>();
 for(const r of reports.items.value as Report[]){
  const root=r.root_id||r.id;
  if(!map.has(root))map.set(root,[]);
  map.get(root)!.push(r);
 }
 return [...map.values()].map(list=>list.sort((a,b)=>a.version-b.version));
});
const pendingCorrections=computed(()=>corrections.value.filter(c=>c.state==='submitted'));
const formReportRow=computed(()=>reportById(formReport.value));
const formEligibleRuns=computed(()=>(formReportRow.value?eligibleRuns(formReportRow.value):[]));

function reportById(id:string|null){return reports.items.value.find(r=>r.id===id) as Report|undefined}
function runById(id:string){return runs.items.value.find(r=>r.id===id)}
function correctionOf(reportId:string){return corrections.value.find(c=>c.report_id===reportId&&c.state==='submitted')}
function eligibleRuns(report:Report){
 return runs.items.value.filter(r=>r.study_id===report.study_id&&r.status==='completed'&&r.id!==report.backing_run_id);
}
function openForm(chain:Report[]){
 const current=chain.find(r=>r.is_current)||chain[chain.length-1];
 formReport.value=current.id;
 replacementRun.value=eligibleRuns(current)[0]?.id||'';
 reason.value='';
}
function approveReview(id:string){act(async()=>{await request('/reviews/'+id+'/approve','POST');await reviews.load()})}
function publish(id:string){act(async()=>{await reports.create({review_id:id,title:'因子敏感度底稿 '+new Date().toLocaleDateString()});await reports.load()})}
function download(id:string){act(()=>downloadCsv(id))}
function submitCorrection(){
 act(async()=>{await createCorrection({report_id:formReport.value,replacement_run_id:replacementRun.value,reason:reason.value});formReport.value='';await reports.load()});
}
function decide(id:string,path:'approve'|'reject'){
 const note=path==='reject'?window.prompt('请填写驳回说明（可选）')||'':'';
 act(async()=>{await decideCorrection(id,path,note);await Promise.all([reports.load(),reviews.load(),runs.load()])});
}
</script>

<template>
 <PageHeading index="05 / 试验归档" title="把范围、假设和采样量，一并签入底稿；选错运行可申请更正。" note="主管批准后才生成不可变报告并替换当前有效底稿；待审或驳回期间原版仍有效。旧版快照与CSV保持原值，新旧版本按版本链相互追溯。"/>
 <Notice :message="error||reports.error.value"/>
 <div class="two-col">
  <section>
   <h2>待审与已审因子复核</h2>
   <article v-for="r in reviews.items.value" :key="r.id" class="review-row">
    <StatusPill :status="r.state"/>
    <p>{{r.action}}</p>
    <small>{{r.reviewer||'等待主管批准'}} · 运行 {{r.run_id.slice(0,8)}}</small>
    <div v-if="isAdmin()" class="actions">
     <button v-if="r.state==='submitted'" @click="approveReview(r.id)" :disabled="busy">批准因子复核</button>
     <button v-if="r.state==='approved'" class="secondary" @click="publish(r.id)" :disabled="busy">生成敏感度快照</button>
    </div>
   </article>

   <h2 style="margin-top:34px">底稿更正申请（换运行）</h2>
   <p v-if="!pendingCorrections.length" class="method-note">暂无待审更正；主管批准前，原当前版底稿持续有效。</p>
   <article v-for="c in pendingCorrections" :key="c.id" class="review-row correction-row">
    <StatusPill :status="c.state"/>
    <p>{{c.reason}}</p>
    <small>申请人 {{c.requester}} · 目标底稿 {{reportById(c.report_id)?.title}}（第{{reportById(c.report_id)?.version}}版）</small>
    <small>替换运行 {{c.replacement_run_id.slice(0,8)}} · {{runById(c.replacement_run_id)?.status}}</small>
    <div v-if="isAdmin()" class="actions">
     <button @click="decide(c.id,'approve')" :disabled="busy">批准并发布后继版本</button>
     <button class="secondary" @click="decide(c.id,'reject')" :disabled="busy">驳回</button>
    </div>
   </article>
   <article v-for="c in corrections.filter(x=>x.state!=='submitted')" :key="c.id" class="review-row correction-row">
    <StatusPill :status="c.state"/>
    <p>{{c.reason}}</p>
    <small>{{c.reviewer}} · {{c.review_note}}<template v-if="c.successor_report_id"> · 后继底稿 {{c.successor_report_id.slice(0,8)}}</template></small>
   </article>
  </section>

  <section>
   <h2>批准试验底稿 · 版本链</h2>
   <article v-for="chain in chains" :key="chain[0].root_id||chain[0].id" class="report-row">
    <div v-for="r in chain" :key="r.id" :class="['version-card',{current:r.is_current,historical:!r.is_current}]">
     <div class="version-head">
      <span class="version-badge" :class="r.is_current?'badge-current':'badge-history'">{{r.is_current?'当前版 V'+r.version:'历史版 V'+r.version}}</span>
      <StatusPill status="approved"/>
     </div>
     <p class="eyebrow">APPROVED FACTOR RECORD</p>
     <h3>{{r.title}}</h3>
     <p>{{r.snapshot.result.study_name}}</p>
     <p>{{r.snapshot.result.metrics.length}}因子 · seed {{r.snapshot.result.config.seed}} · {{r.snapshot.reviewer}} · 运行 {{r.backing_run_id.slice(0,8)}}</p>
     <p v-if="r.snapshot.correction" class="correction-note">更正原因：{{r.snapshot.correction.reason}}<br>由 {{r.snapshot.correction.requester}} 申请，替换运行 {{r.snapshot.correction.replacement_run_id.slice(0,8)}}；上一版 {{r.snapshot.correction.predecessor_report_id.slice(0,8)}}。</p>
     <p v-else-if="r.predecessor_id" class="method-note">本版由更正流程发布，上一版 {{r.predecessor_id.slice(0,8)}} 保持原值可追溯。</p>
     <div class="actions">
      <button @click="download(r.id)">下载敏感度 CSV ↓</button>
      <button class="secondary" @click="expanded=expanded===r.id?'':r.id">查看采样预算</button>
     </div>
     <BudgetStrip v-if="expanded===r.id" :result="r.snapshot.result"/>
    </div>
    <div v-if="canWrite()" class="actions correction-entry">
     <button class="secondary" @click="openForm(chain)" :disabled="!!correctionOf(chain.find(x=>x.is_current)?.id||chain[0].id)">{{correctionOf(chain.find(x=>x.is_current)?.id||chain[0].id)?'已有待审更正':'申请更正（改选同一研究的已完成运行）'}}</button>
    </div>
   </article>

   <form v-if="formReport&&canWrite()" class="editor-panel correction-form" @submit.prevent="submitCorrection">
    <h2>填写更正原因并选择替换运行</h2>
    <p v-if="!formEligibleRuns.length" class="method-note">同一研究下没有其他已完成运行可替换；请先在「运行底稿」页新建并等待运行完成，再申请更正。</p>
    <label v-else>替换运行（仅限同一研究、已完成）
     <select v-model="replacementRun" required>
      <option v-for="run in formEligibleRuns" :key="run.id" :value="run.id">{{run.id==='demo-run-corrected'?'XH-C06 备选完成运行':run.id.slice(0,8)}} · {{run.status}} · {{run.id}}</option>
     </select>
    </label>
    <label v-if="formEligibleRuns.length">更正原因（选错运行的说明）
     <textarea v-model="reason" rows="4" minlength="8" maxlength="4000" required placeholder="说明已归档底稿选错运行的原因，以及改选运行的依据……"></textarea>
    </label>
    <div class="actions">
     <button :disabled="busy||!replacementRun">提交更正申请</button>
     <button type="button" class="secondary" @click="formReport=''">取消</button>
    </div>
   </form>
  </section>
 </div>
</template>
