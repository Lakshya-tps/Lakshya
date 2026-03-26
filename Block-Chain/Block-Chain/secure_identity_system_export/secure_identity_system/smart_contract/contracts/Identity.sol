// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract IdentityRegistry {
    address public owner;
    mapping(bytes32 => bytes32) private identities;

    event IdentityStored(bytes32 indexed userKey, bytes32 identityHash);

    constructor() {
        owner = msg.sender;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can update identities");
        _;
    }

    function setIdentity(bytes32 userKey, bytes32 identityHash) external onlyOwner {
        identities[userKey] = identityHash;
        emit IdentityStored(userKey, identityHash);
    }

    function getIdentity(bytes32 userKey) external view returns (bytes32) {
        return identities[userKey];
    }
}
