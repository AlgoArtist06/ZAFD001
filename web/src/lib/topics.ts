import {
  Car,
  FileSearch,
  Landmark,
  Laptop,
  Lightbulb,
  Scale,
  Shield,
  ShieldAlert,
  ShoppingCart,
  type LucideIcon,
} from "lucide-react";

// The icon-led tiles for the common legal topics the assistant covers. Each
// prefills a plain-language starter question so a low-literacy user can begin
// without typing. The set mirrors the product's Covered Domains; expanding
// coverage means adding a tile here.
export type TopicTile = { icon: LucideIcon; label: string; prompt: string };

export const TOPIC_TILES: TopicTile[] = [
  {
    icon: ShoppingCart,
    label: "Consumer rights",
    prompt: "What are my consumer rights if a shop cheated me?",
  },
  {
    icon: Shield,
    label: "Police & arrest",
    prompt: "What are my rights during a police interaction or arrest?",
  },
  {
    icon: Landmark,
    label: "Fundamental rights",
    prompt: "What are my fundamental rights?",
  },
  {
    icon: Scale,
    label: "Criminal law",
    prompt: "What does the law say about theft of property?",
  },
  {
    icon: Laptop,
    label: "Cybercrime & online fraud",
    prompt: "What does the law say about online fraud and identity theft?",
  },
  {
    icon: Car,
    label: "Traffic & driving",
    prompt: "What is the penalty for driving without a licence or drunk driving?",
  },
  {
    icon: FileSearch,
    label: "Right to Information",
    prompt: "How do I file an RTI request, and what happens if it is refused?",
  },
  {
    icon: ShieldAlert,
    label: "Domestic & workplace safety",
    prompt: "What protection does the law give against domestic violence?",
  },
  {
    icon: Lightbulb,
    label: "Government schemes",
    prompt: "Which government scheme can help me, and how do I apply?",
  },
];
