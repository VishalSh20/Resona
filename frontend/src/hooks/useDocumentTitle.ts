import { useEffect } from "react";

import { BRAND } from "@/lib/constants/brand";

export function useDocumentTitle(title?: string) {
  useEffect(() => {
    document.title = title ? `${BRAND.name} — ${title}` : BRAND.name;
  }, [title]);
}
