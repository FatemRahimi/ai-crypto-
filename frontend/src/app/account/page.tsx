import type { Metadata } from "next";
import { AccountBoard } from "@/components/account/AccountBoard";

export const metadata: Metadata = { title: "Account" };

export default function AccountPage() {
  return <AccountBoard />;
}
