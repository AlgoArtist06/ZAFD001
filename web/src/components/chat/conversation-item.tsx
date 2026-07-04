import { Trash2 } from "lucide-react";

import { conversationTitle, type Conversation } from "@/hooks/use-chat";

type ConversationItemProps = {
  conversation: Conversation;
  active: boolean;
  onSelect: () => void;
  onDelete: () => void;
};

export function ConversationItem({
  conversation,
  active,
  onSelect,
  onDelete,
}: ConversationItemProps) {
  const title = conversationTitle(conversation);
  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={onSelect}
        aria-current={active}
        className={`min-w-0 flex-1 cursor-pointer rounded-lg border border-transparent px-3 py-2.5 text-left text-sm transition-colors hover:bg-sidebar-accent ${
          active ? "border-border bg-sidebar-accent font-medium" : ""
        }`}
      >
        <span className="block truncate">{title}</span>
      </button>
      <button
        type="button"
        aria-label={`Delete Conversation ${title}`}
        onClick={onDelete}
        className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive cursor-pointer rounded-lg p-2 transition-colors"
      >
        <Trash2 className="size-4" aria-hidden />
      </button>
    </div>
  );
}
