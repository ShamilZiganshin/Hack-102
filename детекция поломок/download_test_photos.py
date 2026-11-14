from pathlib import Path
import json,requests,re,html,concurrent.futures,time,io
from PIL import Image,ImageOps,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent;dest=ROOT/'samples/test_photos';dest.mkdir(exist_ok=True)
commons={}
for p in (ROOT/'research/test_photos').glob('*.json'):
 try:
  for v in json.loads(p.read_text(encoding='utf-8')).get('query',{}).get('pages',{}).values():commons[v['title']]=v
 except Exception:pass
spec=[
('e01','Разрушенная коррозией труба','defect','Проверить выделение открытого повреждения металла.',None,'https://www.lbrk.de/templates/yootheme/cache/2013-02-21-479-1fd1c2d0.jpeg','https://www.lbrk.de/schadensursachen/korrosion'),
('e02','Повреждение изоляции NASA','defect','Открытая/повреждённая наружная изоляция; не утверждать разрыв самой трубы.','File:DAMAGED FOAM INSULATION ON LIQUID NITROGEN LN2 PIPING ON ROOF - NARA - 17446109.jpg',None,None),
('e03','Открытая минеральная вата','defect','Проверить повреждение обшивки и открытые волокна.',None,'https://www.inuma.net/fileadmin/_processed_/csm_kmf3_rohr_f235a25728.jpg','https://www.inuma.net/footer/gebaeude-schadstoffe/kmf/'),
('e04','Сварные стыки нержавеющих труб','control','Контроль: шов не следует автоматически считать трещиной. Исправность не подтверждена.','File:Stainless pipe weld joints.jpg',None,None),
('e05','Шов трубы перед обмоткой','control','Контроль ложных тревог на штатном сварном соединении; не экспертное подтверждение исправности.','File:Pipe weld before protective wrapping - geograph.org.uk - 7203352.jpg',None,None),
('e06','Ржавая труба в Duisburg','control','Контроль: коррозия сама по себе не означает наличие видимого разрыва.','File:Duisburg, Landschaftspark Duisburg-Nord -- 2020 -- 7780.jpg',None,None),
('e07','Резервуары в изготовлении','control','Контроль геометрии и сварных швов. Полное состояние оборудования по фото неизвестно.','File:Pressure tanks under construction.jpg',None,None),
('e08','Сломанная металлическая деталь','defect','Видимый излом детали; другой тип объекта для проверки переноса.','File:Pedalarm Bruch.jpg',None,None),
('e09','Сегментированная изоляция','control','Контроль: технологические надрезы и стыки изоляции не равны аварийной трещине металла.','File:Calcium silicate pipe covering, scored block sheets.png',None,None),
('e10','Усталостное разрушение металла','defect','Проверить видимую трещину/излом без вывода о конкретной причине только по кадру.',None,'https://norman-williamson.co.uk/_borders/P1010208.JPG','https://norman-williamson.co.uk/metal_fatigue.htm')]
def strip(s):return html.unescape(re.sub('<[^>]+>','',s or '')).strip()
def fetch(row):
 key,title,kind,purpose,ct,url,page=row
 license='Лицензия не указана; источник сохранён. Локальный исследовательский тест.';author='См. страницу источника'
 if ct:
  v=commons.get(ct)
  if not v:return {'id':key,'error':'Commons metadata not found','title':title}
  inf=v['imageinfo'][0];url=inf.get('thumburl',inf['url']);page=inf.get('descriptionurl');m=inf.get('extmetadata',{});license=strip(m.get('LicenseShortName',{}).get('value',''));author=strip(m.get('Artist',{}).get('value',''))
 for a in range(3):
  try:
   s=requests.Session();resp=s.get(url,headers={'User-Agent':'InspectLabDemo/1.0'},timeout=25);resp.raise_for_status()
   im=ImageOps.exif_transpose(Image.open(io.BytesIO(resp.content))).convert('RGB');original_size=im.size;im.thumbnail((1600,1600),Image.Resampling.LANCZOS);im.save(dest/f'{key}.jpg',quality=94)
   print('Saved',key,title,original_size,flush=True)
   return {'id':key,'title':title,'kind':kind,'purpose':purpose,'source_page':page,'image_url':url,'author':author,'license':license,'size':list(im.size),'note':'No expert masks; examples selected before inference. Training-set overlap unknown.'}
  except Exception as e:print('Retry',key,str(e),flush=True);time.sleep(1)
 return {'id':key,'title':title,'error':'Download failed','source_page':page}
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:rows=list(ex.map(fetch,spec))
 (dest/'sources.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8');ok=[v for v in rows if 'error' not in v]
 f=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',18);small=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',14);cw,ch=360,300;sheet=Image.new('RGB',(cw*3,ch*((len(ok)+2)//3)),(17,19,22));d=ImageDraw.Draw(sheet)
 for i,v in enumerate(ok):
  x=(i%3)*cw;y=(i//3)*ch;im=Image.open(dest/(v['id']+'.jpg'));im.thumbnail((cw-12,ch-65));sheet.paste(im,(x+(cw-im.width)//2,y+(ch-65-im.height)//2));d.text((x+9,y+ch-58),v['id']+' · '+v['title'],font=f,fill=(235,237,240));d.text((x+9,y+ch-28),'Дефект' if v['kind']=='defect' else 'Контроль ложных тревог',font=small,fill=(255,160,110))
 sheet.save(dest/'contact_sheet.jpg',quality=94);print('READY',len(ok),flush=True)
