# Monad Mate Contracts

Solidity contracts for the Monad Mate trust layer, built with [Foundry](https://book.getfoundry.sh/).

## Contracts

- `src/MonadMateEscrow.sol` — stake-to-interact escrow. Users stake USDC against a
  room/match; the backend authority refunds on a confirmed meetup or slashes on
  no-show/harassment (slashed share goes to the safety fund).
- `src/MonadMateEventLog.sol` — append-only event log. The backend writes
  stake/refund/slash records here so each decision produces an explorer-visible
  transaction. Replaces the SPL Memo program used in the earlier Solana build.
- `src/mocks/MockUSDC.sol` — 6-decimal ERC20 stand-in for USDC on testnet.

## Setup

```bash
curl -L https://foundry.paradigm.xyz | bash && foundryup
cd contracts
forge install foundry-rs/forge-std
forge build
forge test
```

## Deploy to Monad testnet

```bash
export MONAD_RPC_URL=https://testnet-rpc.monad.xyz
export MONAD_DEPLOYER_KEY=0x...        # backend authority key
export MONAD_SAFETY_FUND=0x...         # optional, defaults to deployer
export MONAD_USDC_ADDRESS=0x...        # optional, deploys MockUSDC if unset
bash scripts/deploy_testnet.sh
```

The script prints the `MONAD_ESCROW_ADDRESS`, `MONAD_EVENT_LOG_ADDRESS` and
`MONAD_USDC_ADDRESS` values to copy into the backend `.env`.

## Notes

- Monad is EVM-equivalent, so no chain-specific opcodes or precompiles are used.
- Chain id: `10143` (testnet). Explorer: https://testnet.monadexplorer.com
- The backend must hold the `admin` key: only `admin` can call `refund` / `slash`,
  and only allow-listed writers can append to the event log.
