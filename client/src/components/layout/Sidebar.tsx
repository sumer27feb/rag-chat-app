// src/components/layout/Sidebar.tsx
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { PlusIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "@/lib/api"; // your axios wrapper
import { useAuth } from "@/context/AuthContext";

interface Chat {
  chat_id: string;
  title?: string | null;
  updated_at?: string;
}

export default function Sidebar() {
  const [chats, setChats] = useState<Chat[]>([]);
  const { chat_id } = useParams(); // current chat route
  const navigate = useNavigate();
  const { user } = useAuth();
  useEffect(() => {
    let interval: NodeJS.Timeout;

    async function fetchChats() {
      try {
        const id = user?.user_id;
        if (!id) return;
        const { data } = await api.get(`/users/${id}/chats`);
        setChats(data);
      } catch (err) {
        console.error("Failed to fetch chats:", err);
      }
    }

    if (user) {
      fetchChats(); // fetch once immediately
      interval = setInterval(fetchChats, 5000); // every 5 seconds
    }

    return () => clearInterval(interval); // cleanup
  }, [user]);

  return (
    <aside className="h-screen w-64 bg-zinc-950 text-white flex flex-col border-r border-zinc-800">
      {/* New Chat Button */}
      <div className="p-4 border-b border-zinc-800">
        <Button
          variant="outline"
          className="w-full justify-start text-white bg-zinc-900 hover:bg-zinc-800"
          onClick={() => navigate("/chats/new")}
        >
          <PlusIcon className="mr-2 h-4 w-4" />
          New Chat
        </Button>
      </div>

      {/* Chat List */}
      <ScrollArea className="flex-1 px-2 py-2">
        <div className="space-y-1">
          {chats.map((c) => (
            <SidebarItem
              key={c.chat_id}
              title={c.title || "Untitled Chat"}
              active={chat_id === c.chat_id}
              onClick={() => navigate(`/chats/${c.chat_id}`)}
            />
          ))}
        </div>
      </ScrollArea>

      {/* Footer */}
      <div className="p-4 border-t border-zinc-800 text-sm text-zinc-400">
        Sumer's LLM-QA App
      </div>
    </aside>
  );
}

function SidebarItem({
  title,
  active,
  onClick,
}: {
  title: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2 rounded-md text-sm transition ${
        active ? "bg-zinc-800 text-white" : "hover:bg-zinc-800 text-zinc-300"
      }`}
    >
      {title}
    </button>
  );
}
