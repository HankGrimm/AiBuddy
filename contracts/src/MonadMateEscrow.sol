// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title Monad Mate Safety Escrow
/// @notice Implements stake-to-interact mechanics for social trust:
///         1. User stakes native MON into the escrow contract
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

    /// @notice Destination for slashed MON.
    address public safetyFund;

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
    error InvalidStakeStatus();
    error InvalidSlashBps();
    error Unauthorized();
    error StakeAlreadyExists();
    error ZeroAddress();
    error NativeTransferFailed();
    error DirectTransferRejected();

    // -----------------------------------------------------------------------
    // Construction
    // -----------------------------------------------------------------------

    constructor(address admin_, address safetyFund_) {
        if (admin_ == address(0) || safetyFund_ == address(0)) {
            revert ZeroAddress();
        }
        admin = admin_;
        safetyFund = safetyFund_;
        emit AuthorityInitialized(admin_, safetyFund_);
    }

    modifier onlyAdmin() {
        if (msg.sender != admin) revert Unauthorized();
        _;
    }

    receive() external payable {
        revert DirectTransferRejected(); // funds must enter through stake()
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

    /// @notice Stake native MON into escrow for a room interaction.
    /// @dev The staked amount is `msg.value`.
    function stake(bytes32 roomId, StakeType stakeType) external payable {
        uint256 amount = msg.value;
        if (amount == 0) revert ZeroStakeAmount();

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

        _sendMon(staker, amount);

        emit StakeRefunded(staker, roomId, amount);
    }

    /// @notice Slash a stake for no-show, harassment, or fraud.
    /// @param slashBps Basis points to slash (e.g. 5000 = 50%). Slashed MON goes
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

        if (slashAmount > 0) _sendMon(safetyFund, slashAmount);
        if (refundAmount > 0) _sendMon(staker, refundAmount);

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

    /// @dev State is always updated before this runs (checks-effects-interactions).
    function _sendMon(address to, uint256 amount) private {
        (bool success,) = to.call{value: amount}("");
        if (!success) revert NativeTransferFailed();
    }
}
