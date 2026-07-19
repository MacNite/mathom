# Authentication & User Management

Mathom ships as a single-user local archive. Multi-user mode with
[Authentik](https://goauthentik.io/) single sign-on is **optional and disabled
by default** — turn it on only when you want several people to keep separate,
private mathoms behind one install.

- **Off (default):** no login, no accounts. Every recording belongs to the one
  local keeper. Nothing about the original experience changes.
- **On:** everyone signs in through your Authentik server. Each person sees only
  their own Mathoms, chats, tags, and collections. MFA/2FA is handled entirely
  by Authentik.

## Roles

| Role      | Can do                                                                 |
| --------- | --------------------------------------------------------------------- |
| **Owner** | Everything an Admin can, plus change roles, delete users, and edit the Authentik connection settings. There must always be at least one active Owner. |
| **Admin** | View the user list and activate/deactivate regular users.             |
| **User**  | Use their own private mathom.                                    |

The **first person to sign in becomes the Owner** and adopts any recordings that
existed before user management was enabled (see *Backward compatibility*). To
pin ownership to a specific person regardless of sign-in order, set
`AUTH_OWNER_EMAIL` to their Authentik email.

## Set up Authentik

1. In Authentik, create an **OAuth2/OpenID Provider**:
   - **Client type:** Confidential
   - **Redirect URI:** `https://mathom.example.com/api/auth/callback`
     (use your real `PUBLIC_BASE_URL`)
   - **Scopes:** `openid`, `profile`, `email`
   - Note the generated **Client ID** and **Client Secret**.
2. Create an **Application** bound to that provider and give it a slug, e.g.
   `mathom`. The provider's **Issuer** URL then looks like
   `https://auth.example.com/application/o/mathom/`.
3. Assign the users/groups who should have access to the application.
4. (MFA) Configure MFA in Authentik as usual — Mathom never sees passwords or
   second factors; it only receives the verified identity after Authentik is
   satisfied.

## Configure Mathom

Set these in your `.env` (see `.env.example` for the full list):

```dotenv
AUTH_ENABLED=true
PUBLIC_BASE_URL=https://mathom.example.com
AUTHENTIK_ISSUER=https://auth.example.com/application/o/mathom/
AUTHENTIK_CLIENT_ID=<client id from Authentik>
AUTHENTIK_CLIENT_SECRET=<client secret from Authentik>
# Optional: force a specific Owner
AUTH_OWNER_EMAIL=you@example.com
```

Then `docker compose up -d`. Visit Mathom, sign in through Authentik, and you
become the Owner.

> **Chicken-and-egg:** the connection details must be provided via environment
> variables to get the first Owner signed in. After that, the Owner can adjust
> them in the UI under **Sign-in** without redeploying. The database copy, once
> saved, takes precedence over the environment values.

### Environment variables

| Variable                   | Default               | Purpose                                                        |
| -------------------------- | --------------------- | -------------------------------------------------------------- |
| `AUTH_ENABLED`             | `false`               | Master switch for user management + SSO.                       |
| `PUBLIC_BASE_URL`          | *(request origin)*    | Public origin, used to build the OAuth redirect URI.           |
| `SESSION_COOKIE_SECURE`    | `true`                | Send the session cookie only over HTTPS.                       |
| `SESSION_TTL_HOURS`        | `336` (14 days)       | Absolute session lifetime before re-login is required.         |
| `AUTH_OWNER_EMAIL`         | *(empty)*             | Email that becomes Owner; empty = first sign-in wins.          |
| `AUTHENTIK_ISSUER`         | *(empty)*             | OIDC provider/issuer URL.                                      |
| `AUTHENTIK_CLIENT_ID`      | *(empty)*             | OAuth client id.                                               |
| `AUTHENTIK_CLIENT_SECRET`  | *(empty)*             | OAuth client secret.                                           |
| `AUTHENTIK_SCOPES`         | `openid profile email`| Scopes requested at login.                                    |

All are consumed with the `MATHOM_` prefix inside the backend (e.g.
`MATHOM_AUTH_ENABLED`); the compose file maps the friendlier names above onto
them.

## How it works

- **Login** (`/api/auth/login`) redirects the browser to Authentik with a
  one-time `state`/`nonce`. Authentik authenticates the user (including MFA) and
  redirects back to `/api/auth/callback` with an authorization code.
- The backend exchanges the code for tokens (confidential client, server-side),
  fetches the userinfo claims, and finds or provisions the matching Mathom user.
- A random opaque session token is stored server-side and set as an
  **HttpOnly, SameSite=Lax, Secure** cookie. No tokens are exposed to JavaScript.
- Every data request is scoped to the signed-in user; one user can never read or
  address another user's Mathoms (unknown/owned-by-others ids return `404`).

## Backward compatibility

Enabling auth on an existing install is safe:

- Schema changes are additive. A nullable `user_id` column is added to
  `mathoms`, `tags`, and `collections`; existing rows keep `user_id = NULL`.
- On the **first Owner sign-in**, all pre-existing unowned rows are claimed by
  that Owner, so the archive appears exactly as before — now private to them.
- Turning auth back off (`AUTH_ENABLED=false`) restores the open single-user
  behaviour; the data is untouched.

## Troubleshooting

| Symptom                                   | Likely cause / fix                                                   |
| ----------------------------------------- | -------------------------------------------------------------------- |
| Login button says "not configured"        | Issuer/client id/secret missing. Set them in `.env` or the UI.       |
| `?auth_error=expired` after login         | The login took longer than 15 minutes, or the `state` was reused.    |
| `?auth_error=exchange_failed`             | Backend could not reach Authentik or the client secret is wrong.     |
| `?auth_error=not_provisioned`             | Auto-provisioning is off and no account exists for that identity.    |
| Redirected back to login immediately      | Cookie rejected — check `SESSION_COOKIE_SECURE` matches http/https.  |
| "Redirect URI mismatch" from Authentik    | The provider's redirect URI must equal `PUBLIC_BASE_URL` + `/api/auth/callback`. |
