// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title Monad Mate Event Log
/// @notice Replaces the SPL Memo program used on the previous Solana deployment.
///         The backend writes stake/refund/slash records here so every decision
///         produces a real, explorer-visible transaction without requiring the
///         full ERC20 escrow flow to be wired up.
/// @dev Payloads are opaque UTF-8 JSON strings. Indexed `eventType` and
///      `refId` make records cheap to filter from an RPC log query.
contract MonadMateEventLog {
    /// @notice Addresses allowed to write records.
    mapping(address => bool) public writers;

    address public admin;

    /// @notice Monotonic counter — useful as a cursor when replaying logs.
    uint256 public recordCount;

    event RecordWritten(
        uint256 indexed sequence,
        bytes32 indexed eventType,
        bytes32 indexed refId,
        address writer,
        string payload
    );
    event WriterUpdated(address indexed writer, bool allowed);
    event AdminTransferred(address indexed previousAdmin, address indexed newAdmin);

    error Unauthorized();
    error ZeroAddress();
    error EmptyPayload();

    constructor(address admin_) {
        if (admin_ == address(0)) revert ZeroAddress();
        admin = admin_;
        writers[admin_] = true;
        emit WriterUpdated(admin_, true);
    }

    modifier onlyAdmin() {
        if (msg.sender != admin) revert Unauthorized();
        _;
    }

    function setWriter(address writer, bool allowed) external onlyAdmin {
        if (writer == address(0)) revert ZeroAddress();
        writers[writer] = allowed;
        emit WriterUpdated(writer, allowed);
    }

    function transferAdmin(address newAdmin) external onlyAdmin {
        if (newAdmin == address(0)) revert ZeroAddress();
        emit AdminTransferred(admin, newAdmin);
        admin = newAdmin;
    }

    /// @notice Write one record.
    /// @param eventType Short tag, e.g. keccak-free `bytes32("stake")`.
    /// @param refId Off-chain identifier this record refers to (stake id, etc).
    /// @param payload JSON-encoded event body.
    function write(bytes32 eventType, bytes32 refId, string calldata payload) external returns (uint256 sequence) {
        if (!writers[msg.sender]) revert Unauthorized();
        if (bytes(payload).length == 0) revert EmptyPayload();

        sequence = ++recordCount;
        emit RecordWritten(sequence, eventType, refId, msg.sender, payload);
    }
}
