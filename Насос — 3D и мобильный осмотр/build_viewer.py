from pathlib import Path
import json,base64,shutil,re
ROOT=Path(__file__).resolve().parent;OLD=ROOT.parent/'3D насосная — единая демонстрация';PUB=ROOT/'public';A=PUB/'assets'
def data(p,mime):return 'data:'+mime+';base64,'+base64.b64encode(p.read_bytes()).decode()
shutil.copy2(ROOT.parent/'детекция масла/samples/vehicle_pump.jpg',A/'oil-photo.jpg')
shutil.copy2(ROOT.parent/'детекция ржавчины/data/corrosion-in-industrial-complexes-in-ostrava/test/images/02.jpg',A/'rust-photo.jpg')
assets={'model':data(A/'water-pump.glb','model/gltf-binary'),'rustTexture':data(A/'rust_surface.png','image/png'),'rust':data(A/'rust-photo.jpg','image/jpeg'),'oil':data(A/'oil-photo.jpg','image/jpeg'),'qr':data(A/'qr-AMS-PS-001.png','image/png')}
shutil.copy2(ROOT.parent/'детекция поломок/samples/02.jpg',A/'crack-photo.jpg')
assets['crack']=data(A/'crack-photo.jpg','image/jpeg')
assets['overlays']={k:data(A/(k+'-selected-overlay.jpg'),'image/jpeg') for k in ['rust','oil','crack']}
assets['results']=json.loads((ROOT/'outputs/photo-selection/selected_results.json').read_text(encoding='utf-8'))
assets['qrs']=[data(A/f'qr-AMS-PS-00{i}.png','image/png') for i in range(1,5)]
modules={}
for name,file in [('three-core','three.core.js'),('three','three.module.js'),('gltf','GLTFLoader.js'),('orbit','OrbitControls.js'),('room','RoomEnvironment.js'),('utils','utils/BufferGeometryUtils.js')]:
 s=(OLD/'vendor'/file).read_text(encoding='utf-8').replace("'./three.core.js'","'three-core'").replace("'../utils/BufferGeometryUtils.js'","'utils'")
 modules[name]=s
s=(OLD/'scene.js').read_text(encoding='utf-8');s=s[s.index('function mat('):s.index('// Missing fastener:')]
s=re.sub(r'// Insulation with.*?// Rust is represented', '// Rust is represented',s,flags=re.S)
s=s.replace("flange([2.25,1.47,0],.34,'x',true)","flange([2.25,1.47,0],.34,'x')")
s=s.replace("'./assets/water-pump.glb'",'ASSETS.model').replace("'/assets/rust_surface.png'",'ASSETS.rustTexture')
s=s.replace("const oil=mat(","const oilGroup=new THREE.Group();scene.add(oilGroup);const oil=mat(")
s=s.replace("// Wet residue", "// Wet residue")
# Collect all meshes added after the oil material: this group toggles with scenario.
s=s.replace("const oilGroup=", "const beforeOil=new Set(scene.children);const oilGroup=")
s+='\nfor(const o of [...scene.children])if(!beforeOil.has(o)&&o!==oilGroup)oilGroup.attach(o);\n'
# Rest of viewer is deliberately separate from the scenario/video dashboard.
app=(ROOT/'viewer.js').read_text(encoding='utf-8').replace('/* GEOMETRY */',s)
modules['viewer']=app
html=(ROOT/'viewer.html').read_text(encoding='utf-8')
bootstrap='window.ASSETS='+json.dumps(assets)+';const sources='+json.dumps(modules,ensure_ascii=False)+';const imports={};for(const [k,v] of Object.entries(sources))imports[k]=URL.createObjectURL(new Blob([v],{type:"text/javascript"}));const map=document.createElement("script");map.type="importmap";map.textContent=JSON.stringify({imports});document.head.append(map);import("viewer").catch(e=>{document.querySelector("#loading").textContent="Ошибка 3D: "+e.message;console.error(e)});'
html=html.replace('/* BUNDLE */',bootstrap.replace('</script','<\\/script'))
(PUB/'viewer.html').write_text(html,encoding='utf-8');(ROOT/'Насос — свободный 3D.html').write_text(html,encoding='utf-8')
shutil.copy2(OLD/'vendor/THREE-LICENSE.txt',ROOT/'THREE-LICENSE.txt')
print('Standalone HTML bytes:',len(html.encode()))
