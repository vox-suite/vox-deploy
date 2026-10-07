# Public domain cutover — 2026-10-06

## Final routing

| Hostname | Destination |
| --- | --- |
| `callvox.si` | Vox landing page on Vercel |
| `www.callvox.si` | 308 redirect to `callvox.si` |
| `voxagent.in`, `www.voxagent.in` | 308 redirect to `callvox.si`, preserving path and query |
| `callvox.in`, `www.callvox.in` | 308 redirect to `callvox.si`, preserving path and query |
| `api.callvox.in` | Existing Railway Caddy gateway, port 8080 |
| `app.callvox.si`, `admin.callvox.si` | Existing Vercel Vox Web project aliases |

The root-domain website redirect does not affect `api.callvox.in`, which has an explicit Railway CNAME in Vercel DNS. Both new apex domains use Vercel nameservers at Hostinger. The interim `api.callvox.si` Railway registration and its routing/verification DNS records were removed before any production service or Twilio callback used them.

## Active deployments

- Vercel project `vox-web`: `dpl_77iDC6eGToSJowbwxVfo2xfvoLUC`, observed Ready. Local source upload updates site metadata, sitemap, robots, and policy text.
- Bridge: `965fa7ca-ba11-4af4-ab13-b0f516e48702`, observed SUCCESS. Local source upload changes Twilio canonical HTTP/WebSocket URLs to `api.callvox.in`, with HMAC validation restricted to the configured Callvox callback URLs.
- Core API: `518932c7-4618-43fb-b424-a77fe7e3bbf2`, observed SUCCESS. Reuses the previously deployed `fd78708331952baefb1d3793dfc23a0a346c0771` build; sets `VOX_CORE_API_URL=https://api.callvox.in` and explicit new website CORS origins.
- Worker: `0f4e486f-6fec-4e73-9859-0c4e63dfdcc1`, observed SUCCESS. Reuses the same existing Core revision; sets `VOX_CORE_API_URL=https://api.callvox.in`.

Local migration edits have not been committed or pushed. Core's unrelated local work was not deployed. Desktop and Android source defaults, desktop `.env`, and Android `local.properties` now select `https://api.callvox.in`; distributed binaries have not been rebuilt or published. The retired API compatibility hostname is removed at the owner's request; installed clients must use the new hostname.

## Provider settings

The existing Twilio number now uses POST callbacks at:

- `https://api.callvox.in/bridge/twilio/voice`
- `https://api.callvox.in/bridge/twilio/voice/status`

Read-back confirmed both settings. Bridge emits `wss://api.callvox.in/bridge/twilio/voice/stream`. No live paid call was placed for verification.

The existing Google Web OAuth client now permits `https://api.callvox.in/v1/connectors/google/callback` with the previous callback and JavaScript origins removed. An unauthenticated Google authorization preflight found no redirect mismatch or invalid client error; this does not prove a completed Calendar authorization or refresh. Consent-screen home, privacy, and terms links select `callvox.si`; Google confirms the saved branding is verified and shown to users. Google Search Console verified `callvox.si` and `callvox.in` ownership on 2026-10-06 using a persistent DNS TXT record; The retired authorized domain has been removed. Security reporting and Google support/contact email settings use `rahul.id39@gmail.com`.

Supabase Authentication Site URL is now `https://callvox.si/`. Its redirect allowlist includes `https://callvox.si/**`, `https://app.callvox.si/**`, and `https://admin.callvox.si/**`, with existing native callbacks retained and retired website entries removed. The dashboard confirmed all five URLs and the saved Site URL.

## Verification evidence

- Website lint and production build passed.
- 32 targeted Bridge tests passed, including HMAC acceptance on the configured API origin and rejection of other hosts, changed paths, and wrong secrets.
- Standalone deployment script tests passed.
- API domain ownership verified and Railway certificate VALID.
- `https://api.callvox.in/health` returned 200 with `ok`.
- Protected API and unsigned Twilio webhook returned 401.
- Google callback without authorization parameters returned 400.
- Private gateway endpoint returned 404.
- CORS preflight permits `https://callvox.si`.
- HTTPS website content and sitemap checked at Vercel with certificate verification enabled; direct resolver overrides were needed while the local resolver retained an earlier negative cache.
- Both `.in` website redirects returned 308 and preserved path/query.

These checks establish routing, configuration, deployment, and selected request boundaries; they do not establish a completed real phone call, native login, or connector synchronization.

## Retired domain cleanup

At the owner's request, retired website aliases and redirects were removed from Vercel, the retired API custom domain was removed from Railway, and the explicit app/API CNAME and Railway verification TXT records were removed. The former website and API returned 404 after removal. Source and documentation searches found no remaining retired-domain strings outside Git history, generated build artifacts, and binaries. The Swiggy registration issue and GitHub repository homepage were updated. The retired Search Console property and its verification TXT record were removed; only the two Callvox properties remain.

Automatic approval review rejected removal of the entire former Vercel DNS zone because it contains Hostinger mail records. The old zone, mail-related records, and domain registration remain pending specific approval; mailboxes and their contents were not deleted. A recovery copy of DNS records is saved locally in `/private/tmp/retired-domain-dns-backup.txt`.

## Subsequent website redirect and DNS repair

The owner requested restoring the retired apex and www website redirects to `callvox.si`. Both Vercel mappings are verified and live with 308 path/query-preserving redirects. The earlier full DNS-zone removal request is superseded by this redirect requirement.

A later public DNS check found `callvox.si` delegated to `aster.dns-parking.com` and `helios.dns-parking.com`, resolving to Hostinger parking at `2.57.91.91`. Hostinger settings confirmed the parking delegation. On 2026-10-06, the nameservers were restored to `ns1.vercel-dns.com` and `ns2.vercel-dns.com`, with Hostinger confirming the successful save and warning of up to 24 hours for propagation. The Vercel landing deployment returned 200 over verified TLS using its address directly, and the API remained healthy. Public resolver propagation is separate from the saved registrar settings.
