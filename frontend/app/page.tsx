import { TopBar } from "@/components/TopBar";
import { CommandCenter } from "@/components/CommandCenter";
import { DemoGuideProvider } from "@/components/DemoGuideProvider";
import { DemoGuidePanel } from "@/components/DemoGuidePanel";
import { GuideSpotlight } from "@/components/GuideSpotlight";

export default function Home() {
  return (
    <DemoGuideProvider>
      <main className="min-h-screen bg-redis-bg text-redis-text">
        <TopBar />
        <GuideSpotlight />
        <CommandCenter />
        <DemoGuidePanel />
      </main>
    </DemoGuideProvider>
  );
}
