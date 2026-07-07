// Clerk remains the identity provider; Convex verifies the Clerk-issued JWT
// ("convex" template) instead of the Python backend verifying JWKS itself.
//
// Setup (once per Clerk instance):
//   1. Clerk dashboard -> JWT templates -> New template -> Convex.
//   2. Copy the template's Issuer URL (https://<instance>.clerk.accounts.dev).
//   3. `npx convex env set CLERK_JWT_ISSUER_DOMAIN <issuer url>` per deployment.
const authConfig = {
  providers: [
    {
      domain: process.env.CLERK_JWT_ISSUER_DOMAIN,
      applicationID: "convex",
    },
  ],
};

export default authConfig;
