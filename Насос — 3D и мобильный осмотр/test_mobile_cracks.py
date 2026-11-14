from pathlib import Path
import json
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def main():
    key = json.loads((ROOT / "private/config.json").read_text(encoding="utf-8"))["access_key"]

    def fetch(path, data=None):
        request = urllib.request.Request("http://127.0.0.1:8769" + path, data=data,
                                         headers={"X-Access-Key": key})
        with opener.open(request, timeout=30) as response:
            return response.read()

    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        workers = json.loads(fetch("/api/health"))["models"]
        if all(workers.get(key, {}).get("ready") for key in ("rust", "oil")):
            break
        time.sleep(1)
    else:
        raise TimeoutError("Surface models did not become ready")

    samples = ROOT.parent / "детекция поломок/samples"
    cases = [
        (ROOT / "public/assets/crack-selected-original.jpg", True),
        (samples / "01.jpg", True),
        (samples / "03.jpg", True),
        (samples / "uninformative_control.png", True),
        (ROOT / "public/assets/crack-selected-original.jpg", False),
    ]
    for photo, cracks in cases:
        start = time.monotonic()
        url = f"/api/analyze?tag=AMS-PS-004&quality=1&cracks={int(cracks)}"
        job_id = json.loads(fetch(url, photo.read_bytes()))["id"]
        while time.monotonic() - start < 300:
            result = json.loads(fetch("/api/jobs/" + job_id))
            if result["status"] in ("done", "error"):
                break
            time.sleep(0.5)
        elapsed = time.monotonic() - start
        assert result["status"] == "done", result
        models = {model["key"]: model for model in result["models"]}
        expected = {"rust", "oil", "crack"} if cracks else {"rust", "oil"}
        assert set(models) == expected and all("error" not in m for m in models.values()), models
        if cracks:
            assert models["crack"]["engine"] == "crack_n", models
            assert fetch(f"/results/{job_id}/crack.png").startswith(b"\x89PNG")
        else:
            assert "crack_job" not in result
        assert fetch(result["overlay"]).startswith(b"\xff\xd8")
        assert any(row["frame_id"] == job_id for row in json.loads(fetch("/api/history?tag=AMS-PS-004")))
        print(photo.name, "cracks", cracks, "end_to_end", round(elapsed, 2),
              "server", result["seconds"], "mask_pct", models.get("crack", {}).get("percent"), flush=True)


if __name__ == "__main__":
    main()
