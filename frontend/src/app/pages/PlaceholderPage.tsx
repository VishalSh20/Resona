import { Card } from "@/components/ui/card";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

interface PlaceholderPageProps {
  title: string;
}

export function PlaceholderPage({ title }: PlaceholderPageProps) {
  useDocumentTitle(title);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-display-md">{title}</h1>
        <p className="mt-1 text-body-sm text-muted-foreground">
          This view ships in a later phase of the Resona frontend.
        </p>
      </div>
      <Card className="items-start gap-2 p-6">
        <p className="text-body text-muted-foreground">
          Nothing to render yet. The shell, routing, design tokens, status
          primitives and data tables are in place; this surface lands with the
          configuration, execution, results and forensics phases.
        </p>
      </Card>
    </div>
  );
}
