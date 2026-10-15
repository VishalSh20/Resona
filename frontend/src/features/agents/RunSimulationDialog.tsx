import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Play, Plus } from "lucide-react";

import { ErrorState } from "@/components/domain/States";
import { SelectableCard } from "@/components/forms/SelectableCard";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { newIdempotencyKey } from "@/lib/api/idempotency";
import { simulationsApi } from "@/lib/api/simulations";
import { simulationKeys } from "@/lib/queryKeys";
import type { SimulationDto } from "@/types/api";

type Mode = "previous" | "new";

interface RunSimulationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agentId: string;
  agentName: string;
  revisionId: string;
  revisionLabel: string;
  simulations: SimulationDto[];
  simulationsLoading: boolean;
}

export function RunSimulationDialog({
  open,
  onOpenChange,
  agentId,
  agentName,
  revisionId,
  revisionLabel,
  simulations,
  simulationsLoading,
}: RunSimulationDialogProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<Mode>("previous");
  const [simulationId, setSimulationId] = useState("");

  useEffect(() => {
    if (open) {
      setMode("previous");
      setSimulationId("");
    }
  }, [open]);

  const createRun = useMutation({
    mutationFn: (id: string) =>
      simulationsApi.createRun(
        id,
        { target_revision_id: revisionId },
        newIdempotencyKey("run:create"),
      ),
    onSuccess: (run) => {
      void queryClient.invalidateQueries({ queryKey: simulationKeys.all });
      onOpenChange(false);
      navigate(`/app/simulations/${run.simulation_id}/runs/${run.id}`);
    },
  });

  const hasSimulations = simulationsLoading || simulations.length > 0;

  const createNewSimulation = () => {
    onOpenChange(false);
    const params = new URLSearchParams({ agent: agentId, revision: revisionId });
    navigate(`/app/simulations/new?${params.toString()}`);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Run a simulation</DialogTitle>
          <DialogDescription>
            Start a new run on {revisionLabel} of {agentName}.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-2.5">
          <SelectableCard
            selected={mode === "previous"}
            onToggle={() => setMode("previous")}
            disabled={!hasSimulations}
            leading={<Play className="size-4" />}
            title="Run from a previous simulation"
            description="Create a new run on this revision from a simulation you already have."
          />
          <SelectableCard
            selected={mode === "new"}
            onToggle={() => setMode("new")}
            leading={<Plus className="size-4" />}
            title="Create a new simulation"
            description="Define a new simulation, prefilled with this agent and revision."
          />
        </div>

        {mode === "previous" && (
          <div className="space-y-3">
            {!hasSimulations ? (
              <p className="text-body-sm text-muted-foreground">
                This agent has no simulations yet. Create a new one instead.
              </p>
            ) : (
              <>
                <Select
                  value={simulationId || undefined}
                  onValueChange={setSimulationId}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue
                      placeholder={
                        simulationsLoading
                          ? "Loading simulations…"
                          : "Select a simulation"
                      }
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {simulations.map((simulation) => (
                      <SelectItem key={simulation.id} value={simulation.id}>
                        {simulation.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {createRun.isError && (
                  <ErrorState
                    error={createRun.error}
                    title="Could not create run."
                  />
                )}
              </>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          {mode === "previous" ? (
            <Button
              disabled={!simulationId || createRun.isPending}
              onClick={() => createRun.mutate(simulationId)}
            >
              {createRun.isPending ? "Creating run…" : "Create run"}
            </Button>
          ) : (
            <Button onClick={createNewSimulation}>Create simulation</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
