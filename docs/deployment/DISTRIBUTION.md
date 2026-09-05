# Distribution Guide — PWA + Android APK

Monad Mate ships as a Web3 dApp. There is no app-store dependency: users open it in
any browser, install it to the home screen as a PWA, or sideload the Android build.

---

## Option 1: Web dApp (default)

Nothing to distribute — the deployed URL is the product.

```
https://monad-mate-trust-api-production.up.railway.app
```

Users connect MetaMask or Rabby on Monad testnet (chain id `10143`) and sign the
EIP-191 login challenge.

---

## Option 2: Progressive Web App (Add to Home Screen)

The landing app already serves `landing/public/manifest.json`.

Checklist for a fully installable PWA:

- [x] `public/manifest.json` with `display: "standalone"`
- [x] `<link rel="manifest">` wired via `app/layout.tsx` metadata
- [x] HTTPS (satisfied by the Railway deployment)
- [ ] `public/service-worker.js` for offline caching
- [ ] 512×512 app icon at `public/icon-512.png`

Install flow for users:

1. Open the site in a mobile browser
2. Menu → "Add to Home Screen"
3. Launches standalone, no install prompt from any store

---

## Option 3: Android APK sideload

For testers and internal builds.

```bash
# On the device: Settings → Security → allow install from unknown sources
adb install monad-mate.apk
```

Or share a direct link:

```
https://monad-mate-trust-api-production.up.railway.app/download/monad-mate.apk
```

Recommended APK metadata:

- Package name: `studio.ainative.monadmate`
- Minimum SDK: 26
- Categories: Social, Lifestyle

---

## Store assets (if a store listing is added later)

```
dist/
  icon.png              # 512x512 PNG
  screenshot_1.png      # 1080x2340 — match discovery
  screenshot_2.png      # 1080x2340 — stake-to-connect flow
  screenshot_3.png      # 1080x2340 — GPS meetup attestation
  feature_graphic.png   # 1024x500 banner (optional)
```

Copy to reuse:

- Name: **Monad Mate**
- Tagline: Stake MON to DM, match, and meet.
- Short description: Stake-to-interact social app. Skin in the game replaces swipe culture.
- Long description: Monad Mate is a stake-to-interact social app where economic
  accountability replaces swipe culture. Stake MON to enter rooms, request matches,
  and unlock DMs. Genuine meetups release your stake. No-shows get slashed.
  AI matchmaking. GPS attestation. Hedera HCS audit trail.

---

## Notes

The previous Solana build targeted the Seeker dApp Store, which listed apps as
on-chain NFTs on Solana mainnet. Monad has no equivalent first-party store, so
distribution is PWA-first with an APK fallback.
