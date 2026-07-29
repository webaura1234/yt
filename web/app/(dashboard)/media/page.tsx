import { FolderOpen } from "lucide-react";

import { PagePlaceholder } from "@/components/common/page-placeholder";

export default function MediaPage() {
  return (
    <PagePlaceholder
      icon={FolderOpen}
      title="Media manager"
      description="Cached music and stock footage, license attribution, dedupe and delete actions."
      phase="Phase F"
    />
  );
}
