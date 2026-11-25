# Deployment

| Target | What runs | Cost | Status |
|---|---|---|---|
| **Public demo** | One container: FastAPI serves the API and the built React app (lite profile), on **Render free** | ₹0 | ✅ Image built and tested; 🟡 public URL after the one-time Render setup below |
| Local, one command | `make demo` (SQLite, no services, no keys) | ₹0 | ✅ |
| Local full stack | `make up`: PostgreSQL, Redis, API, worker, nginx; `--profile observability` adds Prometheus, Grafana and Jaeger | ₹0 | ✅ |
| Azure pilot | AKS + PostgreSQL Flexible Server + Azure Cache for Redis + Key Vault in Central India (`deploy/k8s`, `deploy/terraform`) | Estimate below | 🔭 Design artefacts, validated with `helm lint`, `kubeconform` and `terraform validate`; never deployed |

## Public demo: free single container

**Image:** `deploy/huggingface/Dockerfile`.
- **Build:** a Node stage builds the React app; a Python stage generates the 500-factory lake and trains the
  demo model at build time.
- **Runtime:** the slim image runs as uid 1000 on port 7860.

**Lite profile:**
- SQLite in `/tmp`
- in-process cache, rate limits and job worker
- the template LLM writer (no keys)
- a fresh seed on every start
- `UP_FRAME_ANCESTORS=https://huggingface.co`, so the Space page can embed the app

**Measured locally** (Docker, 512 MB memory cap):

| Measure | Result |
|---|---|
| Container start to `/healthz` ready | **7 s** (the seed takes about 4 s) |
| Memory after the full demo story and the browser suite (20 tests at the time; 26 now) | **325 MB** of 512 MB |
| Browser suite (`E2E_BASE_URL=http://localhost:17860 npx playwright test`) | **20 / 20 passed** at the time of this run (the suite now has 26), both themes, axe checks included |
| Image size | 1.34 GB |

### Hosts and their free-tier limits (checked 18 Nov 2026)

| Host | Free tier | Fit | Caveats |
|---|---|---|---|
| **Render**, primary | Web service: 512 MB RAM, sleeps after 15 min idle (about 1 min to wake), 750 instance-hours a month | Fits: measured 325 MB peak with one worker | Cold start of about a minute, so open the link 10 min before presenting. Regions: no Indian region, so we use Singapore. Acceptable only because the demo holds synthetic data and no personal data. |
| **Hugging Face Spaces** (Docker SDK) | **Not free for Docker any more.** Verified on 18 Nov 2026: creating the Space returned *402 Payment Required: "hosting Gradio and Docker Spaces on free cpu-basic requires a PRO subscription"* | Would fit (16 GB) | Needs HF PRO; `deploy/huggingface/push.sh` still works for a PRO account |
| **Koyeb** (alternative) | One small free instance | Same image works | Check current limits before use |
| **Neon + Upstash** (fallback b) | Free PostgreSQL and Redis | Only if the SHOULD-tier full stack is deployed | Not needed for the demo |

Sources:
- [Hugging Face Spaces overview](https://huggingface.co/docs/hub/en/spaces-overview)
- [HF forum: Docker SDK marked as paid](https://discuss.huggingface.co/t/docker-sdk-now-marked-as-paid-when-creating-a-new-space/177580/5)
- [HF forum: CPU Basic quota](https://discuss.huggingface.co/t/question-about-the-cpu-basic-quota-limit/176628)
- [Render free tier article](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026)
- [Render pricing and spin-down summary](https://livemy.app/blog/render-pricing)

Check the providers' own pages again on the day of deployment; free tiers change.

### Publish to Render (one-time setup, about 10 minutes)

1. Sign in at render.com with the team's GitHub account (free, no card for the free instance type).
2. **New → Blueprint →** select `yugh88/UdyamPulse`, branch `main`. Render reads `render.yaml`: one free Docker
   web service built from `deploy/huggingface/Dockerfile`, health check `/healthz`. Press **Apply**.
3. Wait for the first build (about 10–15 minutes). The app is at `https://udyampulse-demo.onrender.com`, or the
   name Render assigns.
4. **CI/CD:** in the service's Settings, copy the **Deploy Hook** URL. In GitHub (Settings → Secrets and
   variables → Actions), add the secret `RENDER_DEPLOY_HOOK` and the variable `DEMO_HOST=render`. From then
   on, every push to `main` deploys once all CI jobs pass (the `deploy-demo` job).
5. Put the URL in the README (live demo link and badge) and on the deck's first slide.

### Publish to Hugging Face (PRO accounts only)

`HF_TOKEN=hf_xxx HF_SPACE=<user>/udyampulse bash deploy/huggingface/push.sh` assembles a clean build context
and uploads it; the app appears at `https://<user>-udyampulse.hf.space`.

### Demo-day checklist

- [ ] Open the live link **10 minutes before** presenting, to wake a sleeping instance (Render free sleeps after 15 minutes idle). `/healthz` answers
      within seconds once the container is up.
- [ ] Open the link (it enters as `rm1`, no sign-in) and check the hero, Sharma Auto Components, is in the queue. If a
      previous visitor changed the state, use **Reset demo data first** in the Guided demo panel.
- [ ] Backups: the recorded video (link in the README), `make demo` on a laptop, and the README screenshots.

## Security on the public demo

Demo personas only; synthetic data only; a "Prototype · synthetic data · not a lending decision" banner on
every screen; `noindex` (meta tag, header and `robots.txt`); rate limits on; no secrets and no outbound LLM
calls. See `docs/SECURITY.md`.

## Azure pilot (design, 🔭)

Central India, private networking, workload identity, Key Vault secrets, KEDA-scaled workers, immutable
audit-anchor storage; see `deploy/k8s/udyampulse/README.md` and `deploy/terraform/README.md`.

Monthly cost (**estimates**, approximate Azure list prices; check the Azure pricing calculator before committing):

| Setup | Basis | Approximate monthly cost |
|---|---|---|
| Pilot (one bank, about 5,000 accounts) | AKS 3 × D2s_v5, PostgreSQL Flexible D2ds_v5, Redis Standard C1, Key Vault, Storage, Log Analytics | about US$500 ≈ ₹42,000 |
| Production (10 lakh accounts) | AKS 3–6 × D4s_v5, PostgreSQL D4ds_v5 with zone-redundant HA, Redis Premium P1, the rest as above | about US$1,200–2,000 ≈ ₹1–1.7 lakh |

Rupee figures use about ₹84 per US$. These are planning estimates, not quotes.
