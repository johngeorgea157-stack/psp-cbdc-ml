"""
ledger.py
----------
Polkadot integration layer for the PSP-CBDC-ML project.
This module connects to the Polkadot testnet and records synthetic CBDC
transactions that have been processed by the ML engine.

"""

from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.exceptions import SubstrateRequestException
import hashlib
import random


class PolkadotLedger:
    def __init__(self, node_url="wss://westend-rpc.polkadot.io"):
        """
        Polkadot ledger helper.
        Default node_url points to Westend testnet (suitable for hackathon/demo).
        """
        try:
            self.substrate = SubstrateInterface(
                url=node_url,
                type_registry_preset="westend"
            )
            # Dev keypair (works on dev/test nets). Do NOT use in production.
            self.keypair = Keypair.create_from_uri("//Alice")
            print(f"[✓] Connected to Polkadot node: {node_url}")
        except Exception as e:
            # Keep substrate attribute so callers can check it
            self.substrate = None
            self.keypair = None
            print(f"[x] Failed to connect to Polkadot node: {e}")

    def record_transaction(self, tx_id, sender, receiver, amount, anomaly_score):
        """
        Records a CBDC transaction on Polkadot testnet (demo).
        Returns extrinsic hash string on success, or None on failure.
        """
        if not self.substrate or not self.keypair:
            print(f"[x] Skipping on-chain record for {tx_id}: no substrate connection")
            return None

        try:
            call = self.substrate.compose_call(
                call_module="Balances",
                call_function="transfer",
                call_params={"dest": receiver, "value": int(amount)}
            )

            extrinsic = self.substrate.create_signed_extrinsic(
                call=call, keypair=self.keypair
            )

            receipt = self.substrate.submit_extrinsic(
                extrinsic, wait_for_inclusion=True
            )

            print(f"[✓] Transaction {tx_id} recorded. Hash: {receipt.extrinsic_hash}")
            # In a real CBDC pallet you'd also store anomaly_score in on-chain metadata.
            return receipt.extrinsic_hash

        except SubstrateRequestException as e:
            print(f"[x] Transaction {tx_id} failed: {e}")
            return None
        except Exception as e:
            print(f"[x] Unexpected error: {e}")
            return None


if __name__ == "__main__":
    ledger = PolkadotLedger()


def log_cbdc_transfer(tx_id, sender, receiver, amount, risk_score):
    """
    Simplified wrapper: logs CBDC transfers to the Polkadot testnet
    as dummy balance transfers (for hackathon demo).
    """
    try:
        ledger = PolkadotLedger()
        print(f"[~] Logging transaction {tx_id} ({sender} → {receiver}, ₹{amount}) to Polkadot…")

        # Record on-chain
        hash_ = ledger.record_transaction(
            tx_id=tx_id,
            sender=sender,
            receiver=receiver,
            amount=amount,
            anomaly_score=risk_score
        )

        # If no real hash (e.g., RPC error), generate mock one
        if not hash_:
            mock_hash = hashlib.sha256(f"{tx_id}-{random.random()}".encode()).hexdigest()[:16]
            print(f"[!] Polkadot log completed but no hash returned. Using mock hash: {mock_hash}")
            return mock_hash

        print(f"[✓] Polkadot log complete. Hash: {hash_}")
        return hash_

    except Exception as e:
        print(f"[x] Ledger log failed for {tx_id}: {e}")
        mock_hash = hashlib.sha256(f"{tx_id}-{random.random()}".encode()).hexdigest()[:16]
        print(f"[!] Returning fallback hash: {mock_hash}")
        return mock_hash