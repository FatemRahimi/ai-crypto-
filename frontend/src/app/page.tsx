import type { Metadata } from "next";
import { CommandCenter } from "@/components/home/CommandCenter";

export const metadata: Metadata = { title: "Home" };

export default function HomePage() {
  return <CommandCenter />;
}
