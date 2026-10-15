import type { Metadata } from "next";
import { PositionBoard } from "@/components/positions/PositionBoard";

export const metadata: Metadata = { title: "Positions" };

export default function PositionsPage() {
  return <PositionBoard />;
}
