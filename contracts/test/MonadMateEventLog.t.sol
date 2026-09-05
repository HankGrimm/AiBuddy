// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {MonadMateEventLog} from "../src/MonadMateEventLog.sol";

contract MonadMateEventLogTest is Test {
    MonadMateEventLog internal log;

    address internal admin = address(0xA11CE);
    address internal backend = address(0xB4CE);

    function setUp() public {
        log = new MonadMateEventLog(admin);
    }

    function test_adminIsWriterByDefault() public {
        assertTrue(log.writers(admin));
    }

    function test_write_incrementsSequence() public {
        vm.startPrank(admin);
        uint256 first = log.write(bytes32("stake"), bytes32("ref-1"), "{\"event\":\"stake\"}");
        uint256 second = log.write(bytes32("refund"), bytes32("ref-1"), "{\"event\":\"refund\"}");
        vm.stopPrank();

        assertEq(first, 1);
        assertEq(second, 2);
        assertEq(log.recordCount(), 2);
    }

    function test_write_rejectsUnknownWriter() public {
        vm.prank(backend);
        vm.expectRevert(MonadMateEventLog.Unauthorized.selector);
        log.write(bytes32("stake"), bytes32("ref-1"), "{}");
    }

    function test_setWriter_grantsAccess() public {
        vm.prank(admin);
        log.setWriter(backend, true);

        vm.prank(backend);
        assertEq(log.write(bytes32("slash"), bytes32("ref-2"), "{}"), 1);
    }

    function test_write_rejectsEmptyPayload() public {
        vm.prank(admin);
        vm.expectRevert(MonadMateEventLog.EmptyPayload.selector);
        log.write(bytes32("stake"), bytes32("ref-1"), "");
    }
}
