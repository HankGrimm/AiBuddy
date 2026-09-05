const API_URL = "/api";
const GITHUB_URL = "https://github.com/HankGrimm/monad-mate-trust-api";

export default function Download() {
  return (
    <section
      id="download"
      className="py-24 px-6 bg-gradient-to-b from-transparent to-brand-card/30"
    >
      <div className="max-w-4xl mx-auto text-center">
        <div className="inline-block text-sm font-medium text-pink-400 bg-brand-pink/10 border border-brand-pink/20 px-4 py-1.5 rounded-full mb-6">
          Get Monad Mate
        </div>
        <h2 className="text-4xl md:text-5xl font-black tracking-tight mb-6">
          Ready to connect{" "}
          <span className="text-gradient">with skin in the game?</span>
        </h2>
        <p className="text-white/50 text-lg max-w-xl mx-auto mb-12">
          Monad Mate is a Web3 dApp — no app store required. Open in any browser
          or install it to your home screen.
        </p>

        <div className="grid sm:grid-cols-3 gap-6 mb-12">
          {/* Option 1: Web dApp */}
          <div className="p-6 rounded-2xl border-gradient bg-brand-card flex flex-col items-center gap-4 hover:glow-violet transition-all">
            <div className="text-4xl">🌐</div>
            <h3 className="font-bold text-lg">Web dApp</h3>
            <p className="text-white/50 text-sm text-center">
              Open in any browser. Connect MetaMask or Rabby. No install
              needed.
            </p>
            <a
              href={API_URL + "/docs"}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-auto w-full py-3 rounded-xl bg-cta-gradient text-white font-semibold text-sm text-center hover:opacity-90 transition-opacity"
            >
              Open Live API →
            </a>
          </div>

          {/* Option 2: Android APK sideload */}
          <div className="p-6 rounded-2xl border border-brand-violet/30 bg-brand-card/50 flex flex-col items-center gap-4 relative overflow-hidden">
            <div className="absolute top-3 right-3 text-xs px-2 py-1 rounded-full bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
              Coming Soon
            </div>
            <div className="text-4xl">📱</div>
            <h3 className="font-bold text-lg">Android APK</h3>
            <p className="text-white/50 text-sm text-center">
              Sideload build for testers. Same dApp, packaged for Android.
            </p>
            <div className="mt-auto w-full py-3 rounded-xl bg-white/5 border border-white/10 text-white/40 font-semibold text-sm text-center cursor-not-allowed">
              Available after review
            </div>
          </div>

          {/* Option 3: PWA / Add to Home Screen */}
          <div className="p-6 rounded-2xl border-gradient bg-brand-card flex flex-col items-center gap-4 hover:glow-violet transition-all">
            <div className="text-4xl">💾</div>
            <h3 className="font-bold text-lg">Install as PWA</h3>
            <p className="text-white/50 text-sm text-center">
              Open in mobile browser → "Add to Home Screen" for a native-like
              experience.
            </p>
            <a
              href={API_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-auto w-full py-3 rounded-xl border border-brand-violet/50 text-white/80 font-semibold text-sm text-center hover:border-brand-violet hover:text-white transition-all"
            >
              Open on Mobile →
            </a>
          </div>
        </div>

        {/* Wallet compatibility */}
        <div className="p-6 rounded-2xl bg-brand-card/50 border border-brand-border inline-block">
          <div className="text-sm text-white/50 mb-3">
            Supported wallets & networks
          </div>
          <div className="flex flex-wrap justify-center gap-4 text-sm">
            {[
              "🟣 MetaMask",
              "🔵 Rabby",
              "⚡ Monad Testnet",
              "🔵 Base Mainnet",
              "🌐 Any Web3 Browser",
            ].map((w) => (
              <span key={w} className="text-white/70">
                {w}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
