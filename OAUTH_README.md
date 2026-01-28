# Notion OAuth Setup Guide

## Complete Guide to Extract Notion Calendar Data Using OAuth

---

## Step 1: Create Notion Public Integration

1. Visit: **https://www.notion.so/my-integrations**

2. Click **"+ New integration"**

3. Configure the integration:
   - **Name**: `BigQuery Calendar Sync` (or any name you prefer)
   - **Associated workspace**: `peerplay`
   - **Type**: **Public** (not Internal)
   - **Capabilities**: 
     - ✅ Read content
     - ❌ Update content (not needed)
     - ❌ Insert content (not needed)

4. Click **"Submit"**

5. After creation, configure OAuth settings:
   - Find **"OAuth Domain & URIs"** section
   - **Redirect URIs**: Add `http://localhost:8080/oauth/callback`
   - Click **"Save changes"**

6. **Copy these credentials** (you'll need them next):
   - **OAuth client ID**: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
   - **OAuth client secret**: `secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

---

## Step 2: Set Your OAuth Credentials

Choose **ONE** of these methods:

### Method A: Environment Variables (Recommended)
```bash
export NOTION_CLIENT_ID='your-client-id-here'
export NOTION_CLIENT_SECRET='your-client-secret-here'
```

### Method B: Edit the Script
Open `notion_oauth_flow.py` and replace:
```python
NOTION_CLIENT_ID = 'YOUR_CLIENT_ID_HERE'
NOTION_CLIENT_SECRET = 'YOUR_CLIENT_SECRET_HERE'
```

---

## Step 3: Run the OAuth Authorization Flow

```bash
cd /Users/matansade/Tools
python3 notion_oauth_flow.py
```

**What happens:**
1. Script opens your browser
2. You authorize the integration in Notion
3. Browser redirects to localhost
4. Script receives authorization code
5. Script exchanges code for access token
6. Token is saved to `notion_token.json`

---

## Step 4: Fetch and Upload Calendar Data

```bash
python3 fetch_notion_oauth.py
```

**What happens:**
1. Loads the access token from `notion_token.json`
2. Queries Notion database API (deterministic, gets ALL entries)
3. Filters for dates: 2026-01-01 to 2026-02-28
4. Uploads to BigQuery: `yotam-395120.peerplay.liveops_calendar_test_2`

---

## Verification

Check the uploaded data:
```bash
bq query --use_legacy_sql=false "SELECT COUNT(*) as total FROM \`yotam-395120.peerplay.liveops_calendar_test_2\`"
```

---

## Troubleshooting

### "OAuth credentials not set"
- Make sure you set the environment variables OR edited the script
- Verify you copied the full Client ID and Secret

### "Token file not found"
- Run `notion_oauth_flow.py` first before running `fetch_notion_oauth.py`

### "Error querying database: 401"
- The access token expired or is invalid
- Re-run `notion_oauth_flow.py` to get a new token

### "Error querying database: 404"
- The database ID might be wrong
- Make sure the integration has access to the Live-Ops Calendar database

---

## Files Created

- `notion_oauth_flow.py` - Handles OAuth authorization
- `fetch_notion_oauth.py` - Fetches data and uploads to BigQuery
- `notion_token.json` - Stores the access token (created after Step 3)
- `OAUTH_README.md` - This guide

---

## Security Notes

- Keep your OAuth credentials secure (treat like passwords)
- Don't commit `notion_token.json` to version control
- Access tokens are workspace-specific
- You can revoke access anytime at https://www.notion.so/my-integrations

---

## Why This Method is Better

✅ **Deterministic** - Gets 100% of entries (no search limitations)
✅ **Complete** - Uses official database query API with pagination
✅ **Reliable** - No missed entries like with semantic search
✅ **Reusable** - Can run again anytime to sync data

---

**Ready to start? Begin with Step 1 above!** 🚀
