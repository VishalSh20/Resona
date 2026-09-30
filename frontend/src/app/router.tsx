import { Suspense, lazy } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppShell } from "@/app/shell/AppShell";
import { OverviewPage } from "@/app/pages/OverviewPage";
import { PlaceholderPage } from "@/app/pages/PlaceholderPage";
import { SignInPage } from "@/features/auth/SignInPage";
import { SignUpPage } from "@/features/auth/SignUpPage";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { BenchmarkCreatePage } from "@/features/benchmarks/BenchmarkCreatePage";
import { BenchmarkListPage } from "@/features/benchmarks/BenchmarkListPage";
import { BenchmarkOverviewPage } from "@/features/benchmarks/BenchmarkOverviewPage";
import { BenchmarkVersionCreatePage } from "@/features/benchmarks/BenchmarkVersionCreatePage";
import { BenchmarkVersionPage } from "@/features/benchmarks/BenchmarkVersionPage";
import { RunDetailPage } from "@/features/runs/RunDetailPage";
import { SimulationCreateWizardPage } from "@/features/simulations/SimulationCreateWizardPage";
import { SimulationListPage } from "@/features/simulations/SimulationListPage";
import { SimulationOverviewPage } from "@/features/simulations/SimulationOverviewPage";
import { AgentCreateWizardPage } from "@/features/agents/AgentCreateWizardPage";
import { AgentListPage } from "@/features/agents/AgentListPage";
import { AgentOverviewPage } from "@/features/agents/AgentOverviewPage";
import { AgentRevisionImportPage } from "@/features/agents/AgentRevisionImportPage";
import { AgentRevisionPage } from "@/features/agents/AgentRevisionPage";

// The public landing page (and its animation/WebGL deps) is split into its own
// chunk so the authenticated application never downloads it.
const LandingPage = lazy(() =>
  import("@/features/landing/LandingPage").then((module) => ({
    default: module.LandingPage,
  })),
);

export const router = createBrowserRouter([
  {
    path: "/",
    element: (
      <Suspense fallback={<div className="min-h-screen bg-white" />}>
        <LandingPage />
      </Suspense>
    ),
  },
  { path: "/signin", element: <SignInPage /> },
  { path: "/signup", element: <SignUpPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        path: "/app",
        element: <AppShell />,
        children: [
          { index: true, element: <OverviewPage /> },
          {
            path: "simulations",
            children: [
              { index: true, element: <SimulationListPage /> },
              { path: "new", element: <SimulationCreateWizardPage /> },
              {
                path: ":simulationId",
                children: [
                  { index: true, element: <SimulationOverviewPage /> },
                  { path: "runs/:runId", element: <RunDetailPage /> },
                ],
              },
            ],
          },
          {
            path: "benchmarks",
            children: [
              { index: true, element: <BenchmarkListPage /> },
              { path: "new", element: <BenchmarkCreatePage /> },
              {
                path: ":benchmarkId",
                children: [
                  { index: true, element: <Navigate to="overview" replace /> },
                  { path: "overview", element: <BenchmarkOverviewPage /> },
                  { path: "versions/new", element: <BenchmarkVersionCreatePage /> },
                  { path: "versions/:versionId", element: <BenchmarkVersionPage /> },
                ],
              },
            ],
          },
          {
            path: "agents",
            children: [
              { index: true, element: <AgentListPage /> },
              { path: "new", element: <AgentCreateWizardPage /> },
              {
                path: ":agentId",
                children: [
                  { index: true, element: <Navigate to="overview" replace /> },
                  { path: "overview", element: <AgentOverviewPage /> },
                  { path: "revisions/import", element: <AgentRevisionImportPage /> },
                  { path: "revisions/:revisionId", element: <AgentRevisionPage /> },
                ],
              },
            ],
          },
          { path: "*", element: <PlaceholderPage title="Not Found" /> },
        ],
      },
    ],
  },
  { path: "*", element: <PlaceholderPage title="Not Found" /> },
]);
