# Plugins

Everything optional is a plugin: `plugins/<kind>/<name>/manifest.json`, discovered at startup.

Kinds: `llm`, `tts`, `asset`, `payment`, `email`, `storage`, `publisher`, `caption_style`, `template`, `niche_pack`.

## manifest.json

| Field | Required | Meaning |
|---|---|---|
| `name` | yes | Folder name |
| `kind` | yes | Must equal the parent folder and be a known kind |
| `version` | yes | Semver |
| `title` | yes | Shown in the plugin manager |
| `description` | no | One line |
| `enabled_by_default` | no | Default `false` |
| `config` | no | List of `{key,label,type,default}`; types `text`, `number`, `secret`, `bool`. The admin UI builds the settings form from this |

Invalid manifests are listed with their error and never stop the app. See `plugins/email/smtp` for an example.

Phase status: discovery and listing work now. Loading plugin code and the enable/disable UI arrive with the features that use each kind.

## Shipped plugins

| Plugin | Kind | Default | What it adds |
|---|---|---|---|
| `tts/piper` | tts | off | 11 local neural voices: UK and US English, French, Spanish, Portuguese (BR), Arabic, Swahili. Each downloads once (about 60 MB). Piper is MIT; **each voice has its own licence**, so check its model card before commercial use. |
| `tts/edge` | tts | off | Online voices, including Nigerian English (`en-NG-AbeoNeural`, `en-NG-EzinneNeural`), Kenyan, South African, French, Spanish, Portuguese, Arabic. Needs internet and sends text to Microsoft's voice service through an unofficial client: personal and evaluation use only; use an Azure Speech plugin for commercial products. |
| `email/smtp` | email | off | Manifest only; sending is not implemented yet. |

Turn a plugin on or off as admin: `POST /api/admin/plugins/<kind>/<name>` with `{"enabled": true}`. The state is stored in the `settings` table under the manifest's `setting` key. Plugin voices appear in every voice picker with an id prefix (`piper:`, `edge:`).

To add a voice engine: implement `TTSProvider` (`voices()`, `synthesize()`) in `apps/api/clue/ai/tts.py`, register it in `Router`, add a manifest with a `setting`.

## Built-in integrations (not plugins yet)

- **YouTube publishing**: Admin > Integrations takes a Google OAuth client id and secret. Redirect URI to register in Google Cloud: `<SITE_URL>/api/youtube/callback`. Scope: `youtube.upload` only. Without it the calendar offers the publish pack.
- **Payment gateway**: `clue/core/billing.py` has a `Gateway` class with one method, `charge(user, amount, currency) -> bool`. Replace it to take real money; invoices, retries and renewals already sit on top of it.
