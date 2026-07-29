import { Upload } from "lucide-react";

import { PagePlaceholder } from "@/components/common/page-placeholder";

export default function UploadsPage() {
  return (
    <PagePlaceholder
      icon={Upload}
      title="Upload manager"
      description="Publish history from real generation records, YouTube connection status, and upload scheduling."
      phase="Phase G"
    />
  );
}
