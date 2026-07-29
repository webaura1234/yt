import { Settings } from "lucide-react";

import { PagePlaceholder } from "@/components/common/page-placeholder";

export default function SettingsPage() {
  return (
    <PagePlaceholder
      icon={Settings}
      title="Settings"
      description="API keys, LLM provider selection, TTS/voice defaults, rendering options, cache management, and scheduling."
      phase="Phase G"
    />
  );
}
