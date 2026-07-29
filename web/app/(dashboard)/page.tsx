import { LayoutDashboard } from "lucide-react";

import { ApiConnectionBadge } from "@/components/common/api-connection-badge";
import { PagePlaceholder } from "@/components/common/page-placeholder";

export default function HomePage() {
  return (
    <div className="space-y-6">
      <div className="flex justify-center">
        <ApiConnectionBadge />
      </div>
      <PagePlaceholder
        icon={LayoutDashboard}
        title="Home overview"
        description="System health, generation stats, live pipeline status, and recent activity will live here."
        phase="Phase D"
      />
    </div>
  );
}
