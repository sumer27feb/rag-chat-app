import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import MainLayout from "./components/layout/MainLayout";

const Home = () => {
  return (
    <MainLayout>
      <div className="flex flex-col items-center justify-center h-full text-center text-white">
        {/* Title */}
        <h1 className="text-3xl font-bold mb-2">Sumer's LLM-QA App</h1>
        <p className="text-gray-400 mb-6">
          Start a new chat and ask anything about your document.
        </p>

        {/* New Chat Button */}
        <Button variant="secondary" size="lg">
          <Plus className="w-4 h-4 mr-2" /> New Chat
        </Button>

        {/* Optional Example Prompts */}
        <div className="mt-8 grid gap-3">
          <Button variant="outline" size="sm" className="text-gray-300">
            Summarize this document
          </Button>
          <Button variant="outline" size="sm" className="text-gray-300">
            Find all key dates
          </Button>
          <Button variant="outline" size="sm" className="text-gray-300">
            Explain technical terms
          </Button>
        </div>
      </div>
    </MainLayout>
  );
};

export default Home;
