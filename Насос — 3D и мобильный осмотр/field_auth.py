"""PostgreSQL-backed role cabinets and repair journal for the pump stand."""
import hashlib
import hmac
import io
import json
import re
import secrets
import ssl
from http.cookies import SimpleCookie
from PIL import Image, ImageOps

ROLES = ('admin', 'brigadir', 'worker')
STATES = ('open', 'review', 'fixed', 'unfixed')

class Rejected(Exception):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)

def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 350000)

def setup(db, outputs):
    with db() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS field_users (
          id bigserial PRIMARY KEY, login text UNIQUE NOT NULL, role text NOT NULL CHECK(role IN ('worker','brigadir','admin')),
          salt bytea NOT NULL, digest bytea NOT NULL);
        CREATE TABLE IF NOT EXISTS field_sessions (
          token text PRIMARY KEY, user_id bigint NOT NULL REFERENCES field_users ON DELETE CASCADE, expires timestamptz NOT NULL);
        CREATE TABLE IF NOT EXISTS field_records (
          id bigserial PRIMARY KEY, tag text NOT NULL REFERENCES equipment(tag), author text NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(), photo bytea, legacy_frame text UNIQUE,
          state text NOT NULL DEFAULT 'open' CHECK(state IN ('open','review','fixed','unfixed')),
          note text NOT NULL DEFAULT '', version int NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS field_events (
          id bigserial PRIMARY KEY, record_id bigint NOT NULL REFERENCES field_records ON DELETE CASCADE,
          actor text NOT NULL, state text NOT NULL, comment text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
        CREATE TABLE IF NOT EXISTS field_migrations(name text PRIMARY KEY);
        """)
        if c.execute("INSERT INTO field_migrations VALUES ('bootstrap') ON CONFLICT DO NOTHING RETURNING name").fetchone():
            salt=secrets.token_bytes(16)
            c.execute("INSERT INTO field_users(login,role,salt,digest) VALUES ('admin','admin',%s,%s)",(salt,password_hash('admin',salt)))
            for row in c.execute("SELECT frame_id, inspections.created_at, tag FROM inspections JOIN equipment ON equipment.id=inspections.equipment_id ORDER BY inspections.id").fetchall():
                frame=row['frame_id']
                if not re.fullmatch(r'[0-9a-f]{16}',str(frame)):continue
                p=outputs/frame/'frame.jpg'
                c.execute("INSERT INTO field_records(tag,author,created_at,photo,legacy_frame) VALUES (%s,'Архив',%s,%s,%s) ON CONFLICT DO NOTHING",
                          (row['tag'],row['created_at'],p.read_bytes() if p.is_file() else None,frame))

def identity(c,h):
    cookies=SimpleCookie()
    cookies.load(h.headers.get('Cookie',''))
    token=cookies.get('field_session')
    if not token:return None
    key=hashlib.sha256(token.value.encode()).hexdigest()
    return c.execute("""SELECT u.id,login,role FROM field_sessions s JOIN field_users u ON u.id=s.user_id
                        WHERE token=%s AND expires>now()""",(key,)).fetchone()

def require(c,h,roles=ROLES):
    u=identity(c,h)
    if not u:raise Rejected(401,'Войдите в кабинет')
    if u['role'] not in roles:raise Rejected(403,'Действие недоступно для вашей роли')
    return u

def login_cookie(h,value,age):
    secure='; Secure' if isinstance(h.connection,ssl.SSLSocket) or h.headers.get('X-Forwarded-Proto')=='https' else ''
    h.session_cookie=f'field_session={value}; HttpOnly; SameSite=Strict; Path=/; Max-Age={age}{secure}'

def text_field(data,key,limit,required=True):
    v=data.get(key,'')
    if not isinstance(v,str) or len(v)>limit or (required and not v.strip()):
        raise Rejected(400,'Проверьте поле '+key)
    return v.strip()

def dispatch(db,h,path,q,body=None):
    if body is not None and h.headers.get('X-Field-Request')!='1':
        raise Rejected(403,'Недопустимый запрос')
    with db() as c:
        if path=='/api/field/login' and body is not None:
            d=json.loads(body); login=text_field(d,'login',80)
            pw=d.get('password')
            if not isinstance(pw,str) or len(pw)>256:raise Rejected(400,'Проверьте пароль')
            u=c.execute('SELECT * FROM field_users WHERE login=%s FOR SHARE',(login,)).fetchone()
            actual=password_hash(pw,bytes(u['salt']) if u else bytes(16))
            if not u or not hmac.compare_digest(actual,bytes(u['digest'])):raise Rejected(401,'Неверный логин или пароль')
            token=secrets.token_urlsafe(32)
            c.execute('DELETE FROM field_sessions WHERE expires<=now()')
            c.execute("INSERT INTO field_sessions VALUES (%s,%s,now()+interval '12 hours')",(hashlib.sha256(token.encode()).hexdigest(),u['id']))
            login_cookie(h,token,43200)
            return {'role':u['role']}
        u=require(c,h)
        if path=='/api/field/me' and body is None:return u
        if path=='/api/field/logout' and body is not None:
            cookie=SimpleCookie();cookie.load(h.headers['Cookie'])
            c.execute('DELETE FROM field_sessions WHERE token=%s',(hashlib.sha256(cookie['field_session'].value.encode()).hexdigest(),))
            login_cookie(h,'',0)
            return {}
        if path=='/api/field/users':
            if u['role']!='admin':raise Rejected(403,'Только администратор')
            if body is None:return c.execute('SELECT id, login, role FROM field_users ORDER BY login').fetchall()
            d=json.loads(body);uid=d.get('id');op=d.get('op')
            if uid==u['id'] and (op=='delete' or d.get('role')!='admin'):raise Rejected(409,'Нельзя удалить собственный доступ администратора')
            if op=='delete':
                updated=c.execute('DELETE FROM field_users WHERE id=%s RETURNING id',(uid,)).fetchone()
            else:
                login=text_field(d,'login',80);role=d.get('role');pw=d.get('password','')
                if role not in ROLES or not isinstance(pw,str) or len(pw)>256 or (not uid and not pw):raise Rejected(400,'Проверьте роль и пароль')
                if uid:
                    updated=c.execute('UPDATE field_users SET login=%s,role=%s WHERE id=%s RETURNING id',(login,role,uid)).fetchone()
                    if updated and pw:
                        salt=secrets.token_bytes(16)
                        c.execute('UPDATE field_users SET salt=%s,digest=%s WHERE id=%s',(salt,password_hash(pw,salt),uid))
                    if updated:c.execute('DELETE FROM field_sessions WHERE user_id=%s',(uid,))
                else:
                    salt=secrets.token_bytes(16)
                    updated=c.execute('INSERT INTO field_users(login,role,salt,digest) VALUES (%s,%s,%s,%s) RETURNING id',(login,role,salt,password_hash(pw,salt))).fetchone()
            if not updated:raise Rejected(404,'Учётная запись не найдена')
            return {}
        if path=='/api/field/capture' and body is not None:
            if u['role'] not in ('worker','admin'):raise Rejected(403,'Снимки сохраняет работник')
            tag=q.get('tag',[''])[0]
            if not c.execute('SELECT id FROM equipment WHERE tag=%s',(tag,)).fetchone():raise Rejected(400,'Насос не найден')
            with Image.open(io.BytesIO(body)) as im:
                if im.width*im.height>24000000:raise Rejected(400,'Слишком большой снимок')
                out=io.BytesIO();im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((2400,2400));im.save(out,'JPEG',quality=92)
            return c.execute('INSERT INTO field_records(tag,author,photo) VALUES (%s,%s,%s) RETURNING id',(tag,u['login'],out.getvalue())).fetchone()
        if path=='/api/field/records' and body is None:
            before=int(q.get('before',[2**63-1])[0])
            return c.execute("""SELECT id,tag,author,created_at,state,note,version,photo IS NOT NULL AS has_photo
                                FROM field_records WHERE id<%s ORDER BY id DESC LIMIT 50""",(before,)).fetchall()
        match=re.fullmatch(r'/api/field/records/(\d+)(/photo|/events)?',path)
        if not match:raise Rejected(404,'Не найдено')
        rid=int(match[1])
        if body is None:
            if match[2]=='/photo':
                row=c.execute('SELECT photo FROM field_records WHERE id=%s',(rid,)).fetchone()
                if not row or not row['photo']:raise Rejected(404,'Снимок недоступен')
                return bytes(row['photo'])
            if match[2]=='/events':
                return c.execute('SELECT actor,created_at,state,comment FROM field_events WHERE record_id=%s ORDER BY id',(rid,)).fetchall()
            raise Rejected(404,'Не найдено')
        if match[2]:raise Rejected(405,'Метод недоступен')
        d=json.loads(body)
        row=c.execute('SELECT state,note,version FROM field_records WHERE id=%s FOR UPDATE',(rid,)).fetchone()
        if not row:raise Rejected(404,'Запись не найдена')
        if row['version']!=d.get('version'):raise Rejected(409,'Запись изменилась. Обновите историю')
        if d.get('op')=='delete':
            if u['role']!='admin':raise Rejected(403,'Удаление доступно администратору')
            c.execute('DELETE FROM field_records WHERE id=%s',(rid,));return {}
        state=d.get('state',row['state'])
        allowed={'admin':STATES,'brigadir':('fixed','unfixed'),'worker':('review',)}
        comment=text_field(d,'comment',2000,False)
        if state!=row['state'] and state not in allowed[u['role']]:raise Rejected(403,'Недоступный статус')
        if state=='review' and row['state']=='fixed' and u['role']=='worker':raise Rejected(409,'Ремонт уже подтверждён')
        note=text_field(d,'note',2000,False) if u['role']=='admin' and 'note' in d else row['note']
        c.execute('UPDATE field_records SET state=%s,note=%s,version=version+1 WHERE id=%s',(state,note,rid))
        c.execute('INSERT INTO field_events(record_id,actor,state,comment) VALUES (%s,%s,%s,%s)',(rid,u['login'],state,comment))
        return {}

