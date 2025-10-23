import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import MainLayout from "../layout/MainLayout";
import ChatMessage from "./ChatMessage";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
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
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  // 🔹 Fetch messages when entering an existing chat
  useEffect(() => {
    async function fetchMessages() {
      if (!chat_id || chat_id === "new") return;

      try {
        const response = await api.get(`/chats/${chat_id}/messages`);
        const messagesData = response.data.data.messages;
        const pagination = response.data.data.pagination;

        const formatted = messagesData
          .sort(
            (a: any, b: any) =>
              new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
          )
          .map((msg: any) => ({
            role: msg.role,
            content: msg.content,
          }));

        console.log("Fetched messages:", formatted);
        console.log("Pagination info:", pagination);

        setMessages(formatted);
      } catch (err) {
        console.error("Failed to load messages:", err);
      }
    }
    fetchMessages();
  }, [chat_id]);

  // 🔹 Upload handler (called when user confirms)
  const handleConfirmUpload = async () => {
    if (!selectedFile) return;
    try {
      setLoading(true);

      // Step 1: Create chat
      const response = await api.post("/chatsCreate", {
        user_id: user?.user_id,
      });
      const newChatId = response.data.data.chat_id;
      console.log("Created new chat with ID:", newChatId);

      // Step 2: Upload file
      const formData = new FormData();
      formData.append("file", selectedFile);
      await api.post(`/chats/${newChatId}/upload`, formData);
      await api.post(`/rag/embed-chat/${newChatId}`);
      console.log("File uploaded and processed.");
      // Step 3: Redirect to new chat page
      navigate(`/chats/${newChatId}`);
    } catch (err) {
      console.error("Upload failed:", err);
    } finally {
      setLoading(false);
      setSelectedFile(null);
    }
  };

  // 🔹 Send message (user + bot + DB persistence)
  const handleSend = async () => {
    if (!input.trim() || !chat_id) return;

    const userMessage = { content: input, role: "user" as const };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");

    try {
      console.log(user?.user_id);
      await api.post(`/chats/${chat_id}/messages`, {
        role: "user",
        content: userMessage.content,
        user_id: user?.user_id,
      });

      const payload = {
        chat_id,
        user_id: user?.user_id || "anonymous",
        query: userMessage.content,
      };

      console.log("📤 Sending RAG request payload:", payload);

      const { data } = await api.post("/rag/ask", payload);

      const botMessage = { content: data.answer, role: "bot" as const };
      console.log(user?.user_id);
      console.log("📥 Received RAG response:", data.answer);
      await api.post(`/chats/${chat_id}/messages`, {
        role: "bot",
        content: data.answer,
        user_id: null,
      });

      setMessages((prev) => [...prev, botMessage]);
    } catch (err) {
      const errorMessage = {
        content: "⚠️ Failed to get response from backend.",
        role: "bot" as const,
      };

      try {
        await api.post(`/chats/${chat_id}/messages`, {
          role: "bot",
          content: errorMessage,
          user_id: null,
        });
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
          <div className="flex flex-col items-center justify-center flex-1 text-center p-6 space-y-4">
            <h2 className="text-2xl font-bold mb-2">
              Upload a document to start chatting
            </h2>

            <Input
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) setSelectedFile(file);
              }}
              className="max-w-sm"
              disabled={loading}
            />

            <p className="text-sm text-gray-400">
              Supported formats: PDF, DOCX, TXT
            </p>

            {/* File confirmation box (animated) */}
            <AnimatePresence mode="wait">
              {selectedFile && (
                <motion.div
                  key="upload-box"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 20 }}
                  transition={{ duration: 0.25 }}
                  className="w-full max-w-sm mt-4 border border-gray-700 rounded-xl p-4 bg-gray-900 shadow-lg"
                >
                  <div className="flex flex-col items-center gap-2">
                    <p className="text-base font-semibold">
                      {selectedFile.name}
                    </p>
                    <p className="text-sm text-gray-400">
                      {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                    </p>

                    <div className="flex gap-3 mt-3">
                      <Button
                        variant="default"
                        onClick={handleConfirmUpload}
                        disabled={loading}
                      >
                        {loading ? "Uploading..." : "Confirm Upload"}
                      </Button>
                      <Button
                        variant="destructive"
                        onClick={() => setSelectedFile(null)}
                        disabled={loading}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
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
