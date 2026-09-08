# Setup

## eBay Developer Account

1. Sign up at [developer.ebay.com](https://developer.ebay.com)
2. Create an application — you need a **Production** keyset (App ID + Cert ID)
3. The Browse API uses client-credentials OAuth — no user login required

## Credentials file

Create `~/.ebay-mcp.toml` (the installer does this for you if migrating from `.env`):

```toml
env = "production"   # or "sandbox"

[production]
app_id  = "YourApp-PRD-..."
cert_id = "PRD-..."

[sandbox]
app_id  = "YourApp-SBX-..."
cert_id = "SBX-..."

dev_id = "..."   # optional, same across both envs
```

Lock it down: `chmod 600 ~/.ebay-mcp.toml`

Note: this server reads public listing data only and does not persist any eBay data.

## Environment variables

Env vars take precedence over the TOML file:

| Variable | Description |
|----------|-------------|
| `EBAY_ENV` | `production` or `sandbox` |
| `EBAY_PRD_APP_ID` | Production App ID |
| `EBAY_PRD_CERT_ID` | Production Cert ID |
| `EBAY_SBX_APP_ID` | Sandbox App ID |
| `EBAY_SBX_CERT_ID` | Sandbox Cert ID |
| `EBAY_DEV_ID` | Dev ID (optional) |

## Validate

```bash
ebay-mcp-config
```

Should print your masked creds and `OK — configuration is valid.`
