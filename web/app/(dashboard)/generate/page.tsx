import { Sparkles } from "lucide-react";

import { PagePlaceholder } from "@/components/common/page-placeholder";

export default function GeneratePage() {
  return (
    <PagePlaceholder
      icon={Sparkles}
      title="Content generation"
      description="Topic input, AI title suggestions, script preview/editing, voice selection, live render progress, and final video preview."
      phase="Phase E"
    />
  );
}
