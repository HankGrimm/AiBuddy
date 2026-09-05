// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";
import {MonadMateEscrow} from "../src/MonadMateEscrow.sol";
import {MonadMateEventLog} from "../src/MonadMateEventLog.sol";
import {MockUSDC} from "../src/mocks/MockUSDC.sol";

/// @notice Deploys the Monad Mate contracts to Monad testnet.
///
/// Required env vars:
///   MONAD_DEPLOYER_KEY   — hex private key of the deployer / backend authority
///   MONAD_SAFETY_FUND    — address receiving slashed stakes
/// Optional:
///   MONAD_USDC_ADDRESS   — existing ERC20 to use as stake token.
///                          If unset, a MockUSDC is deployed (testnet only).
contract DeployMonadMate is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("MONAD_DEPLOYER_KEY");
        address deployer = vm.addr(deployerKey);
        address safetyFund = vm.envOr("MONAD_SAFETY_FUND", deployer);
        address usdc = vm.envOr("MONAD_USDC_ADDRESS", address(0));

        vm.startBroadcast(deployerKey);

        if (usdc == address(0)) {
            MockUSDC mock = new MockUSDC();
            mock.mint(deployer, 1_000_000_000_000); // 1,000,000 USDC
            usdc = address(mock);
            console2.log("MockUSDC deployed:", usdc);
        }

        MonadMateEscrow escrow = new MonadMateEscrow(usdc, deployer, safetyFund);
        MonadMateEventLog eventLog = new MonadMateEventLog(deployer);

        vm.stopBroadcast();

        console2.log("=== Monad Mate deploy complete ===");
        console2.log("Escrow:      ", address(escrow));
        console2.log("EventLog:    ", address(eventLog));
        console2.log("Stake token: ", usdc);
        console2.log("Safety fund: ", safetyFund);
        console2.log("");
        console2.log("Add to backend .env:");
        console2.log("MONAD_ESCROW_ADDRESS=", address(escrow));
        console2.log("MONAD_EVENT_LOG_ADDRESS=", address(eventLog));
        console2.log("MONAD_USDC_ADDRESS=", usdc);
    }
}
