import { TrendingUp } from "lucide-react";

import { PagePlaceholder } from "@/components/common/page-placeholder";

export default function TrendsPage() {
  return (
    <PagePlaceholder
      icon={TrendingUp}
      title="Trend discovery"
      description="Topic list scored by real usage/dedup history, with filtering - built honest against what actually exists today."
      phase="Phase F"
    />
  );
}
