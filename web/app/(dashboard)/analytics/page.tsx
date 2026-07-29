import { BarChart3 } from "lucide-react";

import { PagePlaceholder } from "@/components/common/page-placeholder";

export default function AnalyticsPage() {
  return (
    <PagePlaceholder
      icon={BarChart3}
      title="Analytics"
      description="Real generation history and timings now; views/CTR/watch-time/retention once a channel has published and accrued data."
      phase="Phase G"
    />
  );
}
