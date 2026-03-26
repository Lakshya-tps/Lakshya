import json
import logging
import os
from pathlib import Path

from web3 import Web3

GANACHE_URL = os.getenv("GANACHE_URL", "http://127.0.0.1:7545")
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", ZERO_ADDRESS)

FALLBACK_CONTRACT_ABI = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "userKey", "type": "bytes32"},
            {"internalType": "bytes32", "name": "identityHash", "type": "bytes32"},
        ],
        "name": "setIdentity",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "userKey", "type": "bytes32"}],
        "name": "getIdentity",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "owner",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def _load_contract_abi() -> list:
    """
    Load ABI from Hardhat artifacts if available; otherwise fall back to a minimal ABI.
    """
    try:
        root_dir = Path(__file__).resolve().parents[1]
        artifact_path = (
            root_dir
            / "smart_contract"
            / "artifacts"
            / "contracts"
            / "Identity.sol"
            / "IdentityRegistry.json"
        )
        if artifact_path.exists():
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            abi = payload.get("abi")
            if isinstance(abi, list) and abi:
                return abi
    except Exception:
        pass
    return FALLBACK_CONTRACT_ABI


class BlockchainClient:
    def __init__(self, rpc_url=GANACHE_URL, contract_address=CONTRACT_ADDRESS):
        self.rpc_url = rpc_url
        self.contract_address = contract_address
        self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
        self.abi = _load_contract_abi()
        self.contract = None
        self.account = None
        self.owner = None
        self.last_error = None
        self.deployed = False
        self.write_ready = False
        self.chain_id = None
        self.block_number = None
        self._connect()

    def _update_from_env(self):
        self.rpc_url = os.getenv("GANACHE_URL", self.rpc_url)
        self.contract_address = os.getenv("CONTRACT_ADDRESS", self.contract_address)

    def _connect(self):
        logger = logging.getLogger(__name__)
        try:
            logger.info("Blockchain connect attempt rpc_url=%s contract=%s", self.rpc_url, self.contract_address)
            self.deployed = False
            self.chain_id = None
            self.block_number = None
            self.write_ready = False
            self.owner = None

            if not self.web3.is_connected():
                self.last_error = "RPC connection unavailable."
                self.contract = None
                self.account = None
                return
            if self.contract_address == ZERO_ADDRESS:
                self.last_error = "Contract address not configured."
                self.contract = None
                self.account = None
                return

            checksum_address = Web3.to_checksum_address(self.contract_address)
            code = self.web3.eth.get_code(checksum_address)
            self.deployed = bool(code) and len(code) > 0
            if not self.deployed:
                self.last_error = "No contract bytecode found at CONTRACT_ADDRESS. Deploy the contract to this RPC network."
                self.contract = None
                self.account = None
                return

            accounts = self.web3.eth.accounts
            if not accounts:
                self.last_error = "No blockchain accounts available."
                self.contract = None
                self.account = None
                return

            index_raw = os.getenv("BLOCKCHAIN_ACCOUNT_INDEX", "0")
            try:
                index = int(str(index_raw).strip())
            except Exception:
                index = 0
            if index < 0 or index >= len(accounts):
                self.last_error = (
                    f"BLOCKCHAIN_ACCOUNT_INDEX={index} is out of range for this RPC node. "
                    f"Available accounts: {len(accounts)}."
                )
                self.contract = None
                self.account = None
                return

            self.account = accounts[index]
            self.contract = self.web3.eth.contract(address=checksum_address, abi=self.abi)
            try:
                self.chain_id = int(self.web3.eth.chain_id)
            except Exception:
                self.chain_id = None
            try:
                self.block_number = int(self.web3.eth.block_number)
            except Exception:
                self.block_number = None

            write_ready = True
            try:
                owner = self.contract.functions.owner().call()
                if isinstance(owner, str) and owner:
                    self.owner = owner
                    if owner.lower() != self.account.lower():
                        write_ready = False
                        self.last_error = (
                            "Connected, but the selected signer account does not match the contract owner. "
                            "Deploy the contract from account[0] or set BLOCKCHAIN_ACCOUNT_INDEX to the deployer index."
                        )
            except Exception:
                pass
            self.write_ready = write_ready
            if write_ready:
                self.last_error = None

            logger.info(
                "Blockchain ready rpc_url=%s contract=%s account=%s chain_id=%s block=%s",
                self.rpc_url,
                self.contract_address,
                self.account,
                self.chain_id,
                self.block_number,
            )
        except Exception as exc:
            self.contract = None
            self.account = None
            self.last_error = str(exc)

    def refresh(self):
        self._update_from_env()
        self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
        self.contract = None
        self.account = None
        self._connect()

    def is_ready(self):
        return self.web3.is_connected() and self.contract is not None and self.account is not None

    def status(self):
        prev_rpc = self.rpc_url
        prev_address = self.contract_address
        self._update_from_env()
        if self.rpc_url != prev_rpc:
            self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
            self.contract = None
            self.account = None
        elif self.contract_address != prev_address:
            self.contract = None
            self.account = None

        connected = False
        try:
            connected = self.web3.is_connected()
        except Exception as exc:
            self.last_error = str(exc)

        configured = self.contract_address != ZERO_ADDRESS
        if connected and configured and self.contract is None:
            self._connect()

        return {
            "ready": self.is_ready(),
            "connected": connected,
            "configured": configured,
            "rpc_url": self.rpc_url,
            "contract_address": None if not configured else self.contract_address,
            "account": self.account,
            "deployed": bool(self.deployed),
            "write_ready": bool(self.write_ready),
            "owner": self.owner,
            "chain_id": self.chain_id,
            "block_number": self.block_number,
            "last_error": self.last_error,
        }

    def store_identity(self, user_key_hex, identity_hash_hex):
        if not self.is_ready():
            self.refresh()
        if not self.is_ready() or not self.write_ready:
            return None
        try:
            user_key = Web3.to_bytes(hexstr=user_key_hex)
            identity_hash = Web3.to_bytes(hexstr=identity_hash_hex)
            tx_hash = self.contract.functions.setIdentity(user_key, identity_hash).transact(
                {"from": self.account}
            )
            self.last_error = None
            return tx_hash.hex()
        except Exception as exc:
            self.last_error = str(exc)
            return None

    def get_identity(self, user_key_hex):
        if not self.is_ready():
            self.refresh()
        if not self.is_ready():
            return None
        try:
            user_key = Web3.to_bytes(hexstr=user_key_hex)
            identity_hash = self.contract.functions.getIdentity(user_key).call()
            if isinstance(identity_hash, (bytes, bytearray)):
                if identity_hash == b"\x00" * 32:
                    return None
                return Web3.to_hex(identity_hash)
            return None
        except Exception as exc:
            self.last_error = str(exc)
            return None
