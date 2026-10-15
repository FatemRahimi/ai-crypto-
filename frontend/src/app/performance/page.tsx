import type { Metadata } from "next";
import { PerformanceBoard } from "@/components/performance/PerformanceBoard";

export const metadata: Metadata = { title: "Performance" };

export default function PerformancePage() {
  return <PerformanceBoard />;
}
