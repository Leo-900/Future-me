# Future Me — MVP

A paid, mobile-first AI age-progression web app.

## Current flow

Upload photo → choose +10/+20/+30 → pay €5.99 once → Stripe confirms payment → generate with OpenAI image editing → download/share result.

## Current implementation

- FastAPI backend
- OpenAI image editing; default model is `gpt-image-2` (the current OpenAI image-generation model)
- Stripe Checkout one-time payment
- Stripe webhook for payment confirmation
- SQLite job state
- Temporary local file storage for MVP
- Mobile-first frontend
- Privacy/Terms pages

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --reload
```

Fill in the environment variables first. For an actual payment test, create a Stripe one-time Price for €5.99 and set its Price ID in `STRIPE_PRICE_ID`. Use Stripe test mode first.

## Production before public launch

- Deploy behind HTTPS.
- Configure `APP_URL`.
- Add the Stripe webhook endpoint `/api/stripe-webhook` and set `STRIPE_WEBHOOK_SECRET`.
- Move temporary files from local disk to private object storage.
- Add automatic cleanup after `RETENTION_HOURS`.
- Add bot protection / stronger rate limiting.
- Publish real business identity, support email, privacy policy and terms.
- Test refunds, canceled checkout, failed generation and duplicate webhook delivery.

## Product test

Do not buy significant advertising before the full payment → generation → result loop works with real credentials. Then test a small amount of traffic and measure upload, checkout, payment, generation success, download and share rates.
