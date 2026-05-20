import { redirect } from "next/navigation";

/**
 * Root route. For the static-demo build, redirect to the cargo-plane
 * scenario page. TASK-12 adds the persona launcher that lands here.
 */
export default function Home() {
  redirect("/scenarios/cargo-plane");
}
