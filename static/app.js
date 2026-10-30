(function(){
  const byId = id => document.getElementById(id);
  const categoryNames = {pothole:'Road / Pothole',waste:'Waste',water:'Water',drainage:'Drainage',streetlight:'Streetlight',other:'Other'};
  const colors = {Critical:'#e2523f',High:'#e88a3d',Medium:'#d9b84c',Low:'#4fb286'};
  let reportMap = null, reportMarker = null, overviewMap = null;
  const mapEl = byId('map');
  if (mapEl && window.L) {
    reportMap = L.map('map').setView([12.9716,79.1325],12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}).addTo(reportMap);
    reportMap.on('click', e => selectLocation(e.latlng.lat,e.latlng.lng,'Pinned location'));
    setTimeout(()=>reportMap.invalidateSize(),150);
  }
  function selectLocation(lat,lng,label){
    if(!reportMap) return;
    byId('latitude').value=lat; byId('longitude').value=lng; byId('location_label').value=label||'';
    if(reportMarker) reportMap.removeLayer(reportMarker);
    reportMarker=L.marker([lat,lng]).addTo(reportMap).bindPopup(label||'Selected location').openPopup();
    reportMap.setView([lat,lng],15);
    byId('location-hint').textContent=`Selected: ${label||'Map pin'} · ${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  }
  async function searchPlace(query){
    if(!query || query.trim().length<3){alert('Enter at least 3 characters to search.');return;}
    const button=byId('search-location'); button.disabled=true; button.textContent='Searching…';
    try{
      const url='https://nominatim.openstreetmap.org/search?format=json&limit=5&countrycodes=in&q='+encodeURIComponent(query);
      const res=await fetch(url,{headers:{'Accept-Language':'en'}}); if(!res.ok) throw new Error('Location service unavailable');
      const rows=await res.json(); if(!rows.length){alert('No matching place found. Try a wider area name.');return;}
      const choice=rows.length===1?rows[0]:rows[0];
      if(rows.length>1){const list=rows.map((r,i)=>`${i+1}. ${r.display_name}`).join('\n');const ans=prompt('Choose a matching place by number:\n'+list,'1');if(!ans)return;const idx=Number(ans)-1;if(!Number.isInteger(idx)||idx<0||idx>=rows.length){alert('Invalid choice.');return;}selectLocation(Number(rows[idx].lat),Number(rows[idx].lon),rows[idx].display_name);}
      else selectLocation(Number(choice.lat),Number(choice.lon),choice.display_name);
    }catch(e){alert('Location search failed. You can still tap the map to choose a location.');}
    finally{button.disabled=false;button.textContent='Find';}
  }
  if(byId('search-location')) byId('search-location').addEventListener('click',()=>searchPlace(byId('location-search').value));
  if(byId('location-search')) byId('location-search').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();searchPlace(e.target.value);}});
  if(byId('use-gps')) byId('use-gps').addEventListener('click',()=>{
    if(!navigator.geolocation){alert('This browser does not support GPS location.');return;}
    byId('use-gps').disabled=true;
    navigator.geolocation.getCurrentPosition(p=>{selectLocation(p.coords.latitude,p.coords.longitude,'Current GPS location');byId('use-gps').disabled=false;},()=>{alert('Location permission was denied or GPS is unavailable. Tap the map to select a location.');byId('use-gps').disabled=false;},{enableHighAccuracy:true,timeout:12000,maximumAge:0});
  });
  if(byId('find-pin')) byId('find-pin').addEventListener('click',async()=>{
    const pin=byId('pin-code').value.trim();if(!/^\d{6}$/.test(pin)){alert('Enter a valid 6-digit Indian PIN code.');return;}
    try{const r=await fetch('https://nominatim.openstreetmap.org/search?format=json&limit=1&country=India&postalcode='+encodeURIComponent(pin));const d=await r.json();if(!d.length){alert('No location found for this PIN. Try address search.');return;}selectLocation(Number(d[0].lat),Number(d[0].lon),'PIN '+pin+' · '+d[0].display_name);}catch(e){alert('PIN lookup failed. Tap the map or use address search.');}
  });
  [['severity','severity-value'],['safety_risk','risk-value']].forEach(([input,out])=>{if(byId(input))byId(input).addEventListener('input',()=>byId(out).textContent=byId(input).value);});
  let predictionTimer=null;
  if(byId('description')) byId('description').addEventListener('input',()=>{
    clearTimeout(predictionTimer);const text=byId('description').value.trim();if(text.length<6){byId('prediction').hidden=true;return;}
    predictionTimer=setTimeout(async()=>{try{const r=await fetch('/api/predict',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({description:text})});const d=await r.json();if(!r.ok)throw new Error();byId('prediction').hidden=false;byId('pred-label').textContent=d.label;byId('pred-confidence').textContent=d.model_ready?Math.round(d.confidence*100)+'%':'Model not trained';byId('model-status').textContent=d.model_ready?'Trained model':'Model unavailable';}catch(e){}},450);
  });
  if(byId('photo')) byId('photo').addEventListener('change',()=>{const file=byId('photo').files[0];const img=byId('photo-preview');if(!file){img.hidden=true;return;}if(file.size>8*1024*1024){alert('Photo is larger than 8 MB.');byId('photo').value='';img.hidden=true;return;}img.src=URL.createObjectURL(file);img.hidden=false;});
  if(byId('complaint-form')) byId('complaint-form').addEventListener('submit',e=>{if(!byId('latitude').value||!byId('longitude').value){e.preventDefault();alert('Please select the complaint location on the map, use GPS, or search for a place.');}});
  if(byId('map2') && window.L){
    overviewMap=L.map('map2').setView([12.9716,79.1325],11);L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}).addTo(overviewMap);
    fetch('/api/complaints/map').then(r=>r.ok?r.json():[]).then(rows=>{const points=[];rows.forEach(c=>{const col=colors[c.tier]||'#f2a53d';const m=L.circleMarker([c.latitude,c.longitude],{radius:8,color:col,fillColor:col,fillOpacity:.85}).addTo(overviewMap);m.bindPopup(`<b>#${c.id} · ${escapeText(c.category)}</b><br>${escapeText(c.description)}<br>Status: ${escapeText(c.status)}<br>Priority: ${c.priority} (${c.tier})`);points.push([c.latitude,c.longitude]);});if(points.length)overviewMap.fitBounds(points,{padding:[20,20],maxZoom:14});}).catch(()=>{});
    setTimeout(()=>overviewMap.invalidateSize(),150);
  }
  function escapeText(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
})();
