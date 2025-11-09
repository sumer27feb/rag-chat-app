import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ComponentProps } from "react";

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
        className={`p-3 rounded-lg max-w-md prose prose-sm
          ${isUser ? "bg-zinc-800 text-white" : "bg-zinc-100 text-black"}
          prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-strong:font-semibold`}
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            code({
              inline,
              className,
              children,
              ...props
            }: ComponentProps<"code"> & { inline?: boolean }) {
              // const match = /language-(\w+)/.exec(className || "");

              return !inline ? (
                <pre className="bg-zinc-900 text-zinc-100 p-2 rounded-md overflow-x-auto text-sm">
                  <code {...props}>{children}</code>
                </pre>
              ) : (
                <code className="bg-zinc-200 text-zinc-900 px-1 rounded">
                  {children}
                </code>
              );
            },
          }}
        >
          {content}
        </ReactMarkdown>
      </div>

      {isUser && (
        <Avatar>
          <AvatarFallback>👤</AvatarFallback>
        </Avatar>
      )}
    </div>
  );
}
