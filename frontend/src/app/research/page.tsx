import type { Metadata } from "next";
import { ResearchBoard } from "@/components/research/ResearchBoard";

export const metadata: Metadata = { title: "Research" };

export default function ResearchPage() {
  return <ResearchBoard />;
}
