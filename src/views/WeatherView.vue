<template>
  <LayoutHeader
    :env="env" :page_title="page_title"
    :client="client_info"
  />

  <div class="container">
    <h1>台灣縣市氣象色塊圖</h1>
    <div class="seg">
      <template v-for="(m,k) in METRICS" :key="k">
        <button v-if="!m.tipOnly" :class="{on:metric===k}" @click="metric=k">{{ m.label }}</button>
      </template>
    </div>
    <div class="status" :class="{err:failed}">{{ status }}</div>
    <div v-if="failed" class="card" style="font-size:13px;margin-bottom:8px">
      自動載入失敗時，可自行選擇縣市 TopoJSON / GeoJSON 檔案：
      <input type="file" accept=".json,.topojson,.geojson" @change="onFile">
    </div>
    <div class="ctl">
      <label><input type="checkbox" v-model="showLabels"> 顯示縣市名稱與數值</label>
      <label><input type="checkbox" v-model="showIcons"> 顯示天氣圖示</label>
      <button @click="loadLive">載入即時資料</button>
    </div>
    <!-- <div class="ctl"> -->
    <!--   授權碼：<input type="text" v-model="apiKey" placeholder="CWA 授權碼"><br> -->
    <!-- </div> -->
    <!-- <div class="ctl"> -->
    <!--   <button @click="downloadCounty" :disabled="!hasData">下載縣市彙整 CSV</button> -->
    <!--   <button @click="downloadStations" :disabled="!hasData">下載測站明細 CSV</button> -->
    <!-- </div> -->
    <div class="ctl">
      <span>{{ M.label }}資料：{{ sources[metric] }}（{{ records.length }} 筆）</span>
    </div>
    <div style="font-size:12px;color:#b3261e;min-height:16px;white-space:pre-line">{{ msg }}</div>
    <div class="row">
      <div class="card" ref="cardEl" style="position:relative">
        <div class="name">{{ info || '滑鼠移到縣市上查看氣溫、紫外線、降雨機率（滾輪縮放、拖曳平移）' }}</div>
        <svg ref="svg" viewBox="0 0 600 700"></svg>
        <div v-if="tip" class="tip" :style="{left:tip.x+'px',top:tip.y+'px',transform:tip.flip?'translate(-100%,0)':'none'}">
          <div class="tn">{{ tip.name }}</div>
          <div v-if="tip.wx" class="tr"><span>天氣</span><b>{{ tip.wx.icon }} {{ tip.wx.text }}</b></div>
          <div v-for="r in tip.rows" :key="r.k" class="tr" :class="{cur:r.k===metric}">
            <span><i class="dot" :style="{background:r.color}"></i>{{ r.label }}</span><b>{{ r.text }}</b>
          </div>
        </div>
        <svg ref="legend" viewBox="0 0 300 44" style="margin-top:8px;background:none;cursor:default"></svg>
      </div>
      <div class="card">
        <b style="font-size:14px">{{ M.title }}</b>
        <ol>
          <li v-for="r in rows" :key="r.name" :class="{on:sel===r.name}" @click="sel=r.name">
            <span><i class="dot" :style="r.avg==null?{}:{background:color(r.avg)}"></i>{{ r.icon }} {{ r.name }}</span>
            <b>{{ r.avg==null ? '—' : M.short(r.avg) }}</b>
          </li>
        </ol>
      </div>
    </div>
  </div>
    

  <LayoutFooter
    :env="env"
    :client="client_info"
    :page_title="page_title"
  />
</template>

<script setup>
import '../assets/weather.css';
import LayoutHeader from '@/components/LayoutHeader.vue';
import LayoutFooter from '@/components/LayoutFooter.vue';
// import taiwan_county_weather from '@/assets/taiwan_county_weather.csv';

import { createApp, ref, computed, watch, onMounted } from 'vue';
import * as d3 from 'd3';
import * as topojson from 'topojson-client';
import Papa from 'papaparse';
</script>

<script>

// 測試用預設授權碼（瀏覽器若已存過其他授權碼，以瀏覽器內的為準；分享檔案前請先清空）
const URLS = [
  "https://cdn.jsdelivr.net/npm/taiwan-atlas/counties-10t.json",
  "https://unpkg.com/taiwan-atlas/counties-10t.json"
];

// ---- 指標設定 ----
const uvLevels = [
  {from:0, label:"低量級", color:"#4caf50"}, {from:3, label:"中量級", color:"#fdd835"},
  {from:6, label:"高量級", color:"#fb8c00"}, {from:8, label:"過量級", color:"#e53935"},
  {from:11, label:"危險級", color:"#8e24aa"}
];
const uvLevel = v => [...uvLevels].reverse().find(l => v >= l.from);
const METRICS = {
  temp: { label:"氣溫", title:"縣市平均氣溫", showN:true,
    color:d3.scaleSequential(t=>d3.interpolateRdYlBu(1-t)).domain([0,35]).clamp(true),
    domain:[0,35], ticks:[0,5,10,15,20,25,30,35], tickFmt:d=>d+"°",
    short:v=>v.toFixed(1)+"°", full:v=>v.toFixed(1)+"°C" },
  uv: { label:"紫外線", title:"縣市平均紫外線指數", showN:true,
    color:v=>uvLevel(v).color,
    bands:uvLevels,
    short:v=>v.toFixed(1), full:v=>`指數 ${v.toFixed(1)}（${uvLevel(v).label}）` },
  rain: { label:"降雨機率", title:"縣市降雨機率", showN:false,
    color:d3.scaleSequential(t=>d3.interpolateBlues(.08+.92*t)).domain([0,100]).clamp(true),
    domain:[0,100], ticks:[0,20,40,60,80,100], tickFmt:d=>d+"%",
    short:v=>Math.round(v)+"%", full:v=>Math.round(v)+"%" },
  // 以下兩項目前只顯示在提示窗（tipOnly），不出現在切換按鈕
  acc: { label:"累積雨量", title:"縣市平均累積雨量", showN:true, tipOnly:true,
    color:d3.scaleSequential(t=>d3.interpolateBlues(.08+.92*t)).domain([0,100]).clamp(true),
    domain:[0,100], ticks:[0,25,50,75,100], tickFmt:d=>d+"mm",
    short:v=>v.toFixed(1)+"mm", full:v=>v.toFixed(1)+" mm" },
  sun: { label:"日照時數", title:"縣市平均日照時數", showN:true, tipOnly:true,
    color:d3.scaleSequential(t=>d3.interpolateYlOrBr(.1+.8*t)).domain([0,12]).clamp(true),
    domain:[0,12], ticks:[0,3,6,9,12], tickFmt:d=>d+"h",
    short:v=>v.toFixed(1)+"h", full:v=>v.toFixed(1)+" 小時" }
};

// ---- 範例資料（示意值，非即時；即時資料載入成功後會被取代）----
const T = [
["基隆","基隆市",24.8],["臺北","臺北市",27.1],["陽明山","臺北市",19.8],["板橋","新北市",26.9],["桃園","桃園市",26.0],
["新竹","新竹縣",26.2],["新竹市區","新竹市",26.3],["苗栗","苗栗縣",26.4],["臺中","臺中市",27.4],["梧棲","臺中市",26.1],
["員林","彰化縣",27.1],["日月潭","南投縣",22.3],["玉山","南投縣",6.2],["斗六","雲林縣",27.3],["阿里山","嘉義縣",14.6],
["嘉義","嘉義市",27.8],["臺南","臺南市",28.3],["高雄","高雄市",29.1],["恆春","屏東縣",28.6],["大武","臺東縣",28.2],
["臺東","臺東縣",27.9],["成功","臺東縣",27.2],["蘭嶼","臺東縣",28.0],["花蓮","花蓮縣",26.5],["宜蘭","宜蘭縣",25.7],
["蘇澳","宜蘭縣",25.4],["澎湖","澎湖縣",27.5],["金門","金門縣",26.0],["馬祖","連江縣",23.8]
].map(([name,county,v])=>({name,county,v}));
const byCounty = o => Object.entries(o).map(([county,v])=>({name:county,county,v}));
// 紫外線、累積雨量、日照時數的範例：與氣溫範例使用同一批測站（山區測站可個別微調）
const perStation = (base, adj={}) => T.map(s=>({name:s.name,county:s.county,v:adj[s.name]!==undefined?adj[s.name]:base[s.county]}));
const UV = perStation({基隆市:6,臺北市:7,新北市:7,桃園市:7,新竹縣:8,新竹市:8,苗栗縣:8,臺中市:9,彰化縣:9,南投縣:8,雲林縣:9,嘉義縣:9,嘉義市:9,臺南市:10,高雄市:10,屏東縣:10,宜蘭縣:5,花蓮縣:7,臺東縣:8,澎湖縣:11,金門縣:7,連江縣:5}, {玉山:11,阿里山:10,日月潭:8,陽明山:6});
const RAIN = byCounty({基隆市:70,臺北市:60,新北市:60,桃園市:50,新竹縣:40,新竹市:40,苗栗縣:30,臺中市:20,彰化縣:20,南投縣:30,雲林縣:20,嘉義縣:20,嘉義市:20,臺南市:10,高雄市:10,屏東縣:20,宜蘭縣:80,花蓮縣:60,臺東縣:40,澎湖縣:10,金門縣:30,連江縣:50});
const ACC = perStation({基隆市:12.5,臺北市:8.0,新北市:10.5,桃園市:5.0,新竹縣:2.5,新竹市:2.0,苗栗縣:1.0,臺中市:0.5,彰化縣:0,南投縣:3.0,雲林縣:0,嘉義縣:1.5,嘉義市:0,臺南市:0,高雄市:0,屏東縣:0.5,宜蘭縣:25.0,花蓮縣:6.0,臺東縣:2.0,澎湖縣:0,金門縣:0.5,連江縣:4.0});
const SUN = perStation({基隆市:1.5,臺北市:3.0,新北市:3.2,桃園市:4.0,新竹縣:5.5,新竹市:5.8,苗栗縣:6.5,臺中市:8.0,彰化縣:8.5,南投縣:6.0,雲林縣:8.8,嘉義縣:8.0,嘉義市:8.9,臺南市:9.5,高雄市:9.8,屏東縣:9.0,宜蘭縣:0.8,花蓮縣:4.5,臺東縣:6.0,澎湖縣:10.2,金門縣:6.5,連江縣:2.0});
// 天氣現象文字 → 圖示（適用觀測的「晴」「陰有雨」與預報的「多雲時晴」「陰短暫雨」等）
const wxIcon = t => {
  if(!t) return "";
  if(/雷/.test(t)) return "⛈️";
  if(/雪/.test(t)) return "🌨️";
  if(/雨/.test(t)) return /晴|多雲/.test(t) ? "🌦️" : "🌧️";
  if(/霧/.test(t)) return "🌫️";
  if(/陰/.test(t)) return "☁️";
  if(/晴/.test(t)) return /多雲/.test(t) ? "🌤️" : "☀️";
  if(/多雲/.test(t)) return "⛅";
  return "🌡️";
};
const WX = Object.entries({基隆市:"陰有雨",臺北市:"多雲",新北市:"多雲",桃園市:"多雲",新竹縣:"晴時多雲",新竹市:"晴時多雲",苗栗縣:"晴",臺中市:"晴",彰化縣:"晴",南投縣:"多雲",雲林縣:"晴",嘉義縣:"晴",嘉義市:"晴",臺南市:"晴",高雄市:"晴",屏東縣:"晴",宜蘭縣:"陰有雨",花蓮縣:"陰",臺東縣:"多雲",澎湖縣:"晴",金門縣:"多雲",連江縣:"陰"})
  .map(([county,text])=>({name:county,county,text}));
const SAMPLE_SRC = "範例快照（示意值，非即時）";

export default {
  inject: ['getMyData', 'setMyData'],
  props: ['env', 'page_title', 'client_info', 'API_KEY', 'API_URL'],
  data() {
    return {
      METRICS: Object.freeze(METRICS),          // 指標設定（凍結，避免被 Vue 代理）
      urls: URLS,                               // 縣市 TopoJSON 來源
      units: {temp:"°C", uv:"指數", rain:"%", acc:"mm", sun:"小時"},
      refreshMs: 600000,                        // 即時資料更新間隔：10 分鐘
      sampleSrc: SAMPLE_SRC,
      status: "載入地圖中…", failed: false, msg: "", info: "", tip: null,
      metric: "temp", showLabels: true, showIcons: true, apiKey: this.API_KEY, sel: "", countyNames: [],
      datasets: {temp:T, uv:UV, rain:RAIN, acc:ACC, sun:SUN},
      weather: WX,                              // 天氣現象（文字），例如「多雲」「陰有雨」
      sources: {temp:SAMPLE_SRC, uv:SAMPLE_SRC, rain:SAMPLE_SRC, acc:SAMPLE_SRC, sun:SAMPLE_SRC, weather:SAMPLE_SRC}
    }
  },

  computed: {
    M(){ return this.METRICS[this.metric]; },
    records(){ return this.datasets[this.metric]; },
    hasData(){ return Object.values(this.datasets).some(a=>a.length); },
    // 各縣市的天氣現象（同縣市多站時取最常出現者）
    weatherMap(){
      const g=new Map();
      for(const w of this.weather){const c=this.norm(w.county);const m=g.get(c)||new Map();m.set(w.text,(m.get(w.text)||0)+1);g.set(c,m);}
      const out=new Map();
      g.forEach((m,c)=>{const text=[...m.entries()].sort((a,b)=>b[1]-a[1])[0][0];out.set(c,{text,icon:wxIcon(text)});});
      return out;
    },
    // 各縣市五項指標的平均值
    allAvg(){
      const out={};
      for(const k in this.METRICS){
        const m=new Map();
        for(const s of this.datasets[k]){const c=this.norm(s.county);const o=m.get(c)||{sum:0,n:0};o.sum+=s.v;o.n++;m.set(c,o);}
        const r=new Map(); m.forEach((o,c)=>r.set(c,{avg:o.sum/o.n,n:o.n})); out[k]=r;
      }
      return out;
    },
    avgMap(){ 
      return this.allAvg[this.metric]; 
    },
    rows(){
      const names=this.countyNames.length?this.countyNames:[...new Set(this.records.map(s=>s.county))];
      return names.map(n=>{const a=this.avgMap.get(this.norm(n)),w=this.wxOf(n);return{name:n,avg:a?a.avg:null,icon:w?w.icon:""};})
        .sort((x,y)=>(y.avg??-999)-(x.avg??-999));
    }
  },

  watch: {
    avgMap(){ this.paint(); },
    showLabels(){ this.paint(); },
    showIcons(){ this.paint(); },
    weatherMap(){ this.paint(); },
    metric(){ this.info=""; this.drawLegend(); },
    sel(){ if(this.g) this.g.selectAll(".county").classed("on",d=>this.nameOf(d)===this.sel); }
  },

  // 初始化：讀取授權碼、立即抓即時資料、設定定時更新
  // （非響應式的 D3 物件放在這裡，不放進 data，避免 selection 被 Vue 代理）
  created(){
    this.g=null; this.labelG=null; this.iconG=null; this.curK=1; this.timer=null;
    try{ this.apiKey=localStorage.getItem("cwa_key")||this.API_KEY; }catch(e){} const auto=()=>this.apiKey||location.protocol.startsWith("http");
    if(auto()) this.loadLive();
    this.timer=setInterval(()=>{ if(auto()) this.loadLive(); }, this.refreshMs);
  },
  // 需要 DOM（svg / 圖例）的動作要等掛載後才能做
  mounted(){ 
   // // 使用 PapaParse 解析字串
   //  Papa.parse(taiwan_county_weather, {
   //    header: true,          // 將第一列視為物件的 Key
   //    skipEmptyLines: true,  // 自動跳過空白列
   //    complete: (results) => {
   //      // csvData.value = results.data
   //      // isLoading.value = false
   //      console.log('專案內 CSV 解析成功：', results.data)
   //    },
   //    error: (error) => {
   //      errorMessage.value = `CSV 解析失敗: ${error.message}`
   //      isLoading.value = false
   //    }
   //  })

    this.drawLegend(); 
    this.loadMap(); 
  },
  beforeUnmount(){ 
    clearInterval(this.timer); 
  },

  methods: {
    // ---- 工具 ----
    color(v){ return this.M.color(v); },
    norm(s){ return (s||"").replace(/台/g,"臺"); },
    nameOf(f){ const p=f.properties||{}; return p.COUNTYNAME||p.name||p.NAME||p.county||"(未命名)"; },
    firstCoord(g){ let c=g.coordinates; while(Array.isArray(c[0])) c=c[0]; return c; },
    rewind(f){
      if(d3.geoArea(f)<=2*Math.PI) return f;
      const g=f.geometry;
      if(g.type==="Polygon") g.coordinates=g.coordinates.map(r=>r.slice().reverse());
      else if(g.type==="MultiPolygon") g.coordinates=g.coordinates.map(pl=>pl.map(r=>r.slice().reverse()));
      return f;
    },
    toFeatures(data){
      let fc=data;
      if(data.type==="Topology"){
        const key=data.objects.counties?"counties":Object.keys(data.objects)[0];
        fc=topojson.feature(data,data.objects[key]);
      }
      const feats=fc.type==="FeatureCollection"?fc.features:[fc];
      if(!feats.length) throw new Error("檔案內沒有任何圖形");
      return feats;
    },

    wxOf(n){ return this.weatherMap.get(this.norm(n))||null; },

    // ---- 提示窗 ----
    tipRows(n){
      return Object.keys(this.METRICS).map(k=>{
        const m=this.METRICS[k], a=this.allAvg[k].get(this.norm(n));
        return{k,label:m.label,color:a?m.color(a.avg):"#d9dee6",
          text:a?m.full(a.avg)+(m.showN&&a.n>1?`（${a.n} 站平均）`:""):"無資料"};
      });
    },
    showTip(e,d){
      const b=this.$refs.cardEl.getBoundingClientRect(), x=e.clientX-b.left, y=e.clientY-b.top, flip=x>b.width*0.55;
      this.tip={name:this.nameOf(d),wx:this.wxOf(this.nameOf(d)),rows:this.tipRows(this.nameOf(d)),x:flip?x-14:x+14,y:y+14,flip};
    },
    describe(f){
      const n=this.nameOf(f), a=this.avgMap.get(this.norm(n)), m=this.M, w=this.wxOf(n), ic=w?w.icon+" ":"";
      if(!a) return `${ic}${n}　無${m.label}資料`;
      return `${ic}${n}　${m.label} ${m.full(a.avg)}`+(m.showN&&a.n>1?`（${a.n} 站平均）`:"");
    },

    // ---- 地圖繪製 ----
    render(feats){
      const vm=this, ext=[[10,10],[590,690]], c0=this.firstCoord(feats[0].geometry);
      const projected=Math.abs(c0[0])>180||Math.abs(c0[1])>90;
      let path;
      if(projected){
        const idp=d3.geoIdentity(); if(Math.abs(c0[1])>1e5) idp.reflectY(true);
        idp.fitExtent(ext,{type:"FeatureCollection",features:feats});
        path=d3.geoPath(idp);
      }else{
        feats=feats.map(this.rewind);
        path=d3.geoPath(d3.geoMercator().fitExtent(ext,{type:"FeatureCollection",features:feats}));
      }
      const root=d3.select(this.$refs.svg); root.selectAll("*").remove();
      this.g=root.append("g");
      this.g.selectAll("path").data(feats).join("path").attr("class","county").attr("d",path)
        .on("mouseenter",function(e,d){d3.select(this).classed("on",true);vm.info=vm.describe(d);vm.showTip(e,d);})
        .on("mousemove",(e,d)=>this.showTip(e,d))
        .on("mouseleave",function(e,d){d3.select(this).classed("on",vm.nameOf(d)===vm.sel);vm.info="";vm.tip=null;})
        .on("click",(e,d)=>{this.sel=this.nameOf(d);this.showTip(e,d);});
      this.labelG=this.g.append("g");
      this.labelG.selectAll("text").data(feats).join("text").attr("class","lbl")
        .attr("transform",d=>`translate(${path.centroid(d)})`);
      this.iconG=this.g.append("g");
      this.iconG.selectAll("text").data(feats).join("text").attr("class","ico")
        .attr("transform",d=>`translate(${path.centroid(d)})`);
      this.curK=1;
      root.call(d3.zoom().scaleExtent([1,14]).on("zoom",e=>{this.g.attr("transform",e.transform);this.curK=e.transform.k;this.updateScale();}));
      this.countyNames=feats.map(this.nameOf);
      this.paint();
    },
    updateScale(){
      if(!this.labelG) return;
      const k=Math.sqrt(this.curK);
      this.labelG.selectAll("text").attr("font-size",9.5/k).attr("stroke-width",2.5/k);
      // 天氣圖示放在名稱上方；沒顯示名稱時置中
      this.iconG.selectAll("text").attr("font-size",15/k).attr("y",(this.showLabels?-11:5)/k);
    },
    paint(){
      if(!this.g) return;
      const m=this.M;
      this.g.selectAll(".county").style("fill",d=>{const a=this.avgMap.get(this.norm(this.nameOf(d)));return a?m.color(a.avg):null;});
      this.labelG.style("display",this.showLabels?null:"none");
      this.iconG.style("display",this.showIcons?null:"none");
      this.iconG.selectAll("text").text(d=>{const w=this.wxOf(this.nameOf(d));return w?w.icon:"";});
      this.labelG.selectAll("text").text(d=>{const a=this.avgMap.get(this.norm(this.nameOf(d)));return this.nameOf(d)+(a?` ${m.short(a.avg)}`:"");});
      this.updateScale();
    },
    drawLegend(){
      const m=this.M, l=d3.select(this.$refs.legend); l.selectAll("*").remove();
      if(m.bands){                                  // 分級色塊（紫外線）
        const w=280/m.bands.length;
        m.bands.forEach((b,i)=>{
          l.append("rect").attr("x",10+i*w).attr("y",4).attr("width",w).attr("height",10).attr("fill",b.color);
          const next=m.bands[i+1];
          l.append("text").attr("x",10+i*w+w/2).attr("y",28).attr("text-anchor","middle").style("font-size","9.5px").attr("fill","currentColor").text(b.label);
          l.append("text").attr("x",10+i*w+w/2).attr("y",40).attr("text-anchor","middle").style("font-size","9px").attr("fill","#6b7685")
            .text(next?`${b.from}–${next.from-1}`:`≥${b.from}`);
        });
        return;
      }
      const [a,b]=m.domain, gr=l.append("defs").append("linearGradient").attr("id","lg");
      d3.range(0,1.01,.1).forEach(t=>gr.append("stop").attr("offset",t*100+"%").attr("stop-color",m.color(a+(b-a)*t)));
      l.append("rect").attr("x",10).attr("y",4).attr("width",280).attr("height",10).attr("rx",5).attr("fill","url(#lg)");
      l.append("g").attr("transform","translate(0,14)")
        .call(d3.axisBottom(d3.scaleLinear().domain(m.domain).range([10,290])).tickValues(m.ticks).tickFormat(m.tickFmt))
        .call(x=>{x.select(".domain").remove();x.selectAll("text").style("font-size","10px")});
    },

    // ---- 載入縣市邊界 ----
    async loadMap(){
      const errs=[];
      for(const u of this.urls){
        try{
          const feats=this.toFeatures(await d3.json(u));
          this.render(feats); this.status=`已載入 ${feats.length} 個縣市邊界`; return;
        }catch(e){errs.push(`${u} → ${e.message||e}`);}
      }
      this.failed=true; this.status="地圖自動載入失敗：\n"+errs.join("\n");
    },
    onFile(e){
      const f=e.target.files[0]; if(!f) return;
      const r=new FileReader();
      r.onload=()=>{
        try{const feats=this.toFeatures(JSON.parse(r.result));this.render(feats);this.failed=false;this.status=`已載入 ${feats.length} 個圖形（${f.name}）`;}
        catch(err){this.status="檔案讀取失敗："+err.message;this.failed=true;}
      };
      r.readAsText(f);
    },

    // ---- 中央氣象署即時資料 ----
    async cwa(id){
      // // 1) 優先走 server.py 的代理（/cwa/<id>），可避開 CORS，授權碼留在伺服器端
      // let pr=null; try{ pr=await fetch(`/cwa/${id}`); }catch(e){}
      // if(pr && (pr.headers.get("content-type")||"").includes("json")){
      //   const j=await pr.json();
      //   if(!pr.ok) throw new Error(j.error||("HTTP "+pr.status));
      //   return j;
      // }
      // 2) 沒有代理時，直接呼叫氣象署（瀏覽器可能因 CORS 而失敗）
      const r=await fetch(`https://opendata.cwa.gov.tw/api/v1/rest/datastore/${id}?Authorization=${encodeURIComponent(this.apiKey)}&format=JSON`);
      if(!r.ok) throw new Error(`${id} HTTP ${r.status}`);
      return r.json();
    },
    setData(k,list,src){
      this.datasets={...this.datasets,[k]:list};
      this.sources={...this.sources,[k]:src};
    },
    async loadLive(){
      this.msg="載入中…";
      try{localStorage.setItem("cwa_key",this.apiKey)}catch(e){}
      const errs=[];
      let wxObs=[], wxFc=[];
      // 1) O-A0003-001（每 10 分鐘更新）：氣溫、紫外線、當日累積雨量、日照時數都在同一份資料裡
      try{
        const j=await this.cwa("O-A0003-001"), st=(j.records &&j.records.Station)||[];
        const pick=(get,ok,fix=v=>v)=>st.map(x=>({name:x.StationName,county:x.GeoInfo&&x.GeoInfo.CountyName,
            v:fix(parseFloat(get(x.WeatherElement||{})))})).filter(r=>r.county&&isFinite(r.v)&&ok(r.v));
        // 天氣現象：觀測的 Weather 欄位（缺值會是 -99 之類的數字，沒有中文就略過）
        wxObs=st.map(x=>({name:x.StationName,county:x.GeoInfo&&x.GeoInfo.CountyName,text:String((x.WeatherElement&&x.WeatherElement.Weather)||"")}))
          .filter(r=>r.county&&/[\u4e00-\u9fff]/.test(r.text));
        const latest=st.map(x=>x.ObsTime&&x.ObsTime.DateTime).filter(Boolean).sort().pop();
        const src="中央氣象署觀測"+(latest?" "+latest.slice(0,16).replace("T"," "):"");
        const defs=[
          ["temp","氣溫",   pick(w=>w.AirTemperature,v=>v>-50&&v<60)],
          ["uv",  "紫外線", pick(w=>w.UVIndex,v=>v>=0&&v<=20)],
          ["acc", "累積雨量",pick(w=>w.Now&&w.Now.Precipitation,v=>v>=0&&v<=1500,v=>v===-998?0:v)],  // -998 為微量，以 0 計
          ["sun", "日照時數",pick(w=>w.SunshineDuration,v=>v>=0&&v<=24)]
        ];
        console.log(defs)
        for(const [k,label,list] of defs){
          if(list.length) this.setData(k,list,src); else errs.push(`${label}：回傳資料中沒有有效數值`);
        }
      }catch(e){errs.push("現在天氣觀測（O-A0003-001）："+(e.message||e));}
      // 2) F-C0032-001（36 小時預報）：各縣市降雨機率，取最近一個時段
      try{
        const j=await this.cwa("F-C0032-001");
        const list=j.records.location.map(l=>{
          const pop=l.weatherElement.find(w=>w.elementName==="PoP");
          return{name:l.locationName,county:l.locationName,v:+pop.time[0].parameter.parameterName};
        }).filter(r=>isFinite(r.v));
        if(!list.length) throw new Error("沒有有效數值");
        this.setData("rain",list,"中央氣象署 36 小時預報");
        // 天氣現象預報（Wx）：觀測沒有資料的縣市用它補上
        wxFc=j.records.location.map(l=>{
          const wx=l.weatherElement.find(w=>w.elementName==="Wx");
          return{name:l.locationName,county:l.locationName,text:wx?String(wx.time[0].parameter.parameterName):""};
        }).filter(r=>r.text);
      }catch(e){errs.push("降雨機率（F-C0032-001）："+(e.message||e));}
      const have=new Set(wxObs.map(r=>this.norm(r.county)));
      const wx=[...wxObs,...wxFc.filter(r=>!have.has(this.norm(r.county)))];
      if(wx.length){ this.weather=wx; this.sources={...this.sources,weather:wxObs.length?"中央氣象署觀測（缺資料縣市用預報）":"中央氣象署預報"}; }
      else errs.push("天氣現象：沒有有效資料");
      this.msg=errs.length?"以下項目載入失敗（仍顯示範例值）：\n"+errs.join("\n")+"\n若是 NetworkError / Failed to fetch，代表瀏覽器擋下了直接呼叫（CORS），請改用「python3 server.py」開啟 http://localhost:8000。":"";
    },

    // ---- 下載 CSV（加 BOM，Excel 直接開啟不會亂碼）----
    csvCell(v){ v=String(v==null?"":v); return /[",\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v; },
    tag(){ return this.sources.temp===this.sampleSrc?"SAMPLE_":""; },
    stamp(){ const d=new Date(), p=n=>String(n).padStart(2,"0"); return `${d.getFullYear()}${p(d.getMonth()+1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}`; },
    saveCsv(rows,name){
      const text="\ufeff"+rows.map(r=>r.map(this.csvCell).join(",")).join("\r\n");
      const a=document.createElement("a");
      a.href=URL.createObjectURL(new Blob([text],{type:"text/csv;charset=utf-8"})); a.download=name;
      document.body.appendChild(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(a.href),1000);
    },
    downloadCounty(){
      const keys=Object.keys(this.METRICS);
      const names=this.countyNames.length?this.countyNames:[...new Set(keys.flatMap(k=>this.datasets[k].map(r=>r.county)))];
      const head=["縣市",...keys.map(k=>`${this.METRICS[k].label}(${this.units[k]})`),"氣溫測站數","天氣"];
      const body=names.map(n=>{
        const t=this.allAvg.temp.get(this.norm(n));
        return[n,...keys.map(k=>{const a=this.allAvg[k].get(this.norm(n));return a?a.avg.toFixed(1):"";}),t?t.n:0,(this.wxOf(n)||{}).text||""];
      }).sort((a,b)=>a[0].localeCompare(b[0],"zh-Hant"));
      this.saveCsv([head,...body],`taiwan_county_weather_${this.tag()}${this.stamp()}.csv`);
    },
    downloadStations(){
      const keys=["temp","uv","acc","sun"], m=new Map();
      for(const k of keys) for(const r of this.datasets[k]){
        const id=r.name+"|"+r.county, o=m.get(id)||{name:r.name,county:r.county}; o[k]=r.v; m.set(id,o);
      }
      const head=["測站","縣市",...keys.map(k=>`${this.METRICS[k].label}(${this.units[k]})`)];
      const body=[...m.values()].sort((a,b)=>a.county.localeCompare(b.county,"zh-Hant")||a.name.localeCompare(b.name,"zh-Hant"))
        .map(o=>[o.name,o.county,...keys.map(k=>o[k]==null?"":o[k])]);
      this.saveCsv([head,...body],`taiwan_station_obs_${this.tag()}${this.stamp()}.csv`);
    }
  }
}
</script>

<style scoped>
</style>
