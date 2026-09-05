// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "./interfaces/IERC20.sol";

/// @title Monad Mate Safety Escrow
/// @notice Implements stake-to-interact mechanics for social trust:
///         1. User stakes USDC into the escrow contract
///         2. On meetup confirmation, stake is refunded
///         3. On no-show/harassment, stake is slashed and sent to the safety fund
///         4. Backend authority (Monad Mate API) controls release/slash decisions
contract MonadMateEscrow {
    // -----------------------------------------------------------------------
    // Types
    // -----------------------------------------------------------------------

    enum StakeType {
        RoomEntry, // Entering a stake-gated room
        MatchRequest, // Initiating a match
        DmUnlock // Unlocking DM channel
    }

    enum StakeStatus {
        None,
        Active,
        Refunded,
        Slashed,
        Disputed
    }

    enum SlashReason {
        NoShow,
        Harassment,
        FalseReport,
        Fraud,
        ContentViolation
    }

    struct StakeVault {
        address staker;
        bytes32 roomId;
        uint256 amount;
        StakeType stakeType;
        StakeStatus status;
        uint64 createdAt;
        uint64 resolvedAt;
    }

    // -----------------------------------------------------------------------
    // Storage
    // -----------------------------------------------------------------------

    /// @notice Backend authority allowed to refund/slash stakes.
    address public admin;

    /// @notice Destination for slashed funds.
    address public safetyFund;

    /// @notice USDC (or any ERC20) used as the stake asset.
    IERC20 public immutable stakeToken;

    uint256 public totalStaked;
    uint256 public totalSlashed;
    uint256 public totalRefunded;

    /// @dev keccak256(staker, roomId) => vault. Mirrors the PDA keying of the
    ///      original Solana program so backend call sites stay unchanged.
    mapping(bytes32 => StakeVault) private _vaults;

    // -----------------------------------------------------------------------
    // Events
    // -----------------------------------------------------------------------

    event AuthorityInitialized(address indexed admin, address indexed safetyFund);
    event AdminTransferred(address indexed previousAdmin, address indexed newAdmin);
    event SafetyFundUpdated(address indexed previousFund, address indexed newFund);
    event StakeDeposited(address indexed staker, bytes32 indexed roomId, uint256 amount, StakeType stakeType);
    event StakeRefunded(address indexed staker, bytes32 indexed roomId, uint256 amount);
    event StakeSlashed(
        address indexed staker,
        bytes32 indexed roomId,
        uint256 slashAmount,
        uint256 refundAmount,
        uint16 slashBps,
        SlashReason reason
    );

    // -----------------------------------------------------------------------
    // Errors
    // -----------------------------------------------------------------------

    error ZeroStakeAmount();
    error InsufficientBalance();
    error InvalidStakeStatus();
    error InvalidSlashBps();
    error Unauthorized();
    error StakeAlreadyExists();
    error ZeroAddress();
    error TransferFailed();

    // -----------------------------------------------------------------------
    // Construction
    // -----------------------------------------------------------------------

    constructor(address stakeToken_, address admin_, address safetyFund_) {
        if (stakeToken_ == address(0) || admin_ == address(0) || safetyFund_ == address(0)) {
            revert ZeroAddress();
        }
        stakeToken = IERC20(stakeToken_);
        admin = admin_;
        safetyFund = safetyFund_;
        emit AuthorityInitialized(admin_, safetyFund_);
    }

    modifier onlyAdmin() {
        if (msg.sender != admin) revert Unauthorized();
        _;
    }

    // -----------------------------------------------------------------------
    // Admin
    // -----------------------------------------------------------------------

    function transferAdmin(address newAdmin) external onlyAdmin {
        if (newAdmin == address(0)) revert ZeroAddress();
        emit AdminTransferred(admin, newAdmin);
        admin = newAdmin;
    }

    function setSafetyFund(address newFund) external onlyAdmin {
        if (newFund == address(0)) revert ZeroAddress();
        emit SafetyFundUpdated(safetyFund, newFund);
        safetyFund = newFund;
    }

    // -----------------------------------------------------------------------
    // Staking
    // -----------------------------------------------------------------------

    /// @notice Stake USDC into escrow for a room interaction.
    /// @dev Caller must have approved this contract for at least `amount`.
    function stake(bytes32 roomId, uint256 amount, StakeType stakeType) external {
        if (amount == 0) revert ZeroStakeAmount();
        if (stakeToken.balanceOf(msg.sender) < amount) revert InsufficientBalance();

        bytes32 key = vaultKey(msg.sender, roomId);
        if (_vaults[key].status != StakeStatus.None) revert StakeAlreadyExists();

        _vaults[key] = StakeVault({
            staker: msg.sender,
            roomId: roomId,
            amount: amount,
            stakeType: stakeType,
            status: StakeStatus.Active,
            createdAt: uint64(block.timestamp),
            resolvedAt: 0
        });

        totalStaked += amount;

        _pullToken(msg.sender, amount);

        emit StakeDeposited(msg.sender, roomId, amount, stakeType);
    }

    /// @notice Refund a stake after a successful meetup attestation.
    function refund(address staker, bytes32 roomId) external onlyAdmin {
        bytes32 key = vaultKey(staker, roomId);
        StakeVault storage vault = _vaults[key];
        if (vault.status != StakeStatus.Active) revert InvalidStakeStatus();

        uint256 amount = vault.amount;
        vault.status = StakeStatus.Refunded;
        vault.resolvedAt = uint64(block.timestamp);
        totalRefunded += amount;

        _pushToken(staker, amount);

        emit StakeRefunded(staker, roomId, amount);
    }

    /// @notice Slash a stake for no-show, harassment, or fraud.
    /// @param slashBps Basis points to slash (e.g. 5000 = 50%). Slashed funds go
    ///        to `safetyFund`; the remainder is returned to the staker.
    function slash(address staker, bytes32 roomId, uint16 slashBps, SlashReason reason) external onlyAdmin {
        if (slashBps > 10_000) revert InvalidSlashBps();

        bytes32 key = vaultKey(staker, roomId);
        StakeVault storage vault = _vaults[key];
        if (vault.status != StakeStatus.Active) revert InvalidStakeStatus();

        uint256 total = vault.amount;
        uint256 slashAmount = (total * slashBps) / 10_000;
        uint256 refundAmount = total - slashAmount;

        vault.status = StakeStatus.Slashed;
        vault.resolvedAt = uint64(block.timestamp);
        totalSlashed += slashAmount;

        if (slashAmount > 0) _pushToken(safetyFund, slashAmount);
        if (refundAmount > 0) _pushToken(staker, refundAmount);

        emit StakeSlashed(staker, roomId, slashAmount, refundAmount, slashBps, reason);
    }

    // -----------------------------------------------------------------------
    // Views
    // -----------------------------------------------------------------------

    function vaultKey(address staker, bytes32 roomId) public pure returns (bytes32) {
        return keccak256(abi.encodePacked("stake_vault", staker, roomId));
    }

    function getStake(address staker, bytes32 roomId) external view returns (StakeVault memory) {
        return _vaults[vaultKey(staker, roomId)];
    }

    // -----------------------------------------------------------------------
    // Internal
    // -----------------------------------------------------------------------

    function _pullToken(address from, uint256 amount) private {
        if (!stakeToken.transferFrom(from, address(this), amount)) revert TransferFailed();
    }

    function _pushToken(address to, uint256 amount) private {
        if (!stakeToken.transfer(to, amount)) revert TransferFailed();
    }
}
