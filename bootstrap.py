from pathlib import Path
import hashlib
import json
import os
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
APP = ROOT / "Насос — 3D и мобильный осмотр"
version_file = APP / "private/postgres/PG_VERSION"
pg_versions = [version_file.read_text().strip()] if version_file.exists() else ["17","18"]
pg_base = Path(os.environ["ProgramFiles"]) / "PostgreSQL"
PG = next((pg_base/v/"bin" for v in pg_versions if (pg_base/v/"bin/initdb.exe").exists()), pg_base/pg_versions[0]/"bin")


def run(*args, **kwargs):
    subprocess.run(list(map(str, args)), check=True, **kwargs)


def environment():
    env = ROOT / ".venv"
    python = env / "Scripts/python.exe"
    mode = "cpu" if "--cpu" in sys.argv else "cu128"
    lock = ROOT / "requirements.txt"
    marker = env / "installed.sha256"
    digest = hashlib.sha256(lock.read_bytes() + mode.encode()).hexdigest()
    if not python.exists():
        run(sys.executable, "-m", "venv", env)
    if not marker.exists() or marker.read_text() != digest:
        run(python, "-m", "pip", "install", "torch==2.11.0", "torchvision==0.26.0",
            "--index-url", "https://download.pytorch.org/whl/" + mode)
        run(python, "-m", "pip", "install", "-r", lock)
        marker.write_text(digest)
    os.environ["PUMP_DEVICE"] = "cpu" if mode == "cpu" else "cuda"
    if mode != "cpu":
        run(python, "-c", "import torch; print(torch.cuda.get_device_name()); print(torch.ones(1, device='cuda').cpu())")
    return python


def database(python):
    private = APP / "private"
    private.mkdir(exist_ok=True)
    data = private / "postgres"
    config = private / "config.json"
    if not config.exists():
        password = secrets.token_hex(32)
        config.write_text(json.dumps(dict(database=f"host=127.0.0.1 port=55440 dbname=pump_mobile user=pump_mobile password={password}",
            access_key=secrets.token_urlsafe(18), sensor_key=secrets.token_urlsafe(32), demo_epoch=__import__("time").time())), encoding="utf-8")
    from shlex import split
    settings = dict(item.split("=", 1) for item in split(json.loads(config.read_text(encoding="utf-8"))["database"]))
    password = settings["password"]
    env = dict(os.environ, PGPASSWORD=password, PGUSER="pump_mobile", PGHOST="127.0.0.1", PGPORT="55440")
    if not (data / "PG_VERSION").exists():
        pw = private / "init-password.tmp"
        try:
            pw.write_text(password, encoding="ascii")
            run(PG / "initdb.exe", "-D", data, "-U", "pump_mobile", "--pwfile", pw, "-A", "scram-sha-256", "-E", "UTF8")
        finally:
            pw.unlink(missing_ok=True)
        with (data / "postgresql.auto.conf").open("a", encoding="ascii") as f:
            f.write("\nport = 55440\nlisten_addresses = '127.0.0.1'\n")
    if subprocess.run([PG / "pg_ctl.exe", "-D", data, "status"], capture_output=True).returncode:
        run(PG / "pg_ctl.exe", "-D", data, "-l", private / "postgres.log", "-w", "start")
    marker = private / "restore.complete"
    if not marker.exists():
        exists = subprocess.check_output([PG / "psql.exe", "-d", "postgres", "-Atc",
            "SELECT count(*) FROM pg_database WHERE datname='pump_mobile'"], env=env).strip()
        if exists == b"0":
            run(PG / "createdb.exe", "pump_mobile", env=env)
        for filename in ("01_migrate.sql", "mobile_demo.sql"):
            run(PG / "psql.exe", "-v", "ON_ERROR_STOP=1", "-d", "pump_mobile", "-f",
                ROOT / "Насосы_БД" / filename, env=dict(env, PGCLIENTENCODING="UTF8"))
        run(python, APP / "seed_demo.py")
        marker.touch()


def main():
    if not (PG / "initdb.exe").is_file():
        sys.exit("Установите PostgreSQL 17 или 18 для Windows (см. README.md).")
    if (ROOT / ".git").exists():
        run("git", "lfs", "pull", cwd=ROOT)
    for folder in ROOT.iterdir():
        if folder.is_dir() and ((folder / "START.bat").exists() or folder.name.startswith("детекция")):
            (folder / "outputs").mkdir(exist_ok=True)
    with environment_lock():
        python = environment()
        database(python)
        (ROOT / "детекция поломок/outputs").mkdir(exist_ok=True)
        run("powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ROOT / "START_RTX.ps1")


from contextlib import contextmanager
@contextmanager
def environment_lock():
    import msvcrt
    with (ROOT / ".setup.lock").open("a+b") as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        yield


if __name__ == "__main__":
    main()

