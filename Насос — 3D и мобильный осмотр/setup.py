from pathlib import Path
import sys,json,shutil,secrets,time,base64,re,subprocess,ipaddress,socket
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'vendor'))
import qrcode
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
P=ROOT/'private';A=ROOT/'public/assets';P.mkdir(exist_ok=True);A.mkdir(exist_ok=True)
conf=P/'config.json'
cfg=json.loads(conf.read_text(encoding='utf-8')) if conf.exists() else {'database':'host=127.0.0.1 port=55440 dbname=pump_mobile user=pump_mobile','access_key':secrets.token_urlsafe(18),'sensor_key':secrets.token_urlsafe(32),'demo_epoch':time.time()}
ips=sorted({a[4][0] for a in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET)}|{'127.0.0.1'})
cfg['ips']=ips;cfg['preferred_ip']=next((x for x in ips if x.startswith('10.161.')),next((x for x in ips if x.startswith('192.168.')), '127.0.0.1'))
conf.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
if not (P/'ca-key.pem').exists():
 key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
 subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Kiber102 local camera CA')])
 cert=x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc)-timedelta(days=1)).not_valid_after(datetime.now(timezone.utc)+timedelta(days=365)).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).add_extension(x509.KeyUsage(digital_signature=True,key_encipherment=False,key_cert_sign=True,crl_sign=True,content_commitment=False,data_encipherment=False,key_agreement=False,encipher_only=False,decipher_only=False),critical=True).sign(key,hashes.SHA256())
 (P/'ca-key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
 (P/'ca.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
else:
 key=serialization.load_pem_private_key((P/'ca-key.pem').read_bytes(),password=None);cert=x509.load_pem_x509_certificate((P/'ca.pem').read_bytes())
(ROOT/'public/kiber102-ca.cer').write_bytes(cert.public_bytes(serialization.Encoding.DER))
serverkey=rsa.generate_private_key(public_exponent=65537,key_size=2048)
servercert=x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Kiber102 LAN inspection')])).issuer_name(cert.subject).public_key(serverkey.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc)-timedelta(days=1)).not_valid_after(datetime.now(timezone.utc)+timedelta(days=90)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),x509.DNSName(socket.gethostname())]+[x509.IPAddress(ipaddress.ip_address(ip)) for ip in ips]),critical=False).add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True).add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),critical=False).sign(key,hashes.SHA256())
(P/'server.pem').write_bytes(servercert.public_bytes(serialization.Encoding.PEM));(P/'server-key.pem').write_bytes(serverkey.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
for i in range(1,5):qrcode.make(f'KIBER102:AMS-PS-00{i}').save(A/f'qr-AMS-PS-00{i}.png')
url=f"https://{cfg['preferred_ip']}:8443/mobile.html#key={cfg['access_key']}"
qrcode.make(url).save(P/'connect-qr.png')
httpurl=url.replace('https:','http:').replace(':8443',':8769')
qrcode.make(httpurl).save(P/'photo-connect-qr.png')
connect=f'''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Телефон — подключение</title><style>body{{font:17px system-ui;background:#eef2f0;color:#182f35;max-width:850px;margin:40px auto;padding:20px}}section{{background:white;padding:28px;border-radius:18px;margin:16px 0}}img{{width:220px;float:right}}a{{color:#176a64}}code{{overflow-wrap:anywhere}}h1{{font-size:38px}}section:after{{content:'';display:block;clear:both}}</style><h1>Телефон → насос → паспорт</h1><p>Компьютер и телефон должны находиться в одной Wi-Fi сети. Камера и вычисления работают раздельно: кадры обрабатывает этот компьютер.</p><section><img src="data:image/png;base64,{base64.b64encode((P/'photo-connect-qr.png').read_bytes()).decode()}"><h2>1. Быстрый запуск со снимками</h2><p><a href="{httpurl}">{httpurl.split('#')[0]}</a></p><p>Сканируйте этот QR обычной камерой телефона. На странице нажмите «Сфотографировать QR» или «Снять оборудование». Снимки работают без установки сертификата.</p></section><section><img src="data:image/png;base64,{base64.b64encode((P/'connect-qr.png').read_bytes()).decode()}"><h2>2. Непрерывная камера</h2><p><a href="{url}">{url.split('#')[0]}</a></p><p>Для непрерывной камеры требуется доверенный HTTPS. На телефоне установите локальный сертификат <a href="http://{cfg['preferred_ip']}:8769/kiber102-ca.cer">kiber102-ca.cer</a>. iPhone: установить профиль, затем Настройки → Основные → Об этом устройстве → Доверие сертификатам. Android: Безопасность → Шифрование и учётные данные → Установить сертификат CA (названия зависят от устройства).</p><p>Сертификат доверия предназначен только для этого стенда. Его закрытый ключ остаётся на компьютере. Если телефон управляется организацией, установка может быть запрещена — используйте снимки или доверенный HTTPS организации.</p></section><section><h2>Если страница не открывается</h2><p>Проверьте одинаковую Wi-Fi сеть, изоляцию клиентов в роутере и Windows Firewall. Скрипт ALLOW_LAN.ps1 добавляет правила только для портов 8769 и 8443 и локальной подсети. Запускать от администратора. Текущий адрес: {cfg['preferred_ip']}. При смене сети повторите START.bat — адреса и сертификат обновятся.</p><p>Код доступа (если ссылка потерялась): <code>{cfg['access_key']}</code></p></section></html>'''
(ROOT/'Подключить телефон.html').write_text(connect,encoding='utf-8')
print('Network setup generated for',cfg['preferred_ip'])
