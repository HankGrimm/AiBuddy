const GITHUB_URL = "https://github.com/HankGrimm/monad-mate-trust-api";
const API_URL = "https://monad-mate-trust-api-production.up.railway.app";

export default function Footer() {
  return (
    <footer className="border-t border-brand-border py-12 px-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6 mb-8">
          <div className="flex items-center gap-2">
            <span className="text-2xl">💜</span>
            <span className="font-bold text-lg tracking-tight">
              Sol<span className="text-gradient">Mate</span>
            </span>
          </div>

          <div className="flex flex-wrap justify-center gap-6 text-sm text-white/50">
            <a
              href={API_URL + "/docs"}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-white transition-colors"
            >
              API Docs
            </a>
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-white transition-colors"
            >
              GitHub
            </a>
            <a
              href={GITHUB_URL + "/blob/main/CONTRIBUTING.md"}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-white transition-colors"
            >
              Contributing
            </a>
            <a
              href={GITHUB_URL + "/blob/main/LICENSE"}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-white transition-colors"
            >
              MIT License
            </a>
          </div>
        </div>

        <div className="flex flex-col md:flex-row items-center justify-between gap-4 pt-6 border-t border-brand-border text-xs text-white/30">
          <span>
            Built for EasyA × Consensus Miami 2026 · Monad + Hedera + Base
          </span>
          <span>
            API:{" "}
            <a
              href={API_URL + "/health"}
              target="_blank"
              rel="noopener noreferrer"
              className="text-green-400 hover:underline"
            >
              Live ↗
            </a>
          </span>
        </div>
      </div>
    </footer>
  );
}
