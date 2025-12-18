# Gmail OAuth 2.0 Authentication Guide

Complete guide to setting up OAuth 2.0 authentication for accessing Gmail accounts.

## Overview

**Important:** For personal Gmail accounts, you use **OAuth 2.0** (NOT service accounts). Service accounts are only for Google Workspace domain-wide delegation.

### OAuth 2.0 Flow

1. **User Authorization** - User grants your app permission to access their Gmail
2. **Authorization Code** - Google returns a temporary authorization code
3. **Token Exchange** - Your app exchanges code for access and refresh tokens
4. **API Access** - Use access token to call Gmail API on user's behalf
5. **Token Refresh** - Automatically refresh expired access tokens

## Prerequisites

- Google Account (free Gmail account works)
- Gmail account you want to access
- 15-30 minutes for setup

## Step-by-Step Setup

### Step 1: Create Google Cloud Project

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com/
   - Sign in with your Google account

2. **Create a new project**
   - Click "Select a project" dropdown at the top
   - Click "NEW PROJECT"
   - Project name: `gmail-processor` (or any name you prefer)
   - Organization: Leave as "No organization" (for personal use)
   - Click "CREATE"

3. **Wait for project creation**
   - You'll see a notification when ready
   - Select your new project from the dropdown

### Step 2: Enable Gmail API

1. **Navigate to APIs & Services**
   - Left sidebar → "APIs & Services" → "Library"
   - Or visit: https://console.cloud.google.com/apis/library

2. **Search for Gmail API**
   - Search bar: type "Gmail API"
   - Click on "Gmail API" from results

3. **Enable the API**
   - Click "ENABLE" button
   - Wait for activation (5-10 seconds)

### Step 3: Configure OAuth Consent Screen

1. **Go to OAuth consent screen**
   - Left sidebar → "APIs & Services" → "OAuth consent screen"
   - Or visit: https://console.cloud.google.com/apis/credentials/consent

2. **Choose user type**
   - Select "External" (allows any Google account)
   - Click "CREATE"

3. **Fill out App information**

   **App Information:**
   - App name: `Gmail Email Processor`
   - User support email: Your email address
   - App logo: (Optional, can skip)

   **App Domain:**
   - Application home page: `http://localhost:8000` (for development)
   - Application privacy policy: (Optional for testing)
   - Application terms of service: (Optional for testing)

   **Authorized domains:**
   - Leave empty for local development
   - For production, add your domain (e.g., `yourdomain.com`)

   **Developer contact information:**
   - Email addresses: Your email address

   Click "SAVE AND CONTINUE"

4. **Configure Scopes**

   Click "ADD OR REMOVE SCOPES"

   **Required Scopes:**
   - `https://www.googleapis.com/auth/gmail.readonly` - Read all emails
     - Description: "See, edit, create, and delete all of your Gmail"
     - **Note:** Despite the description, `.readonly` only allows reading

   **Recommended Additional Scopes (optional):**
   - `https://www.googleapis.com/auth/gmail.labels` - Access labels
   - `https://www.googleapis.com/auth/userinfo.email` - Get user email address

   Click "UPDATE"
   Click "SAVE AND CONTINUE"

5. **Add test users** (Required for External apps in testing mode)

   Click "ADD USERS"
   - Enter the Gmail address you want to access
   - You can add up to 100 test users
   - Click "ADD"

   Click "SAVE AND CONTINUE"

6. **Review summary**
   - Review your settings
   - Click "BACK TO DASHBOARD"

### Step 4: Create OAuth 2.0 Credentials

1. **Go to Credentials**
   - Left sidebar → "APIs & Services" → "Credentials"
   - Or visit: https://console.cloud.google.com/apis/credentials

2. **Create OAuth client ID**
   - Click "CREATE CREDENTIALS" at the top
   - Select "OAuth client ID"

3. **Configure OAuth client**

   **Application type:** Select "Web application"

   **Name:** `Gmail Processor Client`

   **Authorized JavaScript origins:**
   - Click "ADD URI"
   - Enter: `http://localhost:8000`

   **Authorized redirect URIs:**
   - Click "ADD URI"
   - Enter: `http://localhost:8000/auth/callback`
   - **CRITICAL:** This must match exactly with your app's redirect URI

   Click "CREATE"

4. **Download credentials**

   A popup will show your credentials:
   - **Client ID:** `1234567890-abcdefghijk.apps.googleusercontent.com`
   - **Client Secret:** `GOCSPX-xyz123abc456def789`

   **Important:**
   - Click "DOWNLOAD JSON" to save credentials
   - Or copy the Client ID and Client Secret to a secure location
   - You'll need these for your `.env` file

   Click "OK"

### Step 5: Configure Your Application

1. **Update `.env` file**

   ```bash
   GMAIL_CLIENT_ID=1234567890-abcdefghijk.apps.googleusercontent.com
   GMAIL_CLIENT_SECRET=GOCSPX-xyz123abc456def789
   GMAIL_REDIRECT_URI=http://localhost:8000/auth/callback
   ```

2. **Generate encryption keys**

   For storing OAuth tokens securely:

   ```bash
   # Generate Fernet encryption key
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   # Output: xyzABC123...

   # Generate Flask secret key
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   # Output: abc123XYZ...
   ```

   Add to `.env`:
   ```bash
   TOKEN_ENCRYPTION_KEY=xyzABC123...
   SECRET_KEY=abc123XYZ...
   ```

### Step 6: Authorize Your Application

1. **Start your application**

   ```bash
   # Docker
   docker-compose up -d

   # Local
   python -m src.api.main
   ```

2. **Initiate OAuth flow**

   Visit in your browser: `http://localhost:8000/auth/login`

3. **Google OAuth consent screen**

   You'll be redirected to Google. You'll see:

   - "Google hasn't verified this app" warning (expected for testing)
   - Click "Advanced"
   - Click "Go to Gmail Email Processor (unsafe)"
     - It's safe - it's your own app!

4. **Grant permissions**

   - Sign in with the Gmail account you added as a test user
   - Review the requested permissions
   - Click "Allow"

5. **Authorization complete**

   You'll be redirected to: `http://localhost:8000/auth/callback`

   The app will:
   - Exchange authorization code for tokens
   - Encrypt and store tokens in database
   - Display: `✅ Authorization successful!`

6. **Verify token storage**

   ```bash
   # Docker
   docker-compose exec api python -m src.auth.verify_token

   # Local
   python -m src.auth.verify_token
   ```

   Expected output:
   ```
   ✅ OAuth token found for user: your.email@gmail.com
   ✅ Token is valid
   ✅ Token expires: 2025-12-17 11:30:00
   ```

## OAuth Scopes Explained

### Read-Only Access (Recommended)

```
https://www.googleapis.com/auth/gmail.readonly
```

**Allows:**
- Search for emails
- Read email content (subject, body, attachments)
- List messages and threads
- Get email metadata
- Access labels

**Does NOT allow:**
- Sending emails
- Deleting emails
- Modifying emails
- Creating labels

### Full Gmail Access (Use with caution)

```
https://www.googleapis.com/auth/gmail.modify
```

Allows read + modify (mark as read, add labels, delete)

```
https://www.googleapis.com/auth/gmail.compose
```

Allows composing and sending emails

**For this email processor, `.readonly` is sufficient and more secure.**

## Token Management

### Token Lifecycle

1. **Access Token**
   - Expires: 1 hour after issuance
   - Used for API calls
   - Automatically refreshed by the app

2. **Refresh Token**
   - Long-lived (months to years)
   - Used to obtain new access tokens
   - Stored encrypted in database
   - Only expires if:
     - User revokes access
     - Token unused for 6 months (for External apps)
     - User changes password (in some cases)

### Automatic Token Refresh

The application automatically refreshes expired access tokens using the refresh token. No user interaction needed.

**How it works:**
1. API call fails with 401 Unauthorized
2. App detects token expiration
3. App uses refresh token to get new access token
4. App retries original API call
5. New access token stored (encrypted)

### Manual Token Refresh

```bash
# Docker
docker-compose exec api python -m src.auth.refresh_token

# Local
python -m src.auth.refresh_token
```

### Revoke Access

**User revokes access:**
1. Go to: https://myaccount.google.com/permissions
2. Find "Gmail Email Processor"
3. Click "Remove Access"

**App revokes access:**
```bash
docker-compose exec api python -m src.auth.revoke_token
```

## Security Best Practices

### 1. Protect Your Credentials

**Never commit to Git:**
```bash
# Add to .gitignore
.env
credentials.json
token.json
*.db
```

**Store securely:**
- Use environment variables (`.env` file)
- Use secrets management in production (AWS Secrets Manager, Vault)
- Never hardcode in source code

### 2. Encrypt OAuth Tokens

All OAuth tokens are encrypted before storing in the database using Fernet encryption.

```python
from cryptography.fernet import Fernet

# Key generation (one-time)
key = Fernet.generate_key()

# Encryption
cipher = Fernet(key)
encrypted_token = cipher.encrypt(token.encode())

# Decryption
decrypted_token = cipher.decrypt(encrypted_token).decode()
```

### 3. Use HTTPS in Production

For production deployments:

```bash
GMAIL_REDIRECT_URI=https://yourdomain.com/auth/callback
```

Update in Google Cloud Console:
- Authorized JavaScript origins: `https://yourdomain.com`
- Authorized redirect URIs: `https://yourdomain.com/auth/callback`

### 4. Minimize Scope Permissions

Only request the minimum scopes needed:
- For read-only processing: `gmail.readonly`
- Avoid `gmail.modify` or `gmail.compose` unless required

### 5. Monitor Token Usage

Log all OAuth events:
- Authorization grants
- Token refreshes
- API call failures
- Revocations

## Multi-User Support

To support multiple Gmail accounts (multi-tenant):

### Database Schema

```sql
CREATE TABLE oauth_tokens (
    user_id VARCHAR(255) PRIMARY KEY,  -- Email address
    encrypted_access_token TEXT NOT NULL,
    encrypted_refresh_token TEXT NOT NULL,
    token_expiry TIMESTAMP NOT NULL,
    scopes TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### User Isolation

Each user's jobs and emails are isolated:

```sql
-- Fetch jobs per user
SELECT * FROM fetch_jobs WHERE user_id = 'user@gmail.com';

-- Email metadata per user
SELECT * FROM email_metadata em
JOIN fetch_jobs fj ON em.fetch_job_id = fj.id
WHERE fj.user_id = 'user@gmail.com';
```

### Authorization Flow

1. Each user visits: `http://localhost:8000/auth/login?user_id=user@gmail.com`
2. After authorization, tokens stored with `user_id`
3. Workers fetch emails using the correct user's tokens

## Troubleshooting

### "Access Blocked: This app's request is invalid"

**Problem:** Redirect URI mismatch

**Solution:**
- Ensure `.env` `GMAIL_REDIRECT_URI` exactly matches Google Console
- Common mistake: `http://localhost:8000/callback` vs `http://localhost:8000/auth/callback`
- Update Google Cloud Console or `.env` to match

### "Error 400: redirect_uri_mismatch"

**Problem:** Same as above

**Solution:**
- Check Google Cloud Console → Credentials → OAuth 2.0 Client IDs
- Verify "Authorized redirect URIs"
- Must match exactly (including http/https, port, path)

### "This app isn't verified"

**Problem:** Normal for apps in testing mode

**Solution:**
- Click "Advanced"
- Click "Go to [Your App Name] (unsafe)"
- This is safe for your own app
- To remove warning: Complete Google's verification process (for public apps)

### "Access Denied: Gmail Email Processor has not completed the Google verification process"

**Problem:** User not added as test user

**Solution:**
- Go to: https://console.cloud.google.com/apis/credentials/consent
- Click "OAuth consent screen"
- Under "Test users", add the Gmail address
- Re-attempt authorization

### "invalid_grant" Error

**Problem:** Refresh token expired or revoked

**Solution:**
- User re-authorizes: `http://localhost:8000/auth/login`
- New tokens will be issued

### "Quota exceeded" (HTTP 429)

**Problem:** Gmail API rate limits

**Solution:**
- Free tier: 1 billion quota units/day
- Each API call: ~5-10 units
- Typical limit: ~250,000 API calls/day
- To increase: Enable billing in Google Cloud Console
- Implement exponential backoff in your app

## Comparison: OAuth vs Service Accounts

| Feature | OAuth 2.0 | Service Account |
|---------|-----------|-----------------|
| **Use Case** | Personal Gmail | Google Workspace domains |
| **User Consent** | Required per user | Domain-wide delegation |
| **Best For** | SaaS apps, personal projects | Internal company tools |
| **Setup** | Simpler | Requires Workspace admin |
| **Token Storage** | Per user | Single service account |
| **Example** | Mailchimp, Superhuman | Company email archival |

**For this project (personal Gmail), OAuth 2.0 is the correct choice.**

## Service Account Setup (Google Workspace Only)

**Note:** This section only applies if you're accessing Google Workspace accounts (company emails like `user@company.com`) and you're a Workspace admin.

### Prerequisites
- Google Workspace domain
- Super Admin access

### Steps

1. **Create service account**
   - Google Cloud Console → IAM & Admin → Service Accounts
   - CREATE SERVICE ACCOUNT
   - Name: `gmail-service-account`
   - CREATE AND CONTINUE
   - Skip roles → DONE

2. **Enable domain-wide delegation**
   - Click on the service account
   - SHOW ADVANCED SETTINGS
   - Enable "Enable G Suite Domain-wide Delegation"
   - Save

3. **Download key file**
   - KEYS tab → ADD KEY → Create new key
   - JSON format
   - Save as `service-account-key.json`

4. **Authorize in Workspace Admin**
   - Go to: https://admin.google.com/
   - Security → API Controls → Domain-wide Delegation
   - ADD NEW
   - Client ID: From service account key file
   - OAuth scopes: `https://www.googleapis.com/auth/gmail.readonly`
   - AUTHORIZE

5. **Use in application**
   ```python
   from google.oauth2 import service_account

   credentials = service_account.Credentials.from_service_account_file(
       'service-account-key.json',
       scopes=['https://www.googleapis.com/auth/gmail.readonly'],
       subject='user@company.com'  # Impersonate this user
   )
   ```

**For personal Gmail: Do NOT use service accounts. Use OAuth 2.0 instead.**

## Production Checklist

Before deploying to production:

- [ ] OAuth consent screen completed
- [ ] App verification submitted (if public app)
- [ ] HTTPS enabled
- [ ] Redirect URI uses production domain
- [ ] Client secrets stored in secrets manager
- [ ] Token encryption key rotated and secured
- [ ] Database backups configured
- [ ] Token refresh logging enabled
- [ ] Rate limiting implemented
- [ ] User notification for authorization expiry
- [ ] Privacy policy and terms of service published
- [ ] GDPR/privacy compliance reviewed

## Additional Resources

- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [OAuth 2.0 Overview](https://developers.google.com/identity/protocols/oauth2)
- [Gmail API Python Quickstart](https://developers.google.com/gmail/api/quickstart/python)
- [Google API Scopes](https://developers.google.com/identity/protocols/oauth2/scopes)
- [Google OAuth Playground](https://developers.google.com/oauthplayground/) - Test API calls
