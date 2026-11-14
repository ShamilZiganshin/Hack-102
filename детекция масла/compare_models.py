from oil_model import *
from PIL import ImageDraw,ImageFont
from html import escape
if __name__=='__main__':
 sources=json.loads((ROOT/'samples/sources.json').read_text(encoding='utf-8'));rows=[]
 for variant in ['nano','medium']:
  model=OilDetector(variant)
  for sample in sources:
   im=ImageOps.exif_transpose(Image.open(ROOT/'samples'/sample['file'])).convert('RGB');im.thumbnail((2048,2048));rgb=np.array(im)
   result=model.predict(rgb);out=ROOT/'outputs'/f"{variant}_{sample['id']}"
   metadata=save_prediction(rgb,result,out,{'image':sample['file'],'sample_id':sample['id'],'source':sample['source'],'title':sample['title'],'ground_truth':False})
   rows.append(metadata);print(variant,sample['id'],'detections at .80:',metadata['count'],'area',metadata['mask_percent_of_image'],'time',metadata['seconds'],flush=True)
 (ROOT/'outputs/comparison.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
 html='''<!doctype html><meta charset="utf-8"><title>OilTrace: результаты 13 реальных фото</title><style>body{font:15px Segoe UI;background:#11171b;color:#e5edf2;padding:30px}h1{font-size:26px}p{max-width:1050px;line-height:1.6;color:#adbfc8}.row{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:35px}img{width:100%;height:350px;object-fit:contain;background:#080b0d}a{color:#62d7c0}.caption{font-size:13px;color:#a5b8c3}</style><h1>Автоматическое выделение следов масла</h1><p>Все 13 реальных фотографий из выбранной подборки, без удаления неудачных результатов. Слева оригинал, затем Nano и Medium. Порог уверенности 0.80. Это визуальная демонстрация, эталонной разметки нет, IoU/precision/recall здесь не измерялись. Возможны пропуски и выделение целых деталей вместо масла. Нулевой результат не доказывает отсутствие утечки. Принадлежность фото к исходному обучению неизвестна.</p>'''
 for sample in sources:
  html+=f"<h2>{escape(sample['title'])}</h2><div class='row'>"
  for variant in ['original','nano','medium']:
   meta=next(x for x in rows if x['model']==('nano' if variant=='original' else variant) and x['sample_id']==sample['id'])
   path=f"{('nano' if variant=='original' else variant)}_{sample['id']}/{'original.jpg' if variant=='original' else 'overlay.jpg'}"
   caption='Оригинал' if variant=='original' else f"{variant}: {meta['count']} областей; {meta['seconds']:.2f} с"
   html+=f"<div><img src='{path}'><div class='caption'>{caption}</div></div>"
  html+=f"</div><a href='{escape(sample['source'],quote=True)}'>Источник фотографии</a>"
 (ROOT/'outputs/Все результаты.html').write_text(html,encoding='utf-8')
 # Compact preview preserves a strong example, a miss, and a hard example.
 w,h=460,350;preview=Image.new('RGB',(w*3,55+3*(h+45)),(17,23,27));draw=ImageDraw.Draw(preview);font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',18)
 for col,title in enumerate(['Оригинал','YOLO26 Nano · порог 0.80','YOLO26 Medium · порог 0.80']):draw.text((col*w+12,15),title,font=font,fill='white')
 for row,name in enumerate(['vehicle_pump','tractor_pump','excavator_pump']):
  for col,v in enumerate(['original','nano','medium']):
   p=ROOT/'outputs'/f"{('nano' if v=='original' else v)}_{name}"/('original.jpg' if v=='original' else 'overlay.jpg')
   im=ImageOps.contain(Image.open(p),(w,h));preview.paste(im,(col*w+(w-im.width)//2,55+row*(h+45)+(h-im.height)//2))
  draw.text((12,55+row*(h+45)+h+7),name,font=font,fill='white')
 preview.save(ROOT/'outputs/demo_comparison.jpg',quality=93)
 print('Comparison complete',len(rows),flush=True)
