import os
import uuid
import base64
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
import stripe
from openai import OpenAI

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)
DB = DATA / "app.db"

PRICE_EUR = os.getenv("PRICE_EUR", "5.99")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gpt-image-2")
APP_URL = os.getenv("APP_URL", "http://localhost:8000").rstrip("/")
RETENTION_HOURS = int(os.getenv("RETENTION_HOURS", "24"))

stripe.api_key = STRIPE_SECRET_KEY

app = FastAPI(title="Future Me MVP")


def db():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        input_path TEXT NOT NULL,
        output_path TEXT,
        status TEXT NOT NULL,
        age_years INTEGER NOT NULL,
        stripe_session_id TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    con.commit()
    return con


def get_job(job_id: str):
    con = db()
    row = con.execute(
        "SELECT id,input_path,output_path,status,age_years,stripe_session_id FROM jobs WHERE id=?",
        (job_id,),
    ).fetchone()
    con.close()
    return row


def update_job(job_id: str, **fields):
    if not fields:
        return
    fields["updated_at"] = "CURRENT_TIMESTAMP"
    normal = {k: v for k, v in fields.items() if k != "updated_at"}
    sets = ", ".join(f"{k}=?" for k in normal)
    params = list(normal.values())
    sets += ", updated_at=CURRENT_TIMESTAMP"
    con = db()
    con.execute(f"UPDATE jobs SET {sets} WHERE id=?", (*params, job_id))
    con.commit()
    con.close()


INDEX_HTML = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Meet Your Future Self. See what you could look like 10, 20 or 30 years from now, powered by AI."><title>Future Me — Meet Your Future Self</title>
<style>
:root{font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#111;background:#f7f5f2}*{box-sizing:border-box}body{margin:0}.wrap{max-width:860px;margin:0 auto;padding:28px 18px 60px}.hero{text-align:center;padding:46px 0 28px}.eyebrow{font-size:13px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#6b6259}.hero h1{font-size:clamp(42px,9vw,76px);line-height:.95;letter-spacing:-.05em;margin:12px 0 18px}.hero p{font-size:clamp(17px,3vw,21px);line-height:1.45;max-width:620px;margin:0 auto;color:#625b55}.card{background:#fff;border:1px solid #e7e1db;border-radius:28px;padding:24px;box-shadow:0 18px 55px rgba(20,15,10,.08)}.examples{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:0 0 24px}.example{aspect-ratio:3/4;border-radius:18px;overflow:hidden;background:linear-gradient(145deg,#ded8d0,#f1ece6);display:flex;align-items:end;padding:14px;font-weight:700;color:#29231f}.example span{background:rgba(255,255,255,.85);padding:8px 10px;border-radius:10px}.drop{border:2px dashed #b9b0a8;border-radius:20px;padding:38px 18px;text-align:center;cursor:pointer;display:block;background:#fcfbfa}.drop strong{display:block;font-size:18px}.drop small{display:block;color:#777;margin-top:7px}.preview{max-width:100%;width:100%;max-height:520px;object-fit:contain;border-radius:18px;margin-top:18px;display:none;background:#eee}.age{display:flex;gap:10px;margin-top:18px}.age button{flex:1;border:1px solid #d9d1ca;background:#fff;color:#171311;border-radius:13px;padding:13px 8px;font-size:15px;font-weight:700;cursor:pointer}.age button.active{background:#111;color:#fff;border-color:#111}button.primary{width:100%;padding:17px;border:0;border-radius:14px;background:#111;color:#fff;font-size:17px;font-weight:800;cursor:pointer;margin-top:16px}button:disabled{opacity:.45;cursor:not-allowed}.muted{text-align:center;color:#746c65;font-size:13px;line-height:1.5;margin:12px 0 0}.status{text-align:center;margin:18px 0;font-weight:700;min-height:22px}.result-actions{display:flex;gap:10px;margin-top:12px}.result-actions a,.result-actions button{flex:1;display:none;text-align:center;padding:14px;border-radius:13px;text-decoration:none;font-weight:800;border:1px solid #d9d1ca;background:#fff;color:#111}.footer{text-align:center;margin-top:22px;color:#847b73;font-size:12px}.footer a{color:inherit}.consent{margin-top:14px;font-size:12px;color:#6d655e;line-height:1.45}.consent input{vertical-align:middle;margin-right:7px}.locked{filter:blur(10px);transform:scale(1.01);pointer-events:none}.hidden{display:none!important}
@media(max-width:620px){.examples{grid-template-columns:repeat(3,1fr)}.card{padding:18px;border-radius:22px}.age button{font-size:14px}.hero{padding-top:28px}}
</style></head><body><main class="wrap"><header class="hero"><div class="eyebrow">AI age progression</div><h1>Meet Your Future Self</h1><p>See what you could look like 10, 20 or 30 years from now — powered by AI.</p></header>
<section class="card"><div class="examples"><div class="example"><span>+10 years</span></div><div class="example"><span>+20 years</span></div><div class="example"><span>+30 years</span></div></div>
<label class="drop" id="drop"><input id="file" type="file" accept="image/jpeg,image/png,image/webp" hidden><strong id="dropText">📷 Choose a portrait photo</strong><small>Best results with a clear, front-facing portrait.</small></label>
<img id="preview" class="preview" alt="Selected portrait">
<div class="age" aria-label="Choose age progression"><button data-age="10">+10 years</button><button data-age="20" class="active">+20 years</button><button data-age="30">+30 years</button></div>
<button class="primary" id="buy" disabled>See My Future Self — €5.99</button>
<div class="consent"><label><input id="consent" type="checkbox"> I have the right to use this photo and agree to temporary processing to create my result.</label></div>
<p class="muted">One-time payment · No subscription · Secure checkout powered by Stripe</p><div id="status" class="status"></div>
<div id="resultWrap" class="hidden"><img id="result" class="preview" alt="Your future self"><div class="result-actions"><a id="download" download="future-you.png">Download</a><button id="share">Share</button></div><button class="primary" id="again">Try another photo</button></div>
</section><div class="footer"><a href="/privacy">Privacy</a> · <a href="/terms">Terms</a></div></main>
<script>
const file=document.getElementById('file'),drop=document.getElementById('drop'),dropText=document.getElementById('dropText'),preview=document.getElementById('preview'),buy=document.getElementById('buy'),consent=document.getElementById('consent'),status=document.getElementById('status'),result=document.getElementById('result'),resultWrap=document.getElementById('resultWrap'),download=document.getElementById('download'),share=document.getElementById('share'),again=document.getElementById('again');
let selected=null,age=20;
drop.onclick=()=>file.click();
file.onchange=()=>{selected=file.files[0]; if(!selected)return; if(!['image/jpeg','image/png','image/webp'].includes(selected.type)||selected.size>12*1024*1024){status.textContent='Please choose a JPG, PNG or WebP photo under 12 MB.'; selected=null; return;} preview.src=URL.createObjectURL(selected); preview.style.display='block'; dropText.textContent=selected.name; updateBuy();};
consent.onchange=updateBuy;
document.querySelectorAll('.age button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.age button').forEach(x=>x.classList.remove('active'));b.classList.add('active');age=Number(b.dataset.age);});
function updateBuy(){buy.disabled=!(selected&&consent.checked)}
buy.onclick=async()=>{buy.disabled=true;status.textContent='Opening secure checkout…';const fd=new FormData();fd.append('file',selected);try{const r=await fetch(`/api/create-checkout?age_years=${age}`,{method:'POST',body:fd});const x=await r.json();if(!r.ok)throw new Error(x.detail||'Could not start checkout.');location.href=x.checkout_url;}catch(e){status.textContent=e.message;updateBuy();}};
const q=new URLSearchParams(location.search),job=q.get('job'),sid=q.get('session_id');
async function poll(){if(!job||!sid)return;status.textContent='Payment confirmed. Creating your future self…';for(let i=0;i<48;i++){const r=await fetch(`/api/result/${job}?session_id=${encodeURIComponent(sid)}`);const x=await r.json();if(x.status==='ready'){result.src=x.image_url+'?t='+Date.now();result.style.display='block';resultWrap.classList.remove('hidden');download.href=x.image_url;download.style.display='block';share.style.display='block';status.textContent=`Your future self at +${x.age_years} years is ready.`;return;}if(x.status==='error'){status.textContent=x.message||'Generation failed. Please contact support.';return;}await new Promise(s=>setTimeout(s,2500));}status.textContent='This is taking longer than expected. Please refresh in a minute.'}
share.onclick=async()=>{try{if(navigator.share){await navigator.share({title:'My Future Self',text:'I just saw my future self with AI.',url:location.href});}else{await navigator.clipboard.writeText(location.href);status.textContent='Link copied.'}}catch(e){}};
again.onclick=()=>location.href='/';
poll();
</script></body></html>
'''

@app.get("/")
def index():
    return HTMLResponse(INDEX_HTML)


@app.get("/privacy")
def privacy():
    return HTMLResponse("""<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Privacy — Future Me</title><style>body{font-family:system-ui;max-width:760px;margin:40px auto;padding:0 20px;line-height:1.6}</style><h1>Privacy</h1><p>Future Me uses uploaded photos only to generate the purchased result. Source and generated files are stored temporarily and automatically deleted after the configured retention period. We do not use customer images for model training unless the customer separately opts in.</p><p>Payment is processed by Stripe. We do not receive or store full card details.</p><p>For support, contact the email address published on the production website.</p><p><a href='/'>Back</a></p>""")


@app.get("/terms")
def terms():
    return HTMLResponse("""<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Terms — Future Me</title><style>body{font-family:system-ui;max-width:760px;margin:40px auto;padding:0 20px;line-height:1.6}</style><h1>Terms</h1><p>Future Me provides AI-generated age-progression images for entertainment and creative purposes. Results are illustrative and are not predictions of a person's actual future appearance.</p><p>By uploading a photo, you confirm you have the right to provide it and consent to processing for the purchased service.</p><p><a href='/'>Back</a></p>""")


@app.post("/api/create-checkout")
async def create_checkout(file: UploadFile = File(...), age_years: int = 20):
    if age_years not in (10, 20, 30):
        raise HTTPException(400, "Invalid age option.")
    if not STRIPE_SECRET_KEY or not PRICE_ID:
        raise HTTPException(500, "Payments are not configured yet.")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(400, "Please upload a JPG, PNG, or WebP portrait.")
    content = await file.read()
    if len(content) > 12 * 1024 * 1024:
        raise HTTPException(400, "Image is too large. Maximum 12 MB.")
    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[file.content_type]
    job_id = uuid.uuid4().hex
    input_path = DATA / f"{job_id}{ext}"
    input_path.write_bytes(content)

    con = db()
    con.execute(
        "INSERT INTO jobs(id,input_path,status,age_years) VALUES(?,?,?,?)",
        (job_id, str(input_path), "waiting_payment", age_years),
    )
    con.commit()
    con.close()

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": PRICE_ID, "quantity": 1}],
            success_url=f"{APP_URL}/?paid=1&job={job_id}&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{APP_URL}/?canceled=1",
            metadata={"job_id": job_id, "age_years": str(age_years)},
            client_reference_id=job_id,
        )
    except Exception:
        input_path.unlink(missing_ok=True)
        con = db(); con.execute("DELETE FROM jobs WHERE id=?", (job_id,)); con.commit(); con.close()
        raise HTTPException(502, "Could not create checkout session.")

    update_job(job_id, stripe_session_id=session.id)
    return {"checkout_url": session.url, "job_id": job_id}


def generate(job):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    client = OpenAI(api_key=OPENAI_API_KEY)
    input_path = Path(job[1])
    age_years = int(job[4])
    prompt = (
        f"Edit the uploaded portrait into a realistic depiction of the same person approximately {age_years} years older. "
        "Preserve recognizable identity, facial structure, ethnicity, skin tone, hairstyle characteristics and gender. "
        "Apply believable age-related changes appropriate to the selected age progression, such as natural skin texture and wrinkles "
        "and gray hair where appropriate. Preserve expression, camera angle, framing, lighting, clothing context and background as much as possible. "
        "Photorealistic, respectful and natural. Do not create a generic replacement, beauty filter, cartoon, fantasy character, dramatic facial reshaping, "
        "text, logos, watermarks, medical devices or other unrelated additions."
    )
    with input_path.open("rb") as f:
        result = client.images.edit(
            model=IMAGE_MODEL,
            image=f,
            prompt=prompt,
            size="1024x1024",
        )
    data = base64.b64decode(result.data[0].b64_json)
    out = DATA / f"{job[0]}-future.png"
    out.write_bytes(data)
    update_job(job[0], output_path=str(out), status="ready")
    input_path.unlink(missing_ok=True)


@app.post("/api/stripe-webhook")
async def stripe_webhook(request: Request):
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(500, "Webhook is not configured.")
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(400, "Invalid webhook signature.")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        job_id = session.get("metadata", {}).get("job_id")
        if job_id:
            job = get_job(job_id)
            if job and session.get("payment_status") == "paid" and job[3] in {"waiting_payment", "payment_confirmed"}:
                update_job(job_id, status="payment_confirmed")
    return {"received": True}


@app.get("/api/result/{job_id}")
def result(job_id: str, session_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job[5] != session_id:
        raise HTTPException(403, "Invalid checkout session")

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        raise HTTPException(400, "Could not verify payment")
    if session.payment_status != "paid":
        return JSONResponse({"status": "waiting_payment"})

    if job[3] not in {"ready", "generating", "payment_confirmed"}:
        update_job(job_id, status="payment_confirmed")
        job = get_job(job_id)

    if job[3] != "ready":
        # Synchronous MVP generation; the webhook still records payment independently.
        update_job(job_id, status="generating")
        job = get_job(job_id)
        try:
            generate(job)
        except Exception as e:
            update_job(job_id, status="error")
            return JSONResponse({"status": "error", "message": "Generation failed. Please contact support."}, status_code=500)
        job = get_job(job_id)
    return {"status": "ready", "image_url": f"/api/image/{job_id}", "age_years": job[4]}


@app.get("/api/image/{job_id}")
def image(job_id: str):
    job = get_job(job_id)
    if not job or not job[2] or not Path(job[2]).exists() or job[3] != "ready":
        raise HTTPException(404, "Image not ready")
    return FileResponse(job[2], media_type="image/png", filename="future-you.png")
