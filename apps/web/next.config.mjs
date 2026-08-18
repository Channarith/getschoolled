/** @type {import('next').NextConfig} */

// Same-origin API routing handled BY THE WEB SERVER itself: the browser calls
// /identity/..., /curriculum/..., /orchestrator/..., etc. (see app/lib/api.ts),
// and these rewrites proxy each prefix to the matching backend service. This
// removes the dependency on a separately-configured edge gateway / ingress -
// the web container only needs network access to the services (always true in
// docker-compose and k8s), so account creation and every API call just work.
//
// Destinations default to the in-cluster/compose service DNS names on port 8000
// and are overridable per service via <NAME>_ORIGIN env (e.g. IDENTITY_ORIGIN).
const SERVICES = [
  "orchestrator",
  "curriculum",
  "memory",
  "identity",
  "billing",
  "integrations",
  "speech",
  "perception",
];

function serviceOrigin(name) {
  return process.env[`${name.toUpperCase()}_ORIGIN`] || `http://${name}:8000`;
}

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return SERVICES.map((name) => ({
      source: `/${name}/:path*`,
      destination: `${serviceOrigin(name)}/:path*`,
    }));
  },
};

export default nextConfig;
