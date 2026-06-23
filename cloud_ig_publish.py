#!/usr/bin/env python3
"""Specchia su INSTAGRAM (Reels) i video già pubblicati su FACEBOOK ma non ancora su IG.

Gira in GitHub Actions (cloud) → nessun PC necessario. I video e le copertine sono
serviti dai Release di questo repo (URL pubblici). FB è il registro maestro.

Env (da GitHub Secrets): IG_TOKEN, IG_USER_ID, FB_PAGE_TOKEN, FB_PAGE_ID, GH_PAT (per
aggiornare il secret del token rinnovato). Opz: IG_MAX (default 4). GITHUB_REPOSITORY (auto).
Stato: ig_posted.json (committato dal workflow). Mappa video/caption/url: mapping.json.
"""
import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

IGH = "https://graph.instagram.com"
FBH = "https://graph.facebook.com/v21.0"
HERE = Path(__file__).resolve().parent

IG_TOKEN = os.environ["IG_TOKEN"]
IG_USER = os.environ["IG_USER_ID"]
PAGE_TOKEN = os.environ["FB_PAGE_TOKEN"]
PAGE_ID = os.environ["FB_PAGE_ID"]
MAX = int(os.environ.get("IG_MAX", "4"))

mapping = json.loads((HERE / "mapping.json").read_text())
STATE = HERE / "ig_posted.json"
state = json.loads(STATE.read_text()) if STATE.exists() else {}


def norm_key(s):
    return re.sub(r"\s+", " ", s).strip().lower()[:35]


def jget(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def fb_published():
    items, url = [], f"{FBH}/{PAGE_ID}/videos?" + urllib.parse.urlencode(
        {"fields": "description,created_time", "limit": "100", "access_token": PAGE_TOKEN})
    while url:
        j = jget(url)
        for v in j.get("data", []):
            d = (v.get("description") or "").strip()
            if d:
                items.append((v.get("created_time", ""), norm_key(d.splitlines()[0])))
        url = j.get("paging", {}).get("next")
    items.sort()
    return items


def ig_existing():
    keys, url = set(), f"{IGH}/me/media?" + urllib.parse.urlencode(
        {"fields": "caption", "limit": "100", "access_token": IG_TOKEN})
    while url:
        j = jget(url)
        for m in j.get("data", []):
            c = (m.get("caption") or "").strip()
            if c:
                keys.add(norm_key(c.splitlines()[0]))
        url = j.get("paging", {}).get("next")
    return keys


def ig_get(path, **p):
    p["access_token"] = IG_TOKEN
    try:
        return jget(f"{IGH}/{path}?" + urllib.parse.urlencode(p))
    except urllib.error.HTTPError as e:
        return {"_err": json.load(e).get("error", {})}


def ig_post(path, **p):
    p["access_token"] = IG_TOKEN
    req = urllib.request.Request(f"{IGH}/{path}", data=urllib.parse.urlencode(p).encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"_err": json.load(e).get("error", {})}


def publish(entry):
    params = {"media_type": "REELS", "video_url": entry["video_url"], "caption": entry["caption"]}
    if entry.get("cover_url"):
        params["cover_url"] = entry["cover_url"]
    c = ig_post(f"{IG_USER}/media", **params)
    if "_err" in c:
        raise RuntimeError(f"container: {c['_err'].get('message', '')[:140]}")
    cid = c["id"]
    for _ in range(30):
        time.sleep(8)
        sc = ig_get(cid, fields="status_code").get("status_code")
        if sc == "FINISHED":
            break
        if sc in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"elaborazione {sc}")
    else:
        raise RuntimeError("timeout elaborazione")
    pub = ig_post(f"{IG_USER}/media_publish", creation_id=cid)
    if "_err" in pub:
        raise RuntimeError(f"publish: {pub['_err'].get('message', '')[:140]}")
    return pub["id"]


def refresh_token_and_store():
    """Rinnova il token IG (estende 60gg) e aggiorna il secret IG_TOKEN via API (cifrato)."""
    pat = os.environ.get("GH_PAT")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not (pat and repo):
        return
    try:
        r = jget(f"{IGH}/refresh_access_token?" + urllib.parse.urlencode(
            {"grant_type": "ig_refresh_token", "access_token": IG_TOKEN}))
        new = r.get("access_token")
        if not new:
            return
        from nacl import encoding, public  # PyNaCl installato dal workflow
        req = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
                                     headers={"Authorization": f"token {pat}", "Accept": "application/vnd.github+json"})
        pk = json.load(urllib.request.urlopen(req, timeout=30))
        sealed = public.SealedBox(public.PublicKey(pk["key"].encode(), encoding.Base64Encoder)).encrypt(new.encode())
        body = json.dumps({"encrypted_value": base64.b64encode(sealed).decode(), "key_id": pk["key_id"]}).encode()
        put = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/secrets/IG_TOKEN",
                                     data=body, method="PUT",
                                     headers={"Authorization": f"token {pat}", "Accept": "application/vnd.github+json"})
        urllib.request.urlopen(put, timeout=30)
        print("  token IG rinnovato e secret aggiornato.")
    except Exception as e:
        print(f"  (refresh token non riuscito: {str(e)[:120]})")


def main():
    fb = fb_published()
    seen = ig_existing() | {v.get("key") for v in state.values() if v.get("key")}
    todo = []
    for _ct, k in fb:
        if k in seen or k not in mapping:
            continue
        todo.append(k)
        seen.add(k)
    todo = todo[:MAX]
    print(f"FB pubblicati: {len(fb)} | da specchiare su IG ora: {len(todo)} (max {MAX})")
    for k in todo:
        e = mapping[k]
        try:
            mid = publish(e)
            state[e["file"]] = {"id": mid, "key": k}
            STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1))
            print(f"  OK {e['file']} -> {mid}")
        except Exception as ex:
            print(f"  FAIL {e['file']}: {str(ex)[:140]}")
    refresh_token_and_store()


if __name__ == "__main__":
    main()
