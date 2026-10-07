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
  // Theodore Music Lab — pre-generated neural voices for all 28 course languages.
  // Served from the `music` compose service; clips are disk-cached so /api/music/tts
  // replies instantly without re-rendering on every request.
  "music",
];

function serviceOrigin(name) {
  return process.env[`${name.toUpperCase()}_ORIGIN`] || `http://${name}:8000`;
}

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Production sets these at image build (see apps/web/Dockerfile). `next build`
    // freezes the rewrites, so a runtime env change does not retarget them.
    // Unset locally, the demos proxy to the labs on this machine.
    const studio = process.env.COURSE_STUDIO_ORIGIN || "http://127.0.0.1:8040";
    const childrenLab = process.env.CHILDREN_LAB_ORIGIN || "http://127.0.0.1:8018";
    const audioLab = process.env.AUDIO_LAB_ORIGIN || "http://127.0.0.1:8041";
    return [
      { source: "/studio", destination: `${studio}/studio` },
      { source: "/api/studio/:path*", destination: `${studio}/api/studio/:path*` },
      { source: "/api/live-audio/:path*", destination: `${studio}/api/live-audio/:path*` },
      { source: "/children-lab", destination: `${childrenLab}/lab` },
      { source: "/children-live-audio/:path*", destination: `${childrenLab}/:path*` },
      { source: "/static/:path*", destination: `${childrenLab}/static/:path*` },
      { source: "/api/child/:path*", destination: `${childrenLab}/api/child/:path*` },
      { source: "/api/tts", destination: `${childrenLab}/api/tts` },
      { source: "/api/tts/:path*", destination: `${childrenLab}/api/tts/:path*` },
      { source: "/vendor/vision/:path*", destination: `${childrenLab}/vendor/vision/:path*` },
      { source: "/audio-lab", destination: `${audioLab}/lab` },
      { source: "/audio-lab-api/:path*", destination: `${audioLab}/:path*` },
      ...SERVICES.map((name) => ({
        source: `/${name}/:path*`,
        destination: `${serviceOrigin(name)}/:path*`,
      })),
    ];
  },
};

export default nextConfig;
