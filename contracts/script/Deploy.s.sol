// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";
import {MonadMateEscrow} from "../src/MonadMateEscrow.sol";
import {MonadMateEventLog} from "../src/MonadMateEventLog.sol";

/// @notice Deploys the Monad Mate contracts to Monad testnet.
///
/// Stakes are held in native MON — no ERC20 wiring is required.
///
/// Required env vars:
///   MONAD_DEPLOYER_KEY   — hex private key of the deployer / backend authority
///   MONAD_SAFETY_FUND    — address receiving slashed stakes (optional,
///                          defaults to the deployer)
contract DeployMonadMate is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("MONAD_DEPLOYER_KEY");
        address deployer = vm.addr(deployerKey);
        address safetyFund = vm.envOr("MONAD_SAFETY_FUND", deployer);

        vm.startBroadcast(deployerKey);

        MonadMateEscrow escrow = new MonadMateEscrow(deployer, safetyFund);
        MonadMateEventLog eventLog = new MonadMateEventLog(deployer);

        vm.stopBroadcast();

        console2.log("=== Monad Mate deploy complete ===");
        console2.log("Escrow:      ", address(escrow));
        console2.log("EventLog:    ", address(eventLog));
        console2.log("Stake asset: ", "native MON");
        console2.log("Safety fund: ", safetyFund);
        console2.log("");
        console2.log("Add to backend .env:");
        console2.log("MONAD_ESCROW_ADDRESS=", address(escrow));
        console2.log("MONAD_EVENT_LOG_ADDRESS=", address(eventLog));
    }
}
