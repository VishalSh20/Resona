import { MotionConfig } from "framer-motion";

import { HeroSection } from "@/features/landing/HeroSection";
import { CoverageSection } from "@/features/landing/sections/CoverageSection";
import { EdgeCasesSection } from "@/features/landing/sections/EdgeCasesSection";
import { EvaluationSection } from "@/features/landing/sections/EvaluationSection";
import { FinalCtaSection } from "@/features/landing/sections/FinalCtaSection";
import { LanguageSection } from "@/features/landing/sections/LanguageSection";
import { ProvenanceSection } from "@/features/landing/sections/ProvenanceSection";
import { ProvidersSection } from "@/features/landing/sections/ProvidersSection";
import { ScoreEvidenceSection } from "@/features/landing/sections/ScoreEvidenceSection";
import { SimulationSection } from "@/features/landing/sections/SimulationSection";
import { VersionCompareSection } from "@/features/landing/sections/VersionCompareSection";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function LandingPage() {
  useDocumentTitle();

  return (
    <MotionConfig reducedMotion="user">
      <main className="min-h-screen bg-canvas text-foreground">
        <HeroSection />
        <EvaluationSection />
        <ScoreEvidenceSection />
        <LanguageSection />
        <SimulationSection />
        <EdgeCasesSection />
        <VersionCompareSection />
        <CoverageSection />
        <ProvenanceSection />
        <ProvidersSection />
        <FinalCtaSection />
      </main>
    </MotionConfig>
  );
}
