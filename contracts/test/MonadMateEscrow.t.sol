// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {MonadMateEscrow} from "../src/MonadMateEscrow.sol";
import {MockUSDC} from "../src/mocks/MockUSDC.sol";

contract MonadMateEscrowTest is Test {
    MonadMateEscrow internal escrow;
    MockUSDC internal usdc;

    address internal admin = address(0xA11CE);
    address internal safetyFund = address(0xFEE5);
    address internal staker = address(0xB0B);

    bytes32 internal constant ROOM_ID = keccak256("room-1");
    uint256 internal constant STAKE_AMOUNT = 5_000_000; // 5 USDC (6 decimals)

    function setUp() public {
        usdc = new MockUSDC();
        escrow = new MonadMateEscrow(address(usdc), admin, safetyFund);

        usdc.mint(staker, 100_000_000);
        vm.prank(staker);
        usdc.approve(address(escrow), type(uint256).max);
    }

    function _stake() internal {
        vm.prank(staker);
        escrow.stake(ROOM_ID, STAKE_AMOUNT, MonadMateEscrow.StakeType.MatchRequest);
    }

    function test_stake_movesFundsAndRecordsVault() public {
        _stake();

        assertEq(usdc.balanceOf(address(escrow)), STAKE_AMOUNT);
        assertEq(escrow.totalStaked(), STAKE_AMOUNT);

        MonadMateEscrow.StakeVault memory vault = escrow.getStake(staker, ROOM_ID);
        assertEq(vault.staker, staker);
        assertEq(vault.amount, STAKE_AMOUNT);
        assertEq(uint8(vault.status), uint8(MonadMateEscrow.StakeStatus.Active));
    }

    function test_stake_revertsOnZeroAmount() public {
        vm.prank(staker);
        vm.expectRevert(MonadMateEscrow.ZeroStakeAmount.selector);
        escrow.stake(ROOM_ID, 0, MonadMateEscrow.StakeType.RoomEntry);
    }

    function test_stake_revertsOnDuplicate() public {
        _stake();
        vm.prank(staker);
        vm.expectRevert(MonadMateEscrow.StakeAlreadyExists.selector);
        escrow.stake(ROOM_ID, STAKE_AMOUNT, MonadMateEscrow.StakeType.RoomEntry);
    }

    function test_refund_returnsFullStake() public {
        _stake();
        uint256 before = usdc.balanceOf(staker);

        vm.prank(admin);
        escrow.refund(staker, ROOM_ID);

        assertEq(usdc.balanceOf(staker) - before, STAKE_AMOUNT);
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
        uint256 before = usdc.balanceOf(staker);

        vm.prank(admin);
        escrow.slash(staker, ROOM_ID, 5_000, MonadMateEscrow.SlashReason.NoShow);

        assertEq(usdc.balanceOf(safetyFund), STAKE_AMOUNT / 2);
        assertEq(usdc.balanceOf(staker) - before, STAKE_AMOUNT / 2);
        assertEq(escrow.totalSlashed(), STAKE_AMOUNT / 2);
        assertEq(
            uint8(escrow.getStake(staker, ROOM_ID).status), uint8(MonadMateEscrow.StakeStatus.Slashed)
        );
    }

    function test_slash_fullSlash() public {
        _stake();
        vm.prank(admin);
        escrow.slash(staker, ROOM_ID, 10_000, MonadMateEscrow.SlashReason.Fraud);
        assertEq(usdc.balanceOf(safetyFund), STAKE_AMOUNT);
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
