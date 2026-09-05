// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {MonadMateEscrow} from "../src/MonadMateEscrow.sol";

contract MonadMateEscrowTest is Test {
    MonadMateEscrow internal escrow;

    address internal admin = address(0xA11CE);
    address internal safetyFund = address(0xFEE5);
    address internal staker = address(0xB0B);

    bytes32 internal constant ROOM_ID = keccak256("room-1");
    uint256 internal constant STAKE_AMOUNT = 5 ether; // 5 MON

    function setUp() public {
        escrow = new MonadMateEscrow(admin, safetyFund);
        vm.deal(staker, 100 ether);
    }

    function _stake() internal {
        vm.prank(staker);
        escrow.stake{value: STAKE_AMOUNT}(ROOM_ID, MonadMateEscrow.StakeType.MatchRequest);
    }

    function test_stake_holdsFundsAndRecordsVault() public {
        _stake();

        assertEq(address(escrow).balance, STAKE_AMOUNT);
        assertEq(escrow.totalStaked(), STAKE_AMOUNT);

        MonadMateEscrow.StakeVault memory vault = escrow.getStake(staker, ROOM_ID);
        assertEq(vault.staker, staker);
        assertEq(vault.amount, STAKE_AMOUNT);
        assertEq(uint8(vault.status), uint8(MonadMateEscrow.StakeStatus.Active));
    }

    function test_stake_revertsOnZeroAmount() public {
        vm.prank(staker);
        vm.expectRevert(MonadMateEscrow.ZeroStakeAmount.selector);
        escrow.stake{value: 0}(ROOM_ID, MonadMateEscrow.StakeType.RoomEntry);
    }

    function test_stake_revertsOnDuplicate() public {
        _stake();
        vm.prank(staker);
        vm.expectRevert(MonadMateEscrow.StakeAlreadyExists.selector);
        escrow.stake{value: STAKE_AMOUNT}(ROOM_ID, MonadMateEscrow.StakeType.RoomEntry);
    }

    function test_stake_directTransferRejected() public {
        vm.prank(staker);
        (bool ok,) = address(escrow).call{value: STAKE_AMOUNT}("");
        assertFalse(ok, "receive() must reject bare transfers");
        assertEq(address(escrow).balance, 0);
    }

    function test_refund_returnsFullStake() public {
        _stake();
        uint256 before = staker.balance;

        vm.prank(admin);
        escrow.refund(staker, ROOM_ID);

        assertEq(staker.balance - before, STAKE_AMOUNT);
        assertEq(address(escrow).balance, 0);
        assertEq(escrow.totalRefunded(), STAKE_AMOUNT);
        assertEq(
            uint8(escrow.getStake(staker, ROOM_ID).status), uint8(MonadMateEscrow.StakeStatus.Refunded)
        );
    }

    function test_refund_onlyAdmin() public {
        _stake();
        vm.prank(staker);
        vm.expectRevert(MonadMateEscrow.Unauthorized.selector);
        escrow.refund(staker, ROOM_ID);
    }

    function test_refund_revertsIfNotActive() public {
        _stake();
        vm.startPrank(admin);
        escrow.refund(staker, ROOM_ID);
        vm.expectRevert(MonadMateEscrow.InvalidStakeStatus.selector);
        escrow.refund(staker, ROOM_ID);
        vm.stopPrank();
    }

    function test_slash_splitsBetweenSafetyFundAndStaker() public {
        _stake();
        uint256 before = staker.balance;

        vm.prank(admin);
        escrow.slash(staker, ROOM_ID, 5_000, MonadMateEscrow.SlashReason.NoShow);

        assertEq(safetyFund.balance, STAKE_AMOUNT / 2);
        assertEq(staker.balance - before, STAKE_AMOUNT / 2);
        assertEq(address(escrow).balance, 0);
        assertEq(escrow.totalSlashed(), STAKE_AMOUNT / 2);
        assertEq(
            uint8(escrow.getStake(staker, ROOM_ID).status), uint8(MonadMateEscrow.StakeStatus.Slashed)
        );
    }

    function test_slash_fullSlash() public {
        _stake();
        vm.prank(admin);
        escrow.slash(staker, ROOM_ID, 10_000, MonadMateEscrow.SlashReason.Fraud);
        assertEq(safetyFund.balance, STAKE_AMOUNT);
    }

    function test_slash_revertsOnInvalidBps() public {
        _stake();
        vm.prank(admin);
        vm.expectRevert(MonadMateEscrow.InvalidSlashBps.selector);
        escrow.slash(staker, ROOM_ID, 10_001, MonadMateEscrow.SlashReason.NoShow);
    }

    function test_transferAdmin() public {
        vm.prank(admin);
        escrow.transferAdmin(address(0xCAFE));
        assertEq(escrow.admin(), address(0xCAFE));
    }
}
