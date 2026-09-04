# JBS OmniVision — Engineering Architecture Reverse-Engineering & Competitive Build Guide

> Prepared as a combined Principal Architect / Distributed Systems / AI Infra / CV / DevOps / CTO review.
> Objective: reconstruct the likely engineering architecture and define a buildable competing Industrial CV SaaS.
> Split: ~80% engineering/architecture, ~20% business.

---

## 0. The one constraint that defines everything

Before any diagrams, internalize OmniVision's actual positioning, because it dictates 70% of the architecture:

**"Works with your *existing* CCTV. No new cameras."**

That single sentence forces these engineering realities, and you must design around them too if you compete here:

1. **You do not control the camera.** No guaranteed smart-camera SoC, no on-camera inference, no controllable codec/FPS/resolution. You inherit whatever H.264/H.265 RTSP stream the customer's NVR/DVR exposes (often via ONVIF). Inference cannot be pushed to the camera — it must run on a **site gateway** (edge box) or in the cloud.
2. **Ingestion is RTSP/ONVIF pull**, frequently behind NAT, on flaky LANs, with mixed vendors (Hikvision, Dahua, Axis, Uniview, Bosch). Discovery, credential management, and reconnection logic are first-class problems.
3. **Bandwidth is the enemy.** Sending raw video to the cloud at scale is economically impossible. → Edge-heavy inference, cloud-thin control plane. This is the central cost-driver and the central scaling decision.
4. **"Real-time AND historical"** (from their FAQ) means two pipelines: a low-latency live path and a clip/event archive with retrieval.
5. **Multi-site, multi-industry, enterprise** → multi-tenant control plane + fleet management of edge nodes.

Everything below follows from these five facts.

---

# Part 1 — Product Decomposition

Inferred from the published capabilities (PPE/fire/zone HSE, idle/bottleneck/throughput/counting productivity, facial recognition + LPR + intrusion security, real-time alerts, dashboards, enterprise integration, multi-site).

### Module map (likely service boundaries)

| Module | Responsibility | Key APIs | Data store | Primary scaling concern |
|---|---|---|---|---|
| **Camera/Device Management** | Register cameras, ONVIF discovery, credentials, RTSP URLs, health/heartbeat | `POST /cameras`, `GET /cameras/:id/health`, ONVIF probe | PostgreSQL (config) + Redis (live status) | Thousands of devices × heartbeat fan-in |
| **Edge/Gateway Management** | Fleet registry of edge nodes, OTA model + agent updates, remote config, telemetry | `POST /edge/register`, `GET /edge/:id/config`, model push | PostgreSQL + object store (artifacts) | OTA to 1000s of nodes, version skew |
| **Stream Management** | Own RTSP connections, decode, frame sampling, stream lifecycle | internal gRPC; `GET /streams/:id/state` | Redis (state), no durable video here | Decode CPU/GPU per stream; reconnect storms |
| **AI Model Management (Model Registry)** | Versioned models, per-camera model assignment, A/B, rollback | `POST /models`, `POST /cameras/:id/models` | Object store + Postgres metadata (or MLflow) | Artifact size, edge-compatible format matrix |
| **Inference Service** | Run detection/tracking/classification, emit detections | internal (in-process at edge) | none (transient) | GPU saturation, batching |
| **Event Engine (Rules)** | Turn detections → business events via rules/zones/temporal logic | `POST /rules`, `GET /events` | TimescaleDB/ClickHouse (events) | High write throughput, rule eval latency |
| **Alert Engine** | Dedup, severity, escalation, routing | `POST /alerts/ack`, webhooks | Postgres + Redis (dedup window) | Alert storms, dedup correctness |
| **Notification Service** | Deliver to email/SMS/WhatsApp/Slack/Teams/webhook | `POST /notify` | Queue + delivery log | Provider rate limits, retries |
| **Analytics Engine** | Aggregations: idle %, throughput, counts, compliance rate over time | `GET /analytics/...` | ClickHouse / TimescaleDB | Time-series rollups at scale |
| **Reporting Engine** | Scheduled/exported reports (PDF/CSV), compliance summaries | `POST /reports`, `GET /reports/:id` | Object store + Postgres | Heavy queries; isolate from OLTP |
| **Clip/Media Service** | Store event clips/snapshots, signed retrieval, retention | `GET /clips/:id` (presigned) | Object store (S3/MinIO) + metadata | Storage growth, lifecycle/TTL |
| **User/Org Management** | Auth, orgs, sites, invitations | `POST /auth`, `GET /me` | Postgres | Standard |
| **Multi-Tenant Management** | Tenant isolation, quotas, billing hooks | internal | Postgres | Noisy-neighbor, quota enforcement |
| **RBAC** | Roles, scoped permissions (org→site→area→camera) | `GET /permissions` | Postgres | Hierarchical scope checks |
| **Audit Log** | Immutable record of config + access changes | `GET /audit` | Append-only (ClickHouse/Postgres) | Write volume, immutability |
| **Dashboard/BFF** | Aggregate APIs for the SPA, live tiles, WebSocket fan-out | WS + REST/GraphQL | reads from above | WebSocket connection count |
| **Integration/Webhook** | Push to ERP/HSE/MES, inbound APIs | `POST /integrations` | Postgres | External system reliability |

**Boundary advice for a competitor:** do *not* build all of these as separate services on day one (see Part 9/11). The table is the *logical* decomposition; the *physical* deployment should be a modular monolith on the cloud side + one agent binary on the edge.

---

# Part 2 — Architecture Reverse Engineering

### High-level system diagram

```
                          CONTROL / SaaS PLANE (Cloud)
  Users (SPA / mobile)
        |
        v
  CDN  →  Frontend (Next.js — confirmed: jbs.live is Next.js)
        |
        v
  API Gateway  (auth, rate limit, tenant routing)   ── WebSocket gateway (live tiles/alerts)
        |
  ┌─────┴───────────────────────────────────────────────┐
  | App services: Camera/Edge mgmt, Rules, Alerts,       |
  | Analytics, Reporting, Model Registry, RBAC, Audit    |
  └─────┬───────────────┬───────────────┬────────────────┘
        |               |               |
   PostgreSQL      TimescaleDB/        Object store
   (config/RBAC)   ClickHouse          (S3/MinIO: clips,
                   (events/metrics)     models, reports)
        |               ^
        |               | events (Kafka/NATS)
        v               |
  Message bus  ─────────┘
        ^
        | (thin telemetry + events + clips up; config + models down)
========|=============================================================
        |                 DATA PLANE (per-site Edge)
        |
  Edge Gateway box (per factory/site)
   ┌──────────────────────────────────────────────┐
   | Stream Mgr → Decode (NVDEC) → Frame sampler →  |
   | Inference (TensorRT) → Tracker → Rule eval →   |
   | Event/clip generator → local buffer/store      |
   └──────────────────────────────────────────────┘
        ^
        | RTSP / ONVIF pull
  Existing cameras / NVR / DVR  (Hikvision, Dahua, Axis, …)
```

### Why this architecture is the likely (and right) one

- **Edge inference + cloud control** is the only model that survives the bandwidth math (Part 8). It also gives data-residency wins for enterprise/industrial buyers.
- **Next.js frontend** is confirmed from the site's static asset paths (`_next/static/...`). It strongly implies a **JS/TS frontend team** and a separate API backend.
- **Event-driven core**: CV produces a firehose of detections; a message bus + time-series DB is the standard, scalable shape.
- **Time-series store** for events/metrics because every analytic they advertise (idle %, throughput, counts, compliance rate) is fundamentally `count/aggregate over time, grouped by camera/zone`.

### Advantages
- Bandwidth + cost scale with *sites*, not with *cloud GPU* per camera.
- Works offline; site keeps detecting if WAN drops (critical for factories).
- Tenant data largely stays on-prem → easier enterprise security sign-off.

### Weaknesses / where it will hurt
- **Fleet management is now your hardest problem**, not CV. OTA, version skew, observability across heterogeneous boxes on customer networks you don't control.
- **Edge hardware capex** per site; you must right-size or margins evaporate.
- **Debugging is distributed**: a missed detection could be camera, network, decode, model, or rule. You need strong edge telemetry from day one.
- **Per-camera model assignment** explodes the config matrix (camera × model × zone × schedule).

---

# Part 3 — Video Processing Pipeline

Per-stage. Assume the unit of work is *one camera stream on one edge node*.

### 1. Camera → RTSP Stream
- **In:** ONVIF profile, RTSP URL, creds. **Out:** encoded H.264/H.265 packets.
- **Tech:** ONVIF discovery, RTSP/RTP, FFmpeg/GStreamer, `go2rtc` for normalization.
- **Bottleneck:** reconnects, vendor quirks, sub-stream vs main-stream choice.
- **Scaling:** prefer the camera's **sub-stream** (e.g., 720p) for detection to cut decode cost ~4×; pull main-stream only for evidence clips. Exponential-backoff reconnect; circuit-breaker per camera.

### 2. Stream Manager
- **In:** N RTSP sessions. **Out:** managed decode pipelines + health.
- **Tech:** GStreamer pipelines, or **NVIDIA DeepStream** (`nvstreammux` multiplexes many streams into one batched inference). 
- **Bottleneck:** connection state, thread/process model.
- **Scaling:** one process per K cameras; batch across cameras into the GPU.

### 3. Frame Extraction / Decode
- **In:** encoded packets. **Out:** decoded frames (ideally on GPU).
- **Tech:** **NVDEC hardware decode** (keep frames in GPU memory — avoid the PCIe round-trip), `nvv4l2decoder` in DeepStream.
- **Bottleneck:** decode is often the *real* limiter before inference, especially many 1080p/4K streams. NVDEC has fixed decode-session limits per GPU generation.
- **Scaling:** decode on sub-stream; cap decode sessions per GPU; spread cameras across nodes by decode budget, not just TOPS.

### 4. Frame Sampling
- **In:** 25–30 fps. **Out:** 3–10 fps (task-dependent).
- **Tech:** simple frame skip; adaptive sampling (motion-gated).
- **Bottleneck:** none if done right — this is your biggest cheap win.
- **Scaling:** **You almost never need full FPS.** PPE/zone/idle work fine at 3–5 fps. Counting/tracking may need 8–15 fps. Sampling is the single largest cost lever after sub-stream selection.

### 5. AI Inference
- **In:** sampled frames (batched). **Out:** detections (boxes, classes, conf, embeddings).
- **Tech:** **TensorRT** engines (FP16/INT8), Triton Inference Server or DeepStream `nvinfer`.
- **Bottleneck:** GPU compute & VRAM; model count per node.
- **Scaling:** INT8 quantization, dynamic batching across cameras, share one detector across cameras + lightweight per-use-case heads. Don't run a separate heavyweight model per use case on the same frame.

### 6. Object Tracking
- **In:** per-frame detections. **Out:** stable track IDs.
- **Tech:** **ByteTrack** (fast, no appearance model — great default), **BoT-SORT/DeepSORT** when you need re-ID across occlusion.
- **Bottleneck:** ID switches under occlusion; CPU for appearance embeddings.
- **Scaling:** ByteTrack on edge CPU is cheap; reserve appearance-based tracking for security/re-ID cameras only.

### 7. Event Rules
- **In:** tracks + zones + time. **Out:** business events ("worker in zone w/o helmet 3s").
- **Tech:** rule engine (zones as polygons, dwell timers, line-crossing, state machines), often a small embedded DSL/CEL.
- **Bottleneck:** temporal logic correctness; flicker/false positives.
- **Scaling:** evaluate at the edge; **temporal validation (N-of-M frames)** to suppress flicker. This is where most product quality lives.

### 8. Alert Engine
- **In:** events. **Out:** deduped, prioritized alerts.
- **Tech:** dedup windows (Redis), severity matrix, escalation policy.
- **Bottleneck:** alert storms (one fire = 50 alerts).
- **Scaling:** debounce + aggregate ("12 PPE violations on Line 3 in 5 min").

### 9. Storage
- **In:** events + clips/snapshots. **Out:** queryable history + evidence.
- **Tech:** events → ClickHouse/TimescaleDB; clips/snapshots → S3/MinIO with lifecycle TTL; metadata → Postgres.
- **Bottleneck:** clip storage growth; time-series cardinality.
- **Scaling:** store clips *only* for events, not continuously; presigned URLs; tiered retention (hot 7d / cold 90d / delete).

### 10. Dashboard
- **In:** aggregated events/metrics + live tiles. **Out:** UI, alerts, reports.
- **Tech:** Next.js + WebSocket for live, REST/GraphQL for history, WebRTC for live video view (not RTSP-in-browser).
- **Bottleneck:** WebSocket fan-out; live-video transcoding.
- **Scaling:** push only metadata over WS; transcode live video via WebRTC (e.g., `go2rtc`/MediaMTX) on demand, not always-on.

---

# Part 4 — Edge Computing Architecture

### What runs on the edge (everything latency- or bandwidth-sensitive)
Stream ingestion, decode, frame sampling, detection, tracking, rule evaluation, event + clip generation, local buffering. The cloud gets **events, thumbnails/clips, telemetry** — not raw video.

### Resource drivers
- **CPU:** RTSP handling, demux, tracking (ByteTrack), rule eval, orchestration. Decode if no NVDEC.
- **GPU:** detection/classification/segmentation/pose/embeddings. The dominant cost.
- **Memory (system + VRAM):** decoded frame buffers + model weights + batch tensors. VRAM is usually the per-node camera-count ceiling.
- **Storage:** local ring buffer for pre/post-event clips (e.g., 30–60s) + spool when WAN is down.

### Rules of thumb (sub-stream ~720p, 5 fps detection, YOLO-class detector, INT8/TensorRT)
- A modern edge GPU handles roughly **8–16 cameras per node** at this profile for a single detector with batching. Multi-model or higher FPS lowers this fast. **Always benchmark on your real streams** — decode sessions and codec (H.265 is heavier) move this number a lot.

### Hardware recommendations (current 2026 lineup)

> NVIDIA Jetson current family: Orin Nano (~67 TOPS, dev kit ~$249), Orin NX 8/16GB (117/157 TOPS), AGX Orin 32/64GB (200/275 TOPS), and the new **Jetson Thor T5000/T4000** (Blackwell, up to ~2070 FP4 TFLOPS, 128GB, 40–130W) for high-density edge. Decode: Thor handles up to ~4×8Kp30 / 10×4Kp60 in parallel.

| Tier | Cameras | Recommended edge | Rationale |
|---|---|---|---|
| **Small factory** | 10 | 1× **Jetson Orin NX 16GB** (or AGX Orin 32GB if multi-model) | Fanless, low power, ~10 cams at 720p/5fps single detector. Cheapest viable smart gateway. |
| **Medium factory** | 50 | 3–4× **Jetson AGX Orin 64GB**, *or* 1× small server w/ **1× NVIDIA L4** | L4 is the sweet spot for decode density + INT8 throughput in a 1U; Jetsons if you want fanless distributed. |
| **Large factory** | 200 | On-prem server(s): **2–4× NVIDIA L4 or L40S** + DeepStream/Triton, *or* a cluster of **Jetson Thor** nodes | Pool decode + batched inference; redundancy across boxes. ~50 cams/L4-class GPU at the standard profile (validate). |
| **Enterprise** | 1000+ | **Multiple sites**, each as "large factory" above + central fleet control. GPU server racks (L40S/RTX 6000 Ada) per large site | Never centralize 1000 streams. Scale by *site*; cloud is control plane only. |

**Cost note:** prefer **L4** over A100/H100 at the edge — L4 is built for high-density video inference at far lower $ and watt; data-center training GPUs are wasted on inference decode workloads.

---

# Part 5 — Multi-Tenant SaaS Architecture

### Hierarchy
```
Tenant (Org)
 └─ Site (factory/location)
     └─ Area (zone/line/floor)
         └─ Camera
             └─ Event
                 └─ Alert
```

### Core schema (PostgreSQL, control plane)

```sql
organizations(id, name, plan, status, created_at)
users(id, org_id, email, password_hash, status)
roles(id, org_id, name)                          -- system + custom
user_roles(user_id, role_id, scope_type, scope_id)  -- scope = org|site|area|camera
sites(id, org_id, name, timezone, address)
edge_nodes(id, site_id, hw_type, agent_version, status, last_heartbeat)
areas(id, site_id, name)
cameras(id, area_id, edge_node_id, rtsp_url, substream_url,
        onvif_profile, codec, resolution, fps, status)
zones(id, camera_id, name, polygon jsonb, type)   -- safety/count/intrusion
models(id, org_id?, task, framework, version, artifact_uri, formats jsonb)
camera_models(camera_id, model_id, config jsonb, enabled, schedule jsonb)
rules(id, org_id, name, definition jsonb, severity)
```

Time-series / high-volume (ClickHouse or TimescaleDB):
```sql
events(ts, org_id, site_id, area_id, camera_id, type, track_id,
       confidence, zone_id, payload jsonb, clip_uri)
metrics(ts, org_id, site_id, camera_id, metric, value)   -- rollups
alerts(id, org_id, event_id, severity, status, acked_by, acked_at)
audit_log(ts, org_id, actor_id, action, target, before, after)
```

### Entity relationships
- `org 1—N site 1—N area 1—N camera 1—N event 1—N alert`
- `camera N—N model` via `camera_models`
- `user N—N role` via `user_roles`, each grant **scoped** to a node in the hierarchy.

### Isolation strategy (pick by stage)
- **MVP:** **shared schema, `org_id` on every row + row-level security (RLS)** in Postgres. Lowest ops cost; enforce tenant scoping in one middleware + DB policy. This is the right starting point.
- **Growth:** **schema-per-tenant** for large/regulated enterprise customers who demand it; keep small tenants pooled.
- **Enterprise/regulated:** dedicated DB or even dedicated edge+cloud stack (single-tenant deployment). Industrial buyers often *require* this.
- Time-series store: partition by `org_id`/`site_id`; in ClickHouse, `org_id` as a leading key + TTL per tier.

### RBAC model
- Roles: `org_admin`, `site_manager`, `hse_officer`, `security_operator`, `viewer`, plus custom.
- Permission = `(action, resource_type)`; grant = `(role, scope_type, scope_id)`.
- A `site_manager` scoped to Site A sees only Site A's areas/cameras/events. Resolve scope by walking the hierarchy (cache the closure in Redis).

---

# Part 6 — AI Inference Architecture

> Model landscape note (current): **YOLO11** is the safe production default (proven, fast, great TensorRT/edge support). **YOLO26** (released Jan 2026) is NMS-free/end-to-end with notable CPU-inference gains and better small-object loss — strong forward choice. **RT-DETR/RF-DETR** (transformer) give higher accuracy at higher memory/latency — reserve for harder accuracy-critical tasks, not dense edge. Ultralytics currently does *not* recommend YOLO12/13 for production.

| Use case | Model choice | Training strategy | Deployment | Optimization |
|---|---|---|---|---|
| **Detection** (PPE, fire, person, vehicle, box/sack) | YOLO11/YOLO26 (n/s/m by node) | Fine-tune on domain data; heavy augmentation; class balancing | TensorRT INT8 on edge via DeepStream/Triton | INT8 PTQ + per-class conf thresholds |
| **Tracking** (workers, vehicles) | **ByteTrack** default; **BoT-SORT/DeepSORT** for re-ID | Tune detector first; tracker is mostly param tuning | On edge CPU, fed by detector | Motion-only (ByteTrack) unless re-ID needed |
| **Classification** (machine on/off, action/idle) | Lightweight CNN (MobileNet/EfficientNet) or temporal head | Train on cropped ROIs / short clips | TensorRT on edge | Crop-then-classify; small input size |
| **OCR** (license plate, gauges, labels) | Detector → **PaddleOCR / TrOCR**; ALPR via plate-detector + OCR | Fine-tune on regional plate fonts (PK plates differ) | Edge for plate detect, OCR edge or cloud | Region-crop before OCR; restrict charset |
| **Pose estimation** (ergonomics, fall, posture) | YOLO11-pose or RTMPose | Fine-tune keypoints; synthetic augmentation | Edge GPU | Run only on flagged tracks, not every frame |
| **Segmentation** (spill/leak area, occupancy mask, region) | YOLO11-seg; **SAM/SAM3** for offline auto-labeling only | Fine-tune small seg model; use SAM to bootstrap labels | Edge for small seg; SAM stays offline | Don't run SAM in real time — too heavy |
| **Re-identification** (cross-camera person/vehicle) | OSNet / TransReID embeddings + vector search | Train embedding on domain; gallery per site | Edge embedding → cloud/edge ANN (FAISS/Qdrant) | Trigger only on security cameras; cache gallery |
| **Anomaly detection** (intrusion, unusual motion, abandoned object) | Rule + temporal first; then autoencoder / memory-bank (PatchCore-style) for unsupervised | Train on "normal" footage per site (one-class) | Edge | Combine with rules to cut false positives |

### Worked examples (matching the prompt + OmniVision's advertised features)

- **PPE Detection (helmet/vest/gloves/goggles):** single multi-class YOLO detector → per-person association (which person lacks which PPE) → **temporal validation (e.g., violation persists ≥3s / N-of-M frames)** before alerting. Class imbalance (goggles/gloves are small + rare) is the main accuracy risk → targeted data collection + higher-res crops.
- **Worker tracking:** YOLO person + **ByteTrack**; switch to BoT-SORT where occlusion/re-entry matters (counting unique workers).
- **Vehicle tracking + LPR:** vehicle detect → ByteTrack → plate detect on best frame → OCR. Pick best frame by size/sharpness, not every frame. Localize OCR to **Pakistan plate formats**.
- **Fire/smoke detection:** detector + **strong temporal validation** (fire flickers; single-frame triggers are false-positive machines). Combine with color/motion priors.
- **Machine idle detection:** your own prior approach is the right one — **OpenCV frame-differencing / optical-flow motion analysis → state classifier (running/idle)** with hysteresis to avoid flapping. Avoid MediaPipe dependency churn; pure-CV idle detection is more stable for industrial scenes.
- **Counting (sack/box):** detection + line-crossing on track IDs (count on cross, not on presence) to avoid double counts; ByteTrack handles the IDs.

### Cross-cutting AI infra
- **One shared detector per frame**, multiple lightweight heads/classifiers downstream — never N heavy models on the same frame.
- **Model registry** with per-camera assignment + canary rollout + rollback.
- **Active learning loop:** auto-capture low-confidence/false-positive frames → label (CVAT) → retrain → redeploy. This loop is your real moat, not the model.

---

# Part 7 — Engineering Technology Selection

### Backend
| Option | Verdict | Why |
|---|---|---|
| **FastAPI (Python)** | ✅ **MVP control plane** | Same language as your CV/ML; fast to build; async OK. Your team already uses FastAPI. |
| Go | ✅ for **edge agent** + high-throughput ingest/event services | Single binary, low footprint, great concurrency — ideal for the edge gateway and stream/event hot path. |
| NestJS | ⚠️ only if backend team is TS-first | Fine, but splits language from ML. |
| Django | ❌ for this | Heavy, sync-first, ORM gets in the way of event throughput. |

**Recommendation:** FastAPI for the SaaS API + a **Go edge agent**. Push CV inference into a C++/Python DeepStream/Triton process the agent supervises.

### Frontend
- **Next.js** ✅ (matches OmniVision; SSR for marketing + app, mature ecosystem). React SPA is fine; Vue only if team preference. Use **WebRTC** for live video, **WebSocket** for live metadata/alerts.

### CV frameworks
- **Ultralytics** ✅ default (fastest path, great export to TensorRT/ONNX). 
- **TensorRT** ✅ mandatory for edge inference (INT8/FP16). 
- **DeepStream + Triton** ✅ for multi-stream batching at density.
- **MMDetection/Detectron2** — research/experimentation only; don't ship them to the edge.

### Streaming
- **RTSP/ONVIF** ✅ ingestion (you have no choice — it's what cameras speak).
- **WebRTC** ✅ for browser live view (low latency, NAT traversal).
- **HLS** ✅ for recorded/many-viewer playback.
- Use **MediaMTX/go2rtc** as the normalization layer between them.

### Messaging
| Option | Use it for |
|---|---|
| **NATS / NATS JetStream** | ✅ Edge↔cloud telemetry + commands; lightweight, great for fleet. |
| **Kafka** | ✅ Cloud-side event firehose / analytics ingestion at scale (Phase 2+). |
| **Redis Streams** | ✅ In-node/edge buffering, dedup windows, simple queues. |
| **RabbitMQ** | ⚠️ fine for task/notification queues; not for the event firehose. |

**Recommendation:** Redis Streams on edge, **NATS** for edge↔cloud, **Kafka** cloud-side once event volume justifies it.

### Databases
- **PostgreSQL** ✅ system of record (config, RBAC, tenancy) + RLS.
- **ClickHouse** ✅ events/analytics at scale (best $/write/query for this firehose). **TimescaleDB** ✅ acceptable alternative if you want to stay in Postgres early.
- **MongoDB** ❌ avoid as primary; not needed.
- Add **Redis** (state/cache/dedup) and a **vector DB (Qdrant/FAISS)** for re-ID.

### Object storage
- **MinIO** ✅ on-prem/edge + self-hosted cloud (S3-compatible, keeps data on-site). 
- **S3** ✅ managed cloud tier. 
- Single S3 API, two backends → clean abstraction. Lifecycle TTL is mandatory.

---

# Part 8 — Scalability Analysis

Assumptions: 720p sub-stream, ~5 fps detection, INT8 TensorRT, single shared detector, event-only clip storage.

### The bandwidth reality (why edge is non-negotiable)
- One 1080p H.264 stream ≈ **2–4 Mbps**. 
  - 100 cams ≈ 200–400 Mbps continuous to cloud — already painful.
  - 1,000 cams ≈ 2–4 Gbps — economically absurd.
  - 10,000 cams — physically/financially impossible to centralize.
- **Therefore inference is at the edge at every phase; cloud receives events + thumbnails + occasional clips** (kilobytes, not megabits).

### Phase 1 — 100 cameras (1–10 sites)
- **Compute/GPU:** ~7–12 edge GPUs total (≈8–16 cams each). e.g., a handful of AGX Orin / 1–2× L4 servers.
- **Storage:** event clips only ≈ tens of GB/day with TTL; thumbnails small.
- **Network:** edge→cloud event traffic ≈ low single-digit Mbps total.
- **DB:** single Postgres + single ClickHouse/Timescale node. 
- **Bottleneck:** getting detection quality + fleet onboarding right, not scale.

### Phase 2 — 1,000 cameras (10s of sites)
- **GPU:** ~60–120 edge GPUs across sites (L4-class servers per large site).
- **Storage:** clips into TB/month → tiered retention + lifecycle is now mandatory.
- **Network:** still modest *to cloud* (events), but **per-site LAN** must be planned (decode pulls full streams locally).
- **DB:** ClickHouse cluster (sharded by org/site); Postgres with read replicas; Kafka introduced for event ingestion.
- **Bottleneck:** **fleet management + OTA + observability** across heterogeneous edge boxes; event ingestion throughput; alert dedup correctness.

### Phase 3 — 10,000 cameras (100s of sites / large enterprise)
- **GPU:** hundreds of edge GPUs; possibly per-site mini-clusters with redundancy.
- **Storage:** petabyte-scale lifecycle; aggressive TTL + cold tiers; per-tenant quotas.
- **Network:** multi-region cloud; edge buffering for WAN partitions.
- **DB:** multi-shard ClickHouse, Kafka with partitioning by tenant, Postgres horizontally partitioned or Citus; per-tenant isolation for the largest accounts.
- **Bottleneck:** **operational** — provisioning, version skew, monitoring 10k camera-health signals, cost control, and support. CV is solved; *running the fleet* is the hard part.

### Persistent bottleneck ranking (in practice)
1. **Decode** (often before inference). 2. **GPU inference density.** 3. **Fleet ops/OTA.** 4. **Event ingestion + time-series query.** 5. **Clip storage cost.** 6. WebSocket/live-video fan-out.

---

# Part 9 — Fastest Development Strategy (3 engineers, 90-day MVP)

Team: 1 FE, 1 BE, 1 AI. The only way to hit 90 days is **buy/borrow everything that isn't your differentiator**, and your differentiator is **rules/events + the dashboard + onboarding**, not the CV plumbing.

### BUILD (your IP — keep it thin)
- The **event/rule engine** (zones, dwell, line-cross, temporal validation) — this *is* the product.
- The **multi-tenant control plane + dashboard** (Next.js + FastAPI).
- **Camera onboarding UX** (ONVIF discovery → assign models → draw zones). Onboarding friction kills CV deployments; make it your edge.
- The **edge agent** glue (supervises pipeline, telemetry, OTA hook) — thin Go/Python wrapper.

### OPEN SOURCE (reuse aggressively)
| Tool | Use for | Why |
|---|---|---|
| **Frigate** | Fastest path to RTSP→detect→event on edge for the MVP | Battle-tested CCTV NVR+detection; can prototype the whole edge path in days. (Outgrow it later.) |
| **NVIDIA DeepStream** | Multi-stream batched inference at density | When you need >10 cams/box. |
| **Ultralytics (YOLO11/26)** | Detection/seg/pose models | Train + export to TensorRT trivially. |
| **ByteTrack / BoT-SORT** | Tracking | Don't write a tracker. |
| **CVAT + FiftyOne** (+ optional Label Studio) | Annotation + dataset curation/active learning | CVAT to label, FiftyOne to debug/curate datasets. |
| **Keycloak** | Auth, RBAC, multi-tenant SSO | Don't build auth. Enterprise needs SSO/SAML anyway. |
| **MinIO** | Object storage (clips/models) | S3 API, self-host. |
| **MediaMTX / go2rtc** | RTSP↔WebRTC↔HLS bridging | Live view without pain. |
| **Triton** | Model serving (later) | When you outgrow in-process. |
| OpenVINO | Optional for Intel/CPU-only edge nodes | If a site can't take a GPU box. |

### BUY (don't self-host on day one)
- **Notifications:** email/SMS/WhatsApp via Twilio/SendGrid/Resend.
- **Error tracking + APM:** Sentry + a hosted Grafana/metrics stack.
- **Edge hardware:** Jetson dev kits / L4 boxes — don't design custom hardware.
- **Managed Postgres/Kafka** (cloud) initially; self-host later for margin.
- Optionally a **managed CV API** (e.g., Roboflow) to bootstrap a model before you have data.

### 90-day arc
- **Wk 1–3:** Frigate-based edge POC on real customer cameras; Next.js dashboard skeleton + Keycloak; Postgres schema + RLS.
- **Wk 4–7:** Your rule/event engine + zone editor; 2–3 flagship detections (PPE, intrusion, idle) fine-tuned; events → Timescale; alerts → notifications.
- **Wk 8–11:** Edge agent + OTA model push; clip capture/retrieval (MinIO); analytics tiles; one pilot site live.
- **Wk 12:** Harden, pilot feedback, demo. Outgrow Frigate into DeepStream only when density demands it.

---

# Part 10 — Production Architecture

### Kubernetes strategy
- **Cloud control plane on K8s** (managed: EKS/GKE/AKS). Stateless app services + HPA; Postgres/ClickHouse/Kafka managed or operator-run with care.
- **Edge: do NOT run full K8s on small boxes.** Use **k3s/KubeEdge** for managed sites, or just **Docker Compose + a supervised agent** for single-box sites. Most factories = one box = Compose is fine and far less ops.

### Docker strategy
- Everything containerized. Edge: pinned, signed images; the **inference container is GPU-specific** (CUDA/TensorRT version matrix) — maintain a build matrix per Jetson/GPU generation.

### CI/CD
- GitHub Actions/GitLab CI → build, test, scan, push to registry. 
- **Two release trains:** cloud (continuous) and **edge (staged/canary OTA)**. Edge updates are the risky ones — ring-based rollout (canary site → 10% → all), automatic rollback on health regression.
- **Model CD:** model registry → canary on a few cameras → metric check → fleet rollout.

### Monitoring
- **Prometheus + Grafana**; per-camera health, FPS, decode errors, inference latency, GPU util/VRAM, event rate, alert rate. 
- **Synthetic camera-down detection** is a core product signal, not just ops.

### Logging
- Structured logs → **Loki/ELK**; edge logs buffered locally and shipped when WAN is up. Correlate by `org/site/camera/track`.

### Security
- mTLS edge↔cloud; per-edge identity + short-lived certs; tenant isolation via RLS + scoped tokens; signed model/agent artifacts; network segmentation (cameras on isolated VLAN; edge box is the only thing talking out).
- Privacy: facial recognition + footage = **DPDP/GDPR-class obligations**; retention limits, access audit, consent posture, on-prem option for sensitive tenants.

### Secrets management
- **Vault** (or cloud KMS/Secrets Manager). Camera credentials are sensitive — never in plaintext config; sealed per edge node, rotated.

### Model deployment
- Registry (MLflow/custom) → versioned TensorRT artifacts per hardware target → canary → fleet, with rollback and per-camera assignment.

---

# Part 11 — CTO Review

### Risk register

**Overengineering risks**
- Microservices + Kafka + multi-cluster K8s on day one for an unproven product. → Start as a **modular monolith + managed infra**.
- Per-camera fully-independent model pipelines (config explosion). → Shared detector, lightweight heads.
- Running K8s on every edge box. → Compose/k3s by site size.

**Underengineering risks**
- No fleet/OTA story → you'll drown in manual edge updates by site #20.
- No temporal validation on detections → false-positive storms kill trust on day one.
- Treating CV accuracy as "done" without an active-learning/data loop → silent drift, churn.
- No tenant isolation/RLS from the start → painful to retrofit.

**Technical debt risks**
- Building on Frigate forever (it's a great MVP, a poor 1,000-camera core). Plan the DeepStream migration.
- Hardcoding one camera vendor's quirks. Abstract via ONVIF/go2rtc early.
- Schema without `org_id`/`site_id` everywhere → retrofit hell.

**Scaling risks**
- Centralizing video (bandwidth death). 
- Decode (not inference) being the hidden ceiling. 
- ClickHouse cardinality blowups from `track_id` in keys.

**Security risks**
- Facial recognition + footage = top regulatory/liability exposure. Make on-prem + retention controls first-class.
- Camera creds and edge boxes on customer networks = attack surface. mTLS + Vault + VLAN.

**Cost risks**
- Over-provisioned GPUs (using A100/H100 where L4 suffices).
- Clip storage with no TTL → unbounded S3 bill.
- Cloud egress if you ever stream video centrally.

---

### CTO recommendations

**1. Recommended MVP architecture**
Edge box per site (Frigate/Ultralytics + TensorRT) → events over NATS → FastAPI modular monolith → Postgres (RLS) + TimescaleDB → Next.js dashboard (WS + WebRTC) → Keycloak auth → MinIO clips. One pilot site, 3 flagship detections.

**2. Recommended production architecture**
Cloud control plane on managed K8s; ClickHouse (sharded) + Kafka for events; Postgres (replicas/Citus); per-site edge (DeepStream/Triton on L4/AGX Orin/Thor) with k3s for managed sites, Compose for single-box; OTA canary pipeline; Prometheus/Grafana/Loki; Vault; mTLS everywhere; single-tenant deployment option for regulated enterprise.

**3. Recommended tech stack**
Next.js + WebRTC/WS · FastAPI (API) + Go (edge agent, hot-path services) · Ultralytics YOLO11→YOLO26 + TensorRT + DeepStream/Triton · ByteTrack/BoT-SORT · Postgres+RLS / ClickHouse / Redis / Qdrant · NATS→Kafka · MinIO+S3 · Keycloak · Vault · Prometheus/Grafana/Loki · K8s(cloud)/k3s+Compose(edge).

**4. Recommended database design**
Postgres = system of record (config, tenancy, RBAC) with `org_id` + RLS on every table. ClickHouse/Timescale = events + metrics, partitioned by org/site, TTL-tiered. Object store = clips/snapshots/models with lifecycle. Redis = state/dedup. Qdrant = re-ID embeddings.

**5. Recommended AI pipeline**
Sub-stream → NVDEC decode → motion-gated frame sampling → shared TensorRT detector (batched across cameras) → ByteTrack → temporal-validated rule engine → deduped alerts → event/clip store. Active-learning loop (CVAT/FiftyOne) feeding retraining and canary model rollout.

**6. Recommended deployment model**
Edge-heavy / cloud-thin. Edge does all inference + rules; cloud is multi-tenant control plane + analytics + fleet management. Scale by *site*, never by centralizing streams. Offer on-prem/single-tenant for regulated buyers.

**7. Recommended development roadmap**
- **Days 0–90 (MVP):** Frigate-based edge, 3 detections, rule engine, dashboard, one pilot, Keycloak+RLS.
- **Months 3–6:** Edge agent + OTA, more detections, analytics, 5–10 paying sites, migrate hot path off Frigate where needed.
- **Months 6–12:** DeepStream/Triton density, ClickHouse cluster, fleet observability, SSO/SAML, single-tenant enterprise option, active-learning loop in production.
- **Year 2:** multi-region, 1,000+ cameras, marketplace of detection models, vertical packs (manufacturing/retail/logistics).

---

### The two things that actually decide whether you win
1. **Onboarding + fleet operations**, not model accuracy. Whoever makes "connect existing cameras and get value in an afternoon" the easiest wins this market.
2. **False-positive discipline** (temporal validation + good rules). Industrial buyers abandon CV products that cry wolf. Trustworthy alerts > more features.

*Models are commodity; the data loop, the rules, the onboarding, and the fleet ops are the moat.*
