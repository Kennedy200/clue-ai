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
