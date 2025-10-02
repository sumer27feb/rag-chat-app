import { useState, useEffect } from "react";
import MainLayout from "../layout/MainLayout";
import ChatMessage from "./ChatMessage";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input"; // for file upload
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { useNavigate, useParams } from "react-router-dom";

type Message = {
  content: string;
  role: "bot" | "user";
};

export default function ChatPage() {
  const { user } = useAuth();
  const { chat_id } = useParams();
  const navigate = useNavigate();

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  // 🔹 Fetch messages when entering an existing chat
  useEffect(() => {
    async function fetchMessages() {
      if (!chat_id || chat_id === "new") return;
      try {
        const { data } = await api.get(`/chats/${chat_id}/messages`);
        // Map backend schema → frontend schema
        const formatted = data
          .sort(
            (a: any, b: any) =>
              new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
          )
          .map((msg: any) => ({
            role: msg.role,
            content: msg.content,
          }));
        console.log("Fetched messages:", formatted);
        setMessages(formatted);
      } catch (err) {
        console.error("Failed to load messages:", err);
      }
    }
    fetchMessages();
  }, [chat_id]);

  // 🔹 Upload handler
  const handleDocumentUpload = async (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setLoading(true);

      // Step 1: Create chat
      const { data } = await api.post("/chatsCreate", {
        user_id: user?.user_id,
      });
      const newChatId = data.chat_id;

      // Step 2: Upload file
      const formData = new FormData();
      formData.append("file", file);
      await api.post(`/chats/${newChatId}/upload`, formData);

      // Step 3: Redirect to new chat page
      navigate(`/chats/${newChatId}`);
    } catch (err) {
      console.error("Upload failed:", err);
    } finally {
      setLoading(false);
    }
  };

  // 🔹 Send message (user + bot + DB persistence)
  const handleSend = async () => {
    if (!input.trim() || !chat_id) return;

    const userMessage = { content: input, role: "user" as const };

    // Optimistically show user message
    setMessages((prev) => [...prev, userMessage]);
    setInput("");

    try {
      // Step 1: Save user message in DB
      await api.post(`/chats/${chat_id}/messages`, {
        role: "user",
        content: userMessage.content,
      });

      // Step 2: Ask backend (RAG pipeline)
      const { data } = await api.post("/rag/ask", {
        chat_id,
        query: userMessage.content,
      });

      const botMessage = { content: data.answer, role: "bot" as const };

      // Step 3: Save bot reply in DB
      await api.post(`/chats/${chat_id}/messages`, {
        role: "bot",
        content: data.answer,
      });

      // Step 4: Show bot reply in UI
      setMessages((prev) => [...prev, botMessage]);
    } catch (err) {
      const errorMessage = {
        content: "⚠️ Failed to get response from backend.",
        role: "bot" as const,
      };

      // Try saving error to DB too
      try {
        await api.post(`/chats/${chat_id}/messages`, errorMessage);
      } catch (saveErr) {
        console.error("Also failed saving error message:", saveErr);
      }

      setMessages((prev) => [...prev, errorMessage]);
      console.error("Backend error:", err);
    }
  };

  return (
    <MainLayout>
      <div className="flex flex-col h-full max-h-screen">
        {/* New Chat (upload first) */}
        {chat_id === "new" ? (
          <div className="flex flex-col items-center justify-center flex-1 text-center p-6">
            <h2 className="text-2xl font-bold mb-4">
              Upload a document to start chatting
            </h2>
            <Input
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={handleDocumentUpload}
              className="max-w-sm"
              disabled={loading}
            />
            <p className="text-sm text-gray-400 mt-2">
              Supported formats: PDF, DOCX, TXT
            </p>
          </div>
        ) : (
          <>
            {/* Chat messages */}
            <ScrollArea className="flex-1 px-4 py-6 space-y-4 overflow-y-auto">
              {messages.length === 0 ? (
                <p className="text-gray-400 text-center">
                  No messages yet. Start asking questions!
                </p>
              ) : (
                messages.map((msg, idx) => (
                  <ChatMessage
                    key={idx}
                    role={msg.role}
                    content={msg.content}
                  />
                ))
              )}
            </ScrollArea>

            {/* Input area */}
            <div className="border-t p-4">
              <div className="flex gap-2">
                <Textarea
                  placeholder="Ask something..."
                  className="resize-none"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                />
                <Button onClick={handleSend}>Send</Button>
              </div>
            </div>
          </>
        )}
      </div>
    </MainLayout>
  );
}
