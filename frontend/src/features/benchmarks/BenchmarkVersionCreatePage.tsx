import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { FormField } from "@/components/forms/FormField";
import { PageHeader } from "@/components/domain/PageHeader";
import { ErrorState } from "@/components/domain/States";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCreateBenchmarkVersion } from "@/features/benchmarks/queries";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { newIdempotencyKey } from "@/lib/api/idempotency";
import { parseJsonObject } from "@/lib/validation/targetConfig";

export function BenchmarkVersionCreatePage() {
  const { benchmarkId = "" } = useParams();
  useDocumentTitle("New benchmark version");
  const navigate = useNavigate();
  const createVersion = useCreateBenchmarkVersion(benchmarkId);

  const [version, setVersion] = useState("");
  const [manifestText, setManifestText] = useState('{ "cases": [] }');
  const [formError, setFormError] = useState<string | null>(null);

  async function submit() {
    setFormError(null);
    if (!version.trim()) {
      setFormError("Version is required.");
      return;
    }

    let manifest: Record<string, unknown> | undefined;
    if (manifestText.trim() !== "") {
      try {
        manifest = parseJsonObject(manifestText);
      } catch (error) {
        setFormError(
          `Manifest: ${error instanceof Error ? error.message : "invalid JSON"}`,
        );
        return;
      }
    }

    try {
      const created = await createVersion.mutateAsync({
        input: { version: version.trim(), manifest: manifest ?? null },
        idempotencyKey: newIdempotencyKey("benchmark:version"),
      });
      navigate(`/app/benchmarks/${benchmarkId}/versions/${created.id}`);
    } catch {
      // surfaced via createVersion.isError
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <PageHeader
        title="New benchmark version"
        description="Versions are drafts until frozen; a frozen version is immutable."
      />
      <Card className="p-6">
        <div className="space-y-4">
          <FormField label="Version" htmlFor="version" required>
            <Input
              id="version"
              value={version}
              placeholder="1"
              className="w-32 font-mono text-mono"
              onChange={(event) => setVersion(event.target.value)}
            />
          </FormField>
          <div className="space-y-1.5">
            <Label htmlFor="manifest">Manifest</Label>
            <Textarea
              id="manifest"
              value={manifestText}
              rows={10}
              spellCheck={false}
              className="font-mono text-mono"
              onChange={(event) => setManifestText(event.target.value)}
            />
            <p className="text-micro text-muted-foreground">
              Optional JSONB. Cases are read from a{" "}
              <code className="font-mono">cases</code> array when present.
            </p>
          </div>

          {(formError || createVersion.isError) && (
            <ErrorState
              error={formError ? new Error(formError) : createVersion.error}
              title="Could not create version."
            />
          )}

          <div className="flex items-center justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => navigate(`/app/benchmarks/${benchmarkId}/overview`)}
            >
              Cancel
            </Button>
            <Button onClick={() => void submit()} disabled={createVersion.isPending}>
              {createVersion.isPending ? "Creating…" : "Create version"}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
