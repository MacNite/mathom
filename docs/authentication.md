# Authentication

Mathom is open, single-user software by default (`MATHOM_AUTH_ENABLED=false`): no accounts or archive scoping are applied. Set `MATHOM_AUTH_ENABLED=true` (or Compose's compatible `AUTH_ENABLED=true`) to enable Mathom-managed accounts.

## First start and local accounts

With authentication enabled and no users, the only available page is first-start onboarding. It creates one active `admin` with a normalized email and an Argon2id password hash (a scrypt compatibility fallback is used only in minimal source installs). There is no environment-variable administrator password. Local email/password login is available by default, even if no OIDC provider is configured; an admin can turn it off once Authentik works (see [Authentik-only sign-in](#authentik-only-sign-in)).

There are only two roles: `admin` and `user`. Admins create users, reset passwords, manage account state and configure Authentik. Users only access their own archive. The last active admin cannot be demoted, deactivated, or deleted; self-deletion is prevented. Password changes, resets, and deactivation revoke server-side sessions.

## Optional Authentik

Configure issuer, client ID and secret in **Admin / Sign-in** or the environment. The login screen then offers “Continue with Authentik” alongside local login. Existing databases retain their legacy OIDC `subject`; `owner` roles are migrated to `admin`.

### Setting up Authentik

1. Set `PUBLIC_BASE_URL` to the HTTPS origin users reach Mathom on (e.g. `https://mathom.example.com`). The redirect URI is built from it; without it Mathom guesses from the request, which behind a reverse proxy is often wrong. A *Public base URL* saved under **Admin / Sign-in** takes precedence — keep it filled in.
2. In Authentik, create an **OAuth2/OpenID Provider**: client type **Confidential**, redirect URI (mode **Strict**) exactly `<PUBLIC_BASE_URL>/api/auth/callback`, scopes `openid`, `email`, `profile`. Keep the default subject mode and do not change it later: Mathom links accounts by `sub`.
3. Create an **Application** for the provider (slug e.g. `mathom`) and, optionally, bind a group to restrict who may sign in.
4. Enter the issuer `https://<authentik-host>/application/o/<slug>/`, client ID and client secret under **Admin / Sign-in**. The Mathom container must be able to reach Authentik directly (token and userinfo calls are server-to-server).

### Linking existing accounts

OIDC identities are looked up by immutable subject. Email matching is permitted only when the provider marks the email verified and only for an unbound account; this prevents an unverified claim from taking over a privileged local account. If Authentik sends `email_verified: false` for an email that a local account already uses (including the admin created during onboarding), sign-in stops with an explanation instead of creating a duplicate.

To have Authentik assert verification, add a scope mapping (**Customization → Property Mappings → Scope Mapping**, scope name `email`) returning `{"email": request.user.email, "email_verified": True}` and use it instead of the default `email` mapping on the provider. Do this only if users cannot set arbitrary email addresses in Authentik. Check the result on the provider's **Preview** tab.

For recovery when every administrator has lost access, use a server-side SQLite maintenance procedure to set a known account active/admin and reset its password; never add a default password to deployment configuration.

## Authentik-only sign-in

Admins can turn off **Allow password sign-in** under **Admin / Sign-in**. While it is off:

- the login page offers only “Continue with Authentik”, and `POST /api/auth/login/local` is refused;
- invitations can be neither sent nor accepted; pending links are left intact and work again once password sign-in returns;
- admins add users without a password (they link on first Authentik sign-in by verified email), and password resets and changes are refused;
- stored password hashes are kept, so turning it back on restores existing passwords.

To keep anyone from locking themselves out, the switch can only be turned off while Authentik is configured and by an admin whose own account is already linked to Authentik (sign in with Authentik once first), and Authentik cannot be unconfigured while it is off. First-start onboarding always uses a password, since Authentik cannot be linked before an account exists.

`MATHOM_LOCAL_LOGIN_ENABLED` (Compose: `LOCAL_LOGIN_ENABLED`) overrides the switch and makes it read-only in the UI:

- unset (default) — the switch decides;
- `true` — password sign-in is always on. This is the break-glass path when Authentik is down or misconfigured: set it, restart, sign in with a password, then unset it again;
- `false` — password sign-in is always off.

## HTTP development or LAN access

Session cookies are `Secure` by default. When accessing Mathom over plain HTTP (for example `http://192.168.x.x:31313`), set `SESSION_COOKIE_SECURE=false` in Compose (or `MATHOM_SESSION_COOKIE_SECURE=false` outside Compose), restart Mathom, and use HTTPS again as soon as possible. Otherwise the browser correctly refuses the sign-in cookie. If onboarding reports that it is complete, the initial account was already created; after correcting the cookie setting, reload and sign in with the email and password entered during setup rather than attempting onboarding again.


## Email invitations

Admins can send local-account invitations from **Admin / Users**. Invitations bind a
pre-set email address and display name to a cryptographically random, single-use
registration link; the recipient chooses a password. Admins can see whether each
invitation is pending, expired, revoked, or accepted, and can revoke a pending
link. Links expire after `MATHOM_INVITE_EXPIRY_HOURS` (168 hours by default).

Configure SMTP in **Admin / Sign-in** or with `MATHOM_SMTP_HOST`,
`MATHOM_SMTP_PORT`, `MATHOM_SMTP_USERNAME`, `MATHOM_SMTP_PASSWORD`,
`MATHOM_SMTP_FROM_EMAIL`, `MATHOM_SMTP_FROM_NAME`, `MATHOM_SMTP_USE_TLS`, and
`MATHOM_PUBLIC_BASE_URL`. SMTP passwords are write-only in the UI. For Gmail,
use an app password and Gmail's authenticated/verified sending address. You
cannot make mail reliably appear from `admin@mathom.com` without control of
`mathom.com` (or provider-verified “send as” authorization): SPF/DKIM/DMARC
will otherwise cause rewriting, spam placement, or rejection.
