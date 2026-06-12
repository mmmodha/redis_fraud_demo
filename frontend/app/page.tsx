import { TopBar } from "@/components/TopBar";
import { CommandCenter } from "@/components/CommandCenter";

export default function Home() {
  return (
    <main className="min-h-screen bg-redis-bg text-redis-text">
      <TopBar />
      <CommandCenter />
    </main>
  );
}
