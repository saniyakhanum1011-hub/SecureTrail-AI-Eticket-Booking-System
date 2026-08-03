const firebaseConfig={apiKey:"AIzaSyBg8DhrkbwRwUP7-OPbIpmjhsCjUcchtUA",authDomain:"trail-45113.firebaseapp.com",projectId:"trail-45113",storageBucket:"trail-45113.firebasestorage.app",messagingSenderId:"713817792010",appId:"1:713817792010:web:438dc6e7e77befd87009f3"};
firebase.initializeApp(firebaseConfig);
const auth=firebase.auth();
const db=firebase.firestore();
const API = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1" ? "http://localhost:5000" : "";

const CITIES=["Ahmedabad","Agra","Amritsar","Bangalore","Bhopal","Bhubaneswar","Chandigarh","Chennai","Coimbatore","Delhi","Goa","Hyderabad","Indore","Jaipur","Jodhpur","Kochi","Kolkata","Lucknow","Mangalore","Mumbai","Mysore","Nagpur","Patna","Pune","Ranchi","Surat","Thiruvananthapuram","Udaipur","Varanasi","Visakhapatnam"];
const DIST={};
const _d=(a,b,k)=>{DIST[a+"|"+b]=k;DIST[b+"|"+a]=k};
_d("Bangalore","Mysore",150);_d("Bangalore","Chennai",350);_d("Bangalore","Hyderabad",570);_d("Bangalore","Mumbai",980);_d("Bangalore","Delhi",2150);_d("Bangalore","Kolkata",1870);_d("Bangalore","Pune",840);_d("Bangalore","Ahmedabad",1300);_d("Bangalore","Jaipur",2050);_d("Bangalore","Kochi",590);_d("Bangalore","Goa",560);_d("Bangalore","Bhopal",1420);_d("Bangalore","Lucknow",2000);_d("Bangalore","Patna",2100);_d("Bangalore","Surat",1250);_d("Bangalore","Nagpur",1130);_d("Bangalore","Indore",1380);_d("Bangalore","Visakhapatnam",1070);_d("Bangalore","Coimbatore",360);_d("Bangalore","Agra",2200);_d("Bangalore","Varanasi",2150);_d("Bangalore","Chandigarh",2550);_d("Bangalore","Amritsar",2700);_d("Bangalore","Jodhpur",2050);_d("Bangalore","Udaipur",1750);_d("Bangalore","Ranchi",1800);_d("Bangalore","Bhubaneswar",1600);_d("Bangalore","Mangalore",350);_d("Bangalore","Thiruvananthapuram",730);
_d("Mumbai","Delhi",1400);_d("Mumbai","Chennai",1330);_d("Mumbai","Hyderabad",710);_d("Mumbai","Kolkata",2050);_d("Mumbai","Pune",150);_d("Mumbai","Ahmedabad",530);_d("Mumbai","Jaipur",1150);_d("Mumbai","Kochi",1200);_d("Mumbai","Goa",590);_d("Mumbai","Bhopal",780);_d("Mumbai","Lucknow",1200);_d("Mumbai","Patna",1600);_d("Mumbai","Surat",280);_d("Mumbai","Nagpur",870);_d("Mumbai","Indore",590);_d("Mumbai","Visakhapatnam",1500);_d("Mumbai","Coimbatore",1150);_d("Mumbai","Agra",1320);_d("Mumbai","Varanasi",1550);_d("Mumbai","Chandigarh",1580);_d("Mumbai","Amritsar",1780);_d("Mumbai","Jodhpur",900);_d("Mumbai","Udaipur",650);_d("Mumbai","Ranchi",1700);_d("Mumbai","Bhubaneswar",1850);_d("Mumbai","Mangalore",1000);_d("Mumbai","Thiruvananthapuram",1550);_d("Mumbai","Mysore",1050);
_d("Delhi","Jaipur",280);_d("Delhi","Chandigarh",260);_d("Delhi","Amritsar",450);_d("Delhi","Agra",200);_d("Delhi","Lucknow",555);_d("Delhi","Varanasi",820);_d("Delhi","Patna",1050);_d("Delhi","Kolkata",1480);_d("Delhi","Bhopal",770);_d("Delhi","Indore",870);_d("Delhi","Jodhpur",620);_d("Delhi","Udaipur",670);_d("Delhi","Nagpur",1160);_d("Delhi","Ranchi",1280);_d("Delhi","Bhubaneswar",1700);_d("Delhi","Hyderabad",1570);_d("Delhi","Chennai",2170);_d("Delhi","Kochi",2700);_d("Delhi","Goa",1900);_d("Delhi","Visakhapatnam",1730);_d("Delhi","Coimbatore",2300);_d("Delhi","Mangalore",2100);_d("Delhi","Surat",1150);_d("Delhi","Ahmedabad",950);_d("Delhi","Thiruvananthapuram",2900);_d("Delhi","Mysore",2300);_d("Delhi","Pune",1450);
_d("Chennai","Hyderabad",630);_d("Chennai","Kochi",720);_d("Chennai","Coimbatore",490);_d("Chennai","Visakhapatnam",800);_d("Chennai","Bhubaneswar",1200);_d("Chennai","Kolkata",1650);_d("Chennai","Thiruvananthapuram",750);_d("Chennai","Mangalore",730);_d("Chennai","Mysore",450);_d("Chennai","Goa",930);_d("Chennai","Pune",1180);_d("Chennai","Nagpur",1100);_d("Chennai","Lucknow",1700);_d("Chennai","Patna",1900);_d("Chennai","Ranchi",1700);
_d("Hyderabad","Kochi",1150);_d("Hyderabad","Visakhapatnam",620);_d("Hyderabad","Nagpur",490);_d("Hyderabad","Pune",570);_d("Hyderabad","Goa",690);_d("Hyderabad","Bhubaneswar",1000);_d("Hyderabad","Kolkata",1490);_d("Hyderabad","Lucknow",1400);_d("Hyderabad","Bhopal",880);
_d("Kolkata","Patna",600);_d("Kolkata","Ranchi",410);_d("Kolkata","Bhubaneswar",440);_d("Kolkata","Varanasi",680);_d("Kolkata","Lucknow",1000);_d("Kolkata","Nagpur",1320);
_d("Ahmedabad","Surat",270);_d("Ahmedabad","Jaipur",660);_d("Ahmedabad","Indore",420);_d("Ahmedabad","Jodhpur",490);_d("Ahmedabad","Udaipur",250);_d("Ahmedabad","Bhopal",680);
_d("Jaipur","Agra",240);_d("Jaipur","Jodhpur",340);_d("Jaipur","Udaipur",400);_d("Jaipur","Chandigarh",530);_d("Jaipur","Amritsar",620);_d("Jaipur","Lucknow",580);
_d("Lucknow","Varanasi",320);_d("Lucknow","Patna",415);_d("Lucknow","Agra",370);
_d("Varanasi","Patna",270);_d("Varanasi","Ranchi",520);_d("Chandigarh","Amritsar",230);
_d("Goa","Mangalore",330);_d("Goa","Kochi",640);_d("Kochi","Coimbatore",210);_d("Kochi","Thiruvananthapuram",220);_d("Kochi","Mangalore",450);
_d("Coimbatore","Thiruvananthapuram",340);_d("Coimbatore","Mangalore",420);
_d("Nagpur","Bhopal",360);_d("Nagpur","Indore",460);_d("Nagpur","Ranchi",680);_d("Bhopal","Indore",190);_d("Ranchi","Bhubaneswar",440);_d("Ranchi","Patna",330);
_d("Mysore","Coimbatore",200);_d("Mysore","Mangalore",250);_d("Mysore","Kochi",480);

function getDist(a,b){return DIST[a+"|"+b]||Math.abs(a.charCodeAt(0)-b.charCodeAt(0))*50+400;}

const RATES={
  train:{General:0.5,Sleeper:1.0,"AC 3 Tier":1.8,"AC 2 Tier":2.5,"First Class":3.5},
  bus:{General:1.2,Sleeper:2.0,"AC Seater":2.5,"AC Sleeper":3.0},
  flight:{Economy:5.0,Business:9.0}
};
const FLIGHT_BASE={Economy:800,Business:2000};
const CLASSES={train:["General","Sleeper","AC 3 Tier","AC 2 Tier","First Class"],bus:["General","Sleeper","AC Seater","AC Sleeper"],flight:["Economy","Business"]};

function calcPrice(mode,cls,src,dst,date){
  const dist=getDist(src,dst);
  const rate=RATES[mode]?.[cls]||1.5;
  const base=mode==="flight"?(FLIGHT_BASE[cls]||800):0;
  let price=rate*dist+base;
  if(date){
    const d=new Date(date);
    const day=d.getDay();
    if(day===0||day===6)price*=1.10;
    const hr=d.getHours();
    if((hr>=6&&hr<=9)||(hr>=17&&hr<=21))price*=1.05;
  }
  price*=1.05; // GST
  return Math.round(price);
}

function genPNR(){
  const L="ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  return L[Math.floor(Math.random()*26)]+L[Math.floor(Math.random()*26)]+
    Math.floor(10000000+Math.random()*90000000);
}

async function predictFraud(features){
  try{
    const r=await fetch(`${API}/api/predict_fraud`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(features)});
    return await r.json();
  }catch{return{risk_score:0,risk_level:"LOW"};}
}

function saveTicket(ticket){return db.collection("tickets").add({...ticket,booking_time:firebase.firestore.FieldValue.serverTimestamp()});}
function getUserTickets(uid){return db.collection("tickets").where("user_id","==",uid).get();}
function getTicketByPNR(pnr){return db.collection("tickets").where("pnr","==",pnr).limit(1).get();}
function markTicketUsed(id){return db.collection("tickets").doc(id).update({status:"USED",used_at:firebase.firestore.FieldValue.serverTimestamp()});}
function requestTicketCancellation(id, reason){return db.collection("tickets").doc(id).update({status:"CANCEL_PENDING",cancel_reason:reason,cancel_requested_at:firebase.firestore.FieldValue.serverTimestamp()});}
function approveCancellation(id){return db.collection("tickets").doc(id).update({status:"CANCELLED",refunded_at:firebase.firestore.FieldValue.serverTimestamp()});}
function hideTicketHistory(id){return db.collection("tickets").doc(id).update({user_hidden:true});}
function flagUser(uid,riskLevel,reason){
  return db.collection("users").doc(uid).update({
    flag_status:"SUSPICIOUS",
    flag_reason:reason,
    flag_level:riskLevel,
    flag_count:firebase.firestore.FieldValue.increment(1),
    flagged_at:firebase.firestore.FieldValue.serverTimestamp()
  });
}
function banUser(uid){return db.collection("users").doc(uid).update({flag_status:"BANNED",banned_at:firebase.firestore.FieldValue.serverTimestamp()});}
function clearUserFlag(uid){return db.collection("users").doc(uid).update({flag_status:"CLEAR",flag_reason:"",flag_level:"",cleared_at:firebase.firestore.FieldValue.serverTimestamp()});}
function deleteUserAccount(uid){return db.collection("users").doc(uid).update({flag_status:"DELETED",account_deleted:true,deleted_at:firebase.firestore.FieldValue.serverTimestamp()});}
function getFlaggedUsers(){return db.collection("users").where("flag_status","in",["SUSPICIOUS","BANNED"]).get();}
function logScanAlert(data){return db.collection("scan_alerts").add({...data,logged_at:firebase.firestore.FieldValue.serverTimestamp()});}
function getScanAlerts(){return db.collection("scan_alerts").orderBy("logged_at","desc").limit(50).get();}

function fmtDate(ts){if(!ts)return"—";const d=ts.toDate?ts.toDate():new Date(ts);return d.toLocaleDateString("en-IN",{day:"2-digit",month:"short",year:"numeric"});}
function fmtCur(n){return"₹"+Number(n).toLocaleString("en-IN");}
function scoreColor(s){return s>=65?"score-high":s>=35?"score-med":"score-low";}
function riskBadge(r){const c=r==="HIGH"?"badge-high":r==="MEDIUM"?"badge-med":"badge-low";return`<span class="badge ${c}">${r==="HIGH"?"🔴":"🟡"} ${r}</span>`;}
