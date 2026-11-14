function showAlerts(data){
 cameraReadings(data);
 const box=document.querySelector('#alertBox');box.replaceChildren();box.hidden=!data?.alerts?.length;
 if(box.hidden)return;
 const title=document.createElement('strong');title.textContent=data.demo?'ALERT · ДЕМО':'ALERT · ДАТЧИКИ';box.append(title);
 for(const alert of data.alerts){
  const p=document.createElement('p');p.textContent=alert.level+' · '+alert.label+' '+alert.value+' '+alert.unit+' — '+alert.direction+' '+alert.limit+' '+alert.unit+'. '+alert.advice;box.append(p);
 }
 if(data.demo){const note=document.createElement('small');note.textContent=data.spectrum_source;box.append(note)}
}
