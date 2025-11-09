"""
ledger.py
----------
Polkadot integration layer for the PSP-CBDC-ML project.
This module connects to the Polkadot testnet and records synthetic CBDC
transactions that have been processed by the ML engine.

Goal (Hackathon): demonstrate an end-to-end CBDC ledger prototype
Goal (IFSC/BIS): show how ML-flagged transactions can be immutably recorded.
"""

from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.exceptions import SubstrateRequestException


class PolkadotLedger:
    def __init__(self, node_url="wss://rpc.polkadot.io"):
        try:
            self.substrate = SubstrateInterface(
                url=node_url,
                type_registry_preset="polkadot"
            )
            self.keypair = Keypair.create_from_uri("//Alice")  # dev account
            print(f"[✓] Connected to Polkadot node: {node_url}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Polkadot node: {e}")

    def record_transaction(self, tx_id, sender, receiver, amount, anomaly_score):
        """
        Records a CBDC transaction on Polkadot testnet.
        For hackathon demo purposes, uses Balances.transfer().
        """
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
            # In a real CBDC setting, you’d log anomaly_score in an on-chain metadata pallet
            return receipt.extrinsic_hash

        except SubstrateRequestException as e:
            print(f"[x] Transaction {tx_id} failed: {e}")
        except Exception as e:
            print(f"[x] Unexpected error: {e}")
if __name__ == "__main__":
    ledger = PolkadotLedger()