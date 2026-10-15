import type { Metadata } from "next";
import { StrategyStudio } from "@/components/strategy/StrategyStudio";

export const metadata: Metadata = { title: "Strategy" };

export default function StrategyPage() {
  return <StrategyStudio />;
}
