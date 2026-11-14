from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent/'passport_files'

def install(db):
    catalog=json.loads((ROOT/'index.json').read_text('utf8'))
    with db() as c:
        c.execute('SELECT pg_advisory_xact_lock(102,4104)')
        for a in catalog['assets']:
            tag=a['tag']
            eq=c.execute('SELECT id,serial_no FROM equipment WHERE tag=%s FOR UPDATE',(tag,)).fetchone()
            if not eq or eq['serial_no'] not in (None,'','DEMO-'+tag[-3:],a['serial_no']):
                raise ValueError('Проверьте соответствие заводского номера для '+tag)
            eid=eq['id'];name=a['passport_file'];digest=a['sha256']
            doc=c.execute('SELECT id FROM documents WHERE sha256=%s',(digest,)).fetchone()
            if not doc:
                data=(ROOT/name).read_bytes()
                if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Повреждён файл '+name)
                doc=c.execute("""INSERT INTO documents(sha256,filename,mime_type,content,size_bytes,source_url,text_status)
                  VALUES (%s,%s,'application/pdf',%s,%s,%s,'needs_ocr') RETURNING id""",
                  (digest,name,data,len(data),catalog['source_url'])).fetchone()
            did=doc['id'];m=catalog['model']
            c.execute('INSERT INTO pump_models(model_code,manufacturer,pump_type,description) VALUES (%s,%s,%s,%s) ON CONFLICT(model_code) DO NOTHING',
                      tuple(m[k] for k in ('model_code','manufacturer','pump_type','description')))
            c.execute("""UPDATE equipment SET serial_no=%s,name=%s,model_id=(SELECT id FROM pump_models WHERE model_code=%s),
                        data_origin='passport',identity_note=%s WHERE id=%s""",(a['serial_no'],a['name'],a['model_code'],a['identity_note'],eid))
            c.execute('INSERT INTO equipment_documents(equipment_id,document_id,role,relation_basis) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING',(eid,did,'passport',a['identity_note']))
            c.execute('UPDATE equipment_passports SET is_current=false WHERE equipment_id=%s AND document_id<>%s AND is_current',(eid,did))
            pid=c.execute("""INSERT INTO equipment_passports(equipment_id,document_id,identity_page) VALUES (%s,%s,%s)
                         ON CONFLICT(equipment_id,document_id) DO UPDATE SET is_current=true RETURNING id""",(eid,did,a['identity_page'])).fetchone()['id']
            for v in a['parameters']:
                c.execute("""INSERT INTO passport_parameters(passport_id,code,label,value_num,value_text,min_value,max_value,unit,operating_condition,source_document_id,source_page,source_locator,verification_status)
                          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                          (pid,*(v[k] for k in ('code','label','value_num','value_text','min_value','max_value','unit','operating_condition')),did,v['source_page'],v['source_locator'],v['verification_status']))
