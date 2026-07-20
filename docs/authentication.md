# Authentication

Mathom is open, single-user software by default (`MATHOM_AUTH_ENABLED=false`): no accounts or archive scoping are applied. Set `MATHOM_AUTH_ENABLED=true` (or Compose's compatible `AUTH_ENABLED=true`) to enable Mathom-managed accounts.

## First start and local accounts

With authentication enabled and no users, the only available page is first-start onboarding. It creates one active `admin` with a normalized email and an Argon2id password hash (a scrypt compatibility fallback is used only in minimal source installs). There is no environment-variable administrator password. Local email/password login is always available, even if no OIDC provider is configured.

There are only two roles: `admin` and `user`. Admins create users, reset passwords, manage account state and configure Authentik. Users only access their own archive. The last active admin cannot be demoted, deactivated, or deleted; self-deletion is prevented. Password changes, resets, and deactivation revoke server-side sessions.

## Optional Authentik

Configure issuer, client ID and secret in **Admin / Sign-in** or the environment. The login screen then offers “Continue with Authentik” alongside local login. Existing databases retain their legacy OIDC `subject`; `owner` roles are migrated to `admin`.

OIDC identities are looked up by immutable subject. Email matching is permitted only when the provider marks the email verified and only for an unbound account; this prevents an unverified claim from taking over a privileged local account. For recovery when every administrator has lost access, use a server-side SQLite maintenance procedure to set a known account active/admin and reset its password; never add a default password to deployment configuration.

## HTTP development or LAN access

Session cookies are `Secure` by default. When accessing Mathom over plain HTTP (for example `http://192.168.x.x:31313`), set `SESSION_COOKIE_SECURE=false` in Compose (or `MATHOM_SESSION_COOKIE_SECURE=false` outside Compose), restart Mathom, and use HTTPS again as soon as possible. Otherwise the browser correctly refuses the sign-in cookie. If onboarding reports that it is complete, the initial account was already created; after correcting the cookie setting, reload and sign in with the email and password entered during setup rather than attempting onboarding again.
