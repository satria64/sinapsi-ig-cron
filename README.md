# sinapsi-ig-cron

Cron **cloud** (GitHub Actions) che pubblica i Reel di **Sinapsi** su Instagram,
specchiando i video già usciti sulla Pagina **Facebook** — così non serve il PC acceso.

- **`cloud_ig_publish.py`** — legge i video pubblicati su FB, trova quelli non ancora su IG
  (dedup via API IG + `ig_posted.json`), e li pubblica come Reels usando i video/copertine
  ospitati nei **Release** di questo repo. Rinnova da solo il token IG (60 gg).
- **`mapping.json`** — caption-key → `{video_url, cover_url, caption}` (Release assets).
- **`ig_posted.json`** — stato (cosa è già stato pubblicato/saltato). Aggiornato dal workflow.
- **`.github/workflows/ig.yml`** — schedule 07:35/12:35/19:35 IT (UTC 05:35/10:35/17:35) + avvio manuale.

## Secrets necessari
`IG_TOKEN`, `IG_USER_ID`, `FB_PAGE_TOKEN`, `FB_PAGE_ID`, `GH_PAT` (per aggiornare IG_TOKEN al refresh).

I video (Release `videos`) sono già pubblici su YouTube/FB/IG. Nessun dato sensibile nel repo.
