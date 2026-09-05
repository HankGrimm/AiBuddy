const STEPS = [
  {
    n: "01",
    icon: "🔐",
    title: "Connect Your Wallet",
    desc: "Sign in with your MetaMask or Rabby wallet. No email, no password. Your Monad public key is your identity. Verification tiers unlock higher-trust rooms.",
  },
  {
    n: "02",
    icon: "🏠",
    title: "Enter a Room",
    desc: "Browse nearby rooms — devs meetup, IRL events, social lounges. Stake-gated rooms require a MON deposit to enter. Your stake comes back when you show up.",
  },
  {
    n: "03",
    icon: "🤖",
    title: "AI Finds Your Match",
    desc: "The match agent scores compatibility across 5 dimensions — shared interests, intent mode, reputation, room context, and safety. It surfaces matches, not just faces.",
  },
  {
    n: "04",
    icon: "💰",
    title: "Stake to Connect",
    desc: "Put 0.5 MON in escrow to unlock the DM channel. Both parties stake. Bad actors forfeit. Genuine conversations earn reputation and get their stake back.",
  },
  {
    n: "05",
    icon: "📍",
    title: "Attest the Meetup",
    desc: "After meeting, both parties submit GPS coordinates. Proximity verified within 100m. Confirmed meetup → stake released + reputation boosted on Hedera HCS.",
  },
  {
    n: "06",
    icon: "⭐",
    title: "Build Portable Trust",
    desc: "Your reputation score (reliability, safety, meetup rate, response rate) persists across rooms and sessions. High-trust users get lower required stakes.",
  },
];

export default function HowItWorks() {
  return (
    <section
      id="how-it-works"
      className="py-24 px-6 max-w-6xl mx-auto"
    >
      <div className="text-center mb-16">
        <div className="inline-block text-sm font-medium text-violet-400 bg-brand-violet/10 border border-brand-violet/20 px-4 py-1.5 rounded-full mb-4">
          How It Works
        </div>
        <h2 className="text-4xl md:text-5xl font-black tracking-tight">
          Skin in the game,{" "}
          <span className="text-gradient">every interaction.</span>
        </h2>
        <p className="mt-4 text-white/50 max-w-xl mx-auto text-lg">
          Every step has economic weight. Genuine actors get rewarded. Bad
          actors get slashed. The protocol enforces accountability.
        </p>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {STEPS.map((step) => (
          <div
            key={step.n}
            className="relative p-6 rounded-2xl border-gradient bg-brand-card hover:glow-violet transition-all duration-300 group"
          >
            <div className="absolute top-4 right-4 text-4xl font-black text-white/5 group-hover:text-white/10 transition-colors select-none">
              {step.n}
            </div>
            <div className="text-3xl mb-4">{step.icon}</div>
            <h3 className="font-bold text-lg mb-2">{step.title}</h3>
            <p className="text-white/55 text-sm leading-relaxed">{step.desc}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
