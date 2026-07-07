// Covered Domain routing, ported from rag/domain/routing.py. Retrieval is
// metadata-filtered and routed by domain first, so a consumer query does not
// pull criminal sections. When nothing matches, every domain is returned -
// retrieval still runs, and the lexical-overlap gate downstream decides
// support vs. Refusal.
import { ACT_TYPES, type ActType } from "./models";
import { contentStems } from "./text";

// Domain trigger words; stemmed at module load to match contentStems output.
const DOMAIN_TRIGGERS: Record<ActType, string[]> = {
  criminal: [
    "theft", "steal", "stolen", "thief", "cheat", "cheated", "fraud",
    "dishonest", "police", "arrest", "arrested", "punishment", "offence",
    "crime", "criminal", "fir", "bail", "robbery", "assault",
  ],
  consumer: [
    "consumer", "complaint", "goods", "good", "service", "seller", "shop",
    "shopkeeper", "refund", "product", "defective", "deliver", "delivery",
    "purchase", "buy", "warranty", "commission",
  ],
  ip: [
    "copyright", "patent", "trademark", "infringe", "infringed",
    "infringement", "intellectual", "invention", "brand", "logo",
  ],
  constitutional: [
    "right", "rights", "liberty", "equality", "life", "freedom",
    "fundamental", "constitution", "constitutional", "discrimination",
    "speech", "personal",
  ],
  scheme: [
    "scheme", "yojana", "eligibility", "eligible", "subsidy", "benefit",
    "pension", "welfare", "apply", "application",
  ],
  cyber: [
    "cyber", "hacking", "hacked", "hacker", "online", "internet",
    "computer", "phishing", "otp", "password", "email", "website",
    "identity",
  ],
  transport: [
    "challan", "traffic", "driving", "drive", "driver", "licence",
    "license", "vehicle", "motor", "helmet", "seatbelt", "accident",
    "drunk", "overspeeding", "insurance",
  ],
  governance: ["rti", "transparency", "disclosure"],
  protection: [
    "domestic", "violence", "abuse", "harass", "harassment", "husband",
    "wife", "workplace", "posh", "dowry", "stridhan",
  ],
};

const STEMMED_TRIGGERS: Record<ActType, Set<string>> = Object.fromEntries(
  ACT_TYPES.map((domain) => [
    domain,
    new Set(DOMAIN_TRIGGERS[domain].flatMap((word) => contentStems(word))),
  ]),
) as Record<ActType, Set<string>>;

// Covered Domains a query touches, in stable order; all domains when none match.
export function routeDomains(query: string): ActType[] {
  const stems = new Set(contentStems(query));
  const matched = ACT_TYPES.filter((domain) =>
    [...stems].some((s) => STEMMED_TRIGGERS[domain].has(s)),
  );
  return matched.length > 0 ? matched : [...ACT_TYPES];
}
