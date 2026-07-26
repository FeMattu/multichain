# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# participants.py -- the registry that ties the simulation's logical actors to
# on-chain addresses and to the node that can sign for them. (Not in the original
# suggested file list, but stream_writer, tx_simulator and economics all need this
# mapping, so it is factored out here rather than duplicated.)
#
# MyLedger actors:
#   ClusterMinerA..E  : address = miner node k's own address; signer = that node.
#   Azienda_X1..X10   : a fresh address created IN THE ADMIN WALLET (so the admin
#                       can sign transfers from it); signer = the admin node.
#   ADMIN             : the genesis / global-admin node's own address -- the Apuana SB
#                       stand-in and the reconciliation counterparty every miner
#                       returns GAS to at the end of an epoch.
#   FEEPOOL           : an admin-wallet address that stands in for the AGGREGATE of
#                       all transaction senders when fees are settled. Each network
#                       transaction costs ALPHA GAS; rather than deduct 0.2 GAS in a
#                       separate tx from every one of ~750 senders per epoch (which
#                       would triple the run's transaction count for no modelling
#                       gain), the pool pays each miner its whole epoch fee income
#                       Guadagno_k = TxMiner_k * ALPHA in ONE transfer. The GAS
#                       totals are identical; only the number of txs differs.
#
# Companies are granted send + receive so they can move GAS (which is what produces
# their on-chain activity counter tau). ADMIN and FEEPOOL are NOT cluster members:
# they carry no ESG score and no membership record, so they never enter a weight.

import config


class ParticipantRegistry(object):
    def __init__(self, network, log):
        self.net = network
        self.log = log
        self._addr = {}     # label -> address
        self._label = {}    # address -> label
        self._node = {}     # label -> Node that can sign for it

    def build(self):
        # cluster miners: address + signer node come straight from the network.
        for m in range(config.NUM_MINERS):
            label = config.miner_id(m)
            node = self.net.miners[m]
            self._register(label, node.address, node)

        admin = self.net.admin
        # ADMIN (Apuana SB): the node's own genesis address, already permissioned.
        self._register(config.ADMIN_LABEL, admin.address, admin)

        # FEEPOOL: a dedicated admin-wallet address, so fee settlement is visible on
        # chain as its own flow and never confused with an ADMIN reconciliation credit.
        fee_addr = admin.cli("getnewaddress")
        admin.cli_ok("grant", fee_addr, "send,receive")
        self._register(config.FEEPOOL_LABEL, fee_addr, admin)

        # companies: create a fresh address in the admin wallet, grant send/receive.
        created = 0
        for m in range(config.NUM_MINERS):
            for c in range(config.COMPANIES_PER_MINER):
                label = config.company_id(m, c)
                addr = admin.cli("getnewaddress")
                admin.cli_ok("grant", addr, "send,receive")
                self._register(label, addr, admin)
                created += 1
        self.log.info("participants: %d cluster miners + %d aziende + ADMIN + FEEPOOL "
                      "registered" % (config.NUM_MINERS, created))

    def _register(self, label, addr, node):
        self._addr[label] = addr
        self._label[addr] = label
        self._node[label] = node

    # -- lookups ------------------------------------------------------------
    def address_of(self, label):
        return self._addr.get(label)

    def label_of(self, addr):
        return self._label.get(addr, addr)   # fall back to the raw address

    def node_for(self, label):
        return self._node.get(label)

    def miner_labels(self):
        return [config.miner_id(m) for m in range(config.NUM_MINERS)]

    def company_labels(self):
        return [config.company_id(m, c)
                for m in range(config.NUM_MINERS)
                for c in range(config.COMPANIES_PER_MINER)]

    def companies_of(self, miner_idx):
        """The 10 aziende of cluster `miner_idx`, in configuration-sheet order."""
        return [config.company_id(miner_idx, c)
                for c in range(config.COMPANIES_PER_MINER)]

    def cluster_labels(self):
        """Only the actors that carry an ESG score / membership record: the cluster
        miners and their companies. Excludes ADMIN and FEEPOOL by design."""
        return self.miner_labels() + self.company_labels()

    def all_labels(self):
        """Every funded participant, including the two non-cluster actors."""
        return (self.miner_labels() + self.company_labels()
                + [config.ADMIN_LABEL, config.FEEPOOL_LABEL])

    def miner_address_set(self):
        return set(self.address_of(l) for l in self.miner_labels())

    def admin_address(self):
        return self.address_of(config.ADMIN_LABEL)

    def feepool_address(self):
        return self.address_of(config.FEEPOOL_LABEL)
