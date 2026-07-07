"use client";

import { Composer } from "@/components/chat/composer";
import { Sidebar } from "@/components/chat/sidebar";
import { Thread } from "@/components/chat/thread";
import { useChat } from "@/hooks/use-chat";
import { useTheme } from "@/hooks/use-theme";

// Signing out is the only thing the shell needs from Clerk; everything else
// (identity, persistence, answering) flows through the Convex hooks, which
// carry the Clerk session themselves.
type ShellProps = { signOut?: () => Promise<void> };

// The authenticated chat screen: the Conversation sidebar, the thread, and the
// composer, composed over the chat and theme hooks. All state lives in the
// hooks; the components under chat/ are presentation only.
export function Shell({
  signOut = async () => undefined,
}: ShellProps) {
  const { dark, toggle } = useTheme();
  const chat = useChat();

  return (
    <div className="flex min-h-screen w-full flex-col md:flex-row">
      <Sidebar
        conversations={chat.conversations}
        activeId={chat.activeId}
        dark={dark}
        onToggleTheme={toggle}
        onSelect={chat.setActiveId}
        onNewChat={chat.newChat}
        onDeleteConversation={(conversation) =>
          void chat.deleteConversation(conversation)
        }
        onSignOut={() => void signOut()}
      />

      <main className="flex w-full flex-1 flex-col gap-4 px-4 py-4 sm:px-6 md:h-screen md:px-8 md:py-6">
        <Thread turns={chat.active.turns} onPickTopic={chat.setQuestion} />
        <Composer
          question={chat.question}
          onQuestionChange={chat.setQuestion}
          streaming={chat.streaming}
          onSubmit={() => void chat.ask()}
        />
        <p className="text-muted-foreground px-4 text-center text-xs leading-5">
          This assistant gives legal information, not legal advice. For help with
          your situation, contact a lawyer or your nearest Legal Services
          Authority (NALSA / DLSA).
        </p>
      </main>
    </div>
  );
}
