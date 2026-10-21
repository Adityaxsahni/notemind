import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site";

// Public marketing and legal pages are indexable; everything behind sign-in and the API is not.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: ["/", "/features", "/privacy", "/terms", "/login", "/signup"],
      disallow: ["/courses", "/c/", "/account", "/join", "/insights", "/auth/", "/me", "/collections", "/invites", "/admin", "/analytics", "/telemetry"],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
