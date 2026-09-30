# Real sign-up / sign-in authentication

## Context

The backend design deliberately kept identity minimal: a `users` / `user_roles`
support model, a user-scope JWT, and out-of-band token minting via
`python -m voiceeval.auth.cli`. `docs/implementation_prompt.md` and the
architecture documents say **"do not build public signup"**.

The Resona frontend, however, needs an interactive way to obtain a user token;
the product owner explicitly requested proper sign-up and sign-in pages. This
decision records that deliberate change so the deviation is not silent.

## Decision

Add real credential authentication on top of the existing support tables.

- **Schema**: `users.password_hash` (nullable) via migration `0005`. Nullable so
  operator-provisioned accounts that never set a password remain valid.
- **Hashing**: standard-library `hashlib.scrypt` (`voiceeval.auth.passwords`),
  stored self-describing as `scrypt$<n>$<r>$<p>$<salt_hex>$<hash_hex>`.
  Verification is constant-time and returns `False` for malformed/absent hashes.
  No third-party dependency is added.
- **Service**: `AuthService` (`register`, `login`, `get_user`) + `UserRepository`.
  Registration validates the email shape and a minimum password length, rejects
  duplicates with `409` (`EMAIL_ALREADY_REGISTERED` / `USERNAME_ALREADY_TAKEN`),
  and grants the `user` role.
- **API**: `POST /api/v1/auth/register` (201), `POST /api/v1/auth/login` (200),
  `GET /api/v1/auth/me` (user scope). `register`/`login` are unauthenticated;
  together with the signed media blob they are the only unauthenticated HTTP
  surfaces.
- **Tokens**: login/registration mint the existing user-scope JWT (`sub=user.id`).

## Consequences

- The control plane now has a real identity model. The CLI remains for service
  accounts and automation; it is no longer the only way to get a token.
- Passwords are never logged or returned; only the hash is stored.
- Out of scope for v1 (documented, not implemented): email verification, password
  reset, refresh tokens, rate limiting, and account lockout. A production
  deployment should add these in front of `/auth/*`.
- The `/auth/me` endpoint trusts the JWT `sub`; a token for a deleted user yields
  a `404` from the user lookup rather than a session error.
