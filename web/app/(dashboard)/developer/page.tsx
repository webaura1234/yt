import { Terminal } from "lucide-react";

import { PagePlaceholder } from "@/components/common/page-placeholder";

export default function DeveloperPage() {
  return (
    <PagePlaceholder
      icon={Terminal}
      title="Developer"
      description="Live logs, health checks, diagnostics, and manual pipeline execution."
      phase="Phase D"
    />
  );
}
