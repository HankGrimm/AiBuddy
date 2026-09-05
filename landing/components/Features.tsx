const FEATURES = [
  {
    icon: "⚡",
    title: "Stake-to-Interact",
    desc: "MON escrow gates every meaningful action — room entry, match requests, DM unlocks. The escrow contract holds funds on-chain. Auto-slash runs hourly via Celery.",
    tags: ["Monad Escrow", "Native MON", "Celery"],
    color: "violet",
  },
  {
    icon: "🤖",
    title: "AI Match Agent",
    desc: "Bag-of-words preference embeddings (45-term vocab, L2-normalised), 5-dimension scoring, vibe filtering, and personalized AI-generated intros via Claude.",
    tags: ["Vector Similarity", "Claude AI", "ZeroDB"],
    color: "purple",
  },
  {
    icon: "📍",
    title: "GPS Meetup Attestation",
    desc: "Haversine proximity check (100m threshold). BLE token + QR code fallbacks. Both parties sign. Confirmed → stake refunded + Hedera HCS anchor.",
    tags: ["Hedera HCS", "GPS", "BLE/QR"],
    color: "pink",
  },
  {
    icon: "💳",
    title: "Coinbase x402 Payments",
    desc: "HTTP 402 payment protocol for DM unlocks. Base USDC (0.5 USDC per DM). Facilitator-verified proof-of-payment. Graceful degradation when disabled.",
    tags: ["x402 Protocol", "Base USDC", "Coinbase"],
    color: "coral",
  },
  {
    icon: "🛡️",
    title: "Safety Engine",
    desc: "6 report categories, auto-deactivation for underage reports, repeat-offender detection (3+ reports), moderation queue with severity scoring.",
    tags: ["Moderation", "Report System", "Auto-Actions"],
    color: "violet",
  },
  {
    icon: "📊",
    title: "Reputation Engine",
    desc: "5-dimension composite score: reliability, safety, response rate, meetup completion, consent. Time-based decay (−1pt/week). Event-driven updates.",
    tags: ["Decay Algorithm", "Trust Score", "Portable"],
    color: "purple",
  },
  {
    icon: "🎭",
    title: "Multi-Persona System",
    desc: "Create multiple personas per wallet — anonymous or named. Room-scoped personas with visibility controls. Intent modes: social, dating, networking, friendship.",
    tags: ["Privacy Modes", "Persona Scoping", "Intent Modes"],
    color: "pink",
  },
  {
    icon: "🔗",
    title: "Immutable Audit Trail",
    desc: "Every safety decision anchored on Hedera Hashgraph Consensus Service. Tamper-proof log of attestations, slashings, and report resolutions.",
    tags: ["Hedera HCS", "DLT", "Compliance"],
    color: "coral",
  },
];

const colorMap: Record<string, string> = {
  violet: "bg-brand-violet/10 text-violet-300 border-brand-violet/20",
  purple: "bg-purple-500/10 text-purple-300 border-purple-500/20",
  pink: "bg-brand-pink/10 text-pink-300 border-brand-pink/20",
  coral: "bg-orange-500/10 text-orange-300 border-orange-500/20",
};

export default function Features() {
  return (
    <section id="features" className="py-24 px-6 bg-brand-dark/50">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <div className="inline-block text-sm font-medium text-pink-400 bg-brand-pink/10 border border-brand-pink/20 px-4 py-1.5 rounded-full mb-4">
            Features
          </div>
          <h2 className="text-4xl md:text-5xl font-black tracking-tight">
            Everything you'd expect.{" "}
            <span className="text-gradient">Nothing you've seen before.</span>
          </h2>
          <p className="mt-4 text-white/50 max-w-xl mx-auto text-lg">
            Built on Monad, Hedera, Base, and Coinbase. Every feature has
            on-chain accountability baked in from day one.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-5">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="p-5 rounded-2xl border-gradient bg-brand-card hover:scale-[1.02] transition-transform duration-200 cursor-default"
            >
              <div className="text-3xl mb-3">{f.icon}</div>
              <h3 className="font-bold mb-2">{f.title}</h3>
              <p className="text-white/50 text-sm leading-relaxed mb-4">
                {f.desc}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {f.tags.map((tag) => (
                  <span
                    key={tag}
                    className={`text-xs px-2 py-0.5 rounded-full border ${colorMap[f.color]}`}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
