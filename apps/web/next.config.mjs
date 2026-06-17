/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The web app talks to the orchestrator; the base URL is the only thing that
  // changes between local (docker compose) and cloud (k8s ingress).
  env: {
    ORCHESTRATOR_URL: process.env.ORCHESTRATOR_URL || "http://localhost:8000",
    DEPLOY_MODE: process.env.DEPLOY_MODE || "local",
  },
};

export default nextConfig;
