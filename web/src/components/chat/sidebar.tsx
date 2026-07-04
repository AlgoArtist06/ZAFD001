"use client";

import Link from "next/link";
import { LogOut, Moon, Plus, Scale, Settings, Sun } from "lucide-react";

import { ConversationItem } from "@/components/chat/conversation-item";
import { Button } from "@/components/ui/button";
import type { Conversation } from "@/hooks/use-chat";

type SidebarProps = {
  conversations: Conversation[];
  activeId: number;
  dark: boolean;
  onToggleTheme: () => void;
  onSelect: (id: number) => void;
  onNewChat: () => void;
  onDeleteConversation: (conversation: Conversation) => void;
  onSignOut: () => void;
};

export function Sidebar({
  conversations,
  activeId,
  dark,
  onToggleTheme,
  onSelect,
  onNewChat,
  onDeleteConversation,
  onSignOut,
}: SidebarProps) {
  return (
    <aside
      aria-label="Conversations"
      className="bg-sidebar relative z-10 flex w-full flex-col gap-5 border-b p-4 md:h-screen md:w-72 md:border-r md:border-b-0 md:p-5"
    >
      <div className="flex items-center gap-3">
        <span className="bg-primary text-primary-foreground grid size-10 place-items-center rounded-lg shadow-xs">
          <Scale className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-heading text-lg font-semibold tracking-tight">
            Legal Saathi
          </p>
          <p className="text-muted-foreground text-xs">
            Rights, made understandable
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label={dark ? "Use light mode" : "Use dark mode"}
          onClick={onToggleTheme}
          className="rounded-full"
        >
          {dark ? <Sun aria-hidden /> : <Moon aria-hidden />}
        </Button>
      </div>
      <Button
        aria-label="New chat"
        onClick={onNewChat}
        className="min-h-11 justify-start rounded-lg shadow-xs"
      >
        <Plus className="size-4" aria-hidden /> New conversation
      </Button>
      <nav
        aria-label="Conversation list"
        className="flex max-h-40 flex-col gap-1 overflow-y-auto md:max-h-none"
      >
        {conversations.map((conversation) => (
          <ConversationItem
            key={conversation.id}
            conversation={conversation}
            active={conversation.id === activeId}
            onSelect={() => onSelect(conversation.id)}
            onDelete={() => onDeleteConversation(conversation)}
          />
        ))}
      </nav>
      <div className="mt-auto flex flex-col gap-1">
        <Button
          asChild
          variant="ghost"
          className="text-muted-foreground min-h-11 justify-start"
        >
          <Link href="/settings">
            <Settings aria-hidden />
            Settings
          </Link>
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={onSignOut}
          className="text-muted-foreground min-h-11 justify-start"
        >
          <LogOut aria-hidden />
          Sign out
        </Button>
      </div>
    </aside>
  );
}
