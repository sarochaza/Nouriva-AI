# Groq client access update

Observed user error: HTTP 403 with plain-text error code: 1010. Cloudflare documents 1010 as client/browser-signature blocking: https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/

The client now declares its real application identity as User-Agent NouraNutritionBenchmark/3.0, accepts JSON, safely classifies Cloudflare 1010 and provider permission codes without logging raw response bodies or keys, closes HTTP error responses, and stops real benchmark runs after a saved 401/403 failure. The image prompt, models, nutrients, database and averaging policy are unchanged.

Access after the client-identity change is NOT verified here. If the identified client is still blocked, contact Groq to investigate the block. No browser impersonation, proxy or security-setting bypass is included.

Apply this patch to the existing project folder. Then test one selected image:
$m = Get-Content '.\data\prepared\smoke-v3\manifest.json' -Raw | ConvertFrom-Json
.\.venv\Scripts\python.exe -m candidate.check --probe-image $m.images[0].image_path

Only after the vision probe succeeds, start a fresh run ID, for example smoke-real-v2. Existing frozen run IDs reject implementation changes. Keep the selected images/ground truth.

Offline verification: 4 new regression tests failed before implementation, then full 80/80 tests passed. Native Windows/live Groq validation still requires the local probe.
