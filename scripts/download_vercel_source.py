"""
Telecharge le code source d'un deploiement Vercel CLI (sans git connecte).
Cas d'usage : recuperer le code source frontend oparence-site sur un nouveau Mac
ou apres perte du repo local.

Usage:
  python3 scripts/download_vercel_source.py

Le script :
  1. Trouve le token Vercel local (vercel link prerequis)
     OU lit VERCEL_TOKEN depuis l'env
  2. Liste l'arborescence du deploy READY actuel
  3. Telecharge tous les fichiers source (exclut node_modules, .next, _next)
  4. Reconstruit l'arborescence dans le dossier courant
"""
import os, json, sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

DEPLOYMENT_ID = "dpl_HC2EzpGKtLWd5GWPupNzpw3aFmFH"
TEAM_ID = "team_mlX0NPUpUzXYxRIiSeTEjiVw"
OUT_DIR = Path.cwd()

auth_paths = [
    Path.home() / "Library/Application Support/com.vercel.cli/auth.json",
    Path.home() / ".local/share/com.vercel.cli/auth.json",
]
token = None
for p in auth_paths:
    if p.exists():
        data = json.loads(p.read_text())
        token = data.get("token")
        if token:
            print(f"OK token trouve dans {p}")
            break

if not token:
    token = os.environ.get("VERCEL_TOKEN")
    if not token:
        print("ABORT pas de token Vercel local et VERCEL_TOKEN non defini")
        print("Cree un token sur https://vercel.com/account/tokens puis :")
        print("  VERCEL_TOKEN=xxx python3 scripts/download_vercel_source.py")
        sys.exit(1)
    print("OK token via env VERCEL_TOKEN")

def vapi(path):
    url = f"https://api.vercel.com{path}"
    sep = "&" if "?" in url else "?"
    url += f"{sep}teamId={TEAM_ID}"
    req = Request(url, headers={"Authorization": f"Bearer {token}"})
    return urlopen(req).read()

tree = json.loads(vapi(f"/v6/deployments/{DEPLOYMENT_ID}/files"))
print(f"Racine : {len(tree)} entrees")

def walk(entries, base):
    files = []
    for e in entries:
        name = e.get("name", "")
        etype = e.get("type", "")
        path = base / name
        if etype == "directory":
            children = e.get("children", []) or []
            files.extend(walk(children, path))
        elif etype == "file":
            uid = e.get("uid")
            if uid:
                files.append((path, uid))
    return files

all_files = walk(tree, Path("."))
print(f"Total files : {len(all_files)}")

n_ok, n_skip, n_err = 0, 0, 0
for path, uid in all_files:
    if any(p in str(path) for p in ["node_modules", ".next", "_next"]):
        n_skip += 1
        continue
    target = OUT_DIR / path
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        content = vapi(f"/v8/deployments/{DEPLOYMENT_ID}/files/{uid}")
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "data" in parsed:
                import base64
                content = base64.b64decode(parsed["data"])
        except Exception:
            pass
        target.write_bytes(content)
        n_ok += 1
    except HTTPError as ex:
        n_err += 1
        print(f"ERR {path} : {ex.code}")

print(f"Resume : {n_ok} telecharges, {n_skip} skipped, {n_err} erreurs")
print(f"Destination : {OUT_DIR}")
