// src/components/ChatMessage.tsx
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

type ChatMessageProps = {
  role: "user" | "bot";
  content: string;
};

export default function ChatMessage({ role, content }: ChatMessageProps) {
  const isUser = role === "user";

  return (
    <div className={`flex items-start gap-4 ${isUser ? "justify-end" : ""}`}>
      {!isUser && (
        <Avatar>
          <AvatarFallback>🤖</AvatarFallback>
        </Avatar>
      )}
      <div
        className={`p-3 rounded-lg max-w-md whitespace-pre-wrap break-words ${
          isUser ? "bg-zinc-800 text-white" : "bg-zinc-200 text-black"
        }`}
      >
        {content}
      </div>
      {isUser && (
        <Avatar>
          <AvatarFallback>👤</AvatarFallback>
        </Avatar>
      )}
    </div>
  );
}
