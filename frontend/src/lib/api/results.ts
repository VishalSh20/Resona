import { http } from "./client";
import { toEvidenceVM, toMetricResultVM } from "@/lib/mappers";
import type {
  CompositeDto,
  EvidenceDto,
  JudgeExecutionDto,
  MetricResultDto,
} from "@/types/api";
import type { EvidenceVM, MetricResultVM } from "@/types/domain";

export const resultsApi = {
  getMetric: (metricResultId: string) =>
    http
      .get<MetricResultDto>(`/metric-results/${metricResultId}`)
      .then(toMetricResultVM),
  getEvidence: (metricResultId: string) =>
    http
      .get<EvidenceDto[]>(`/metric-results/${metricResultId}/evidence`)
      .then((rows) => rows.map(toEvidenceVM)),
  getJudgeExecution: (judgeExecutionId: string) =>
    http.get<JudgeExecutionDto>(`/judge-executions/${judgeExecutionId}`),
  getComposite: (runId: string) =>
    http.get<CompositeDto>(`/runs/${runId}/composite`),
};

export type { CompositeDto, EvidenceVM, JudgeExecutionDto, MetricResultVM };
