# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# participants.py -- the registry that ties the simulation's logical actors
# (M1..M4, COMPANY_Mx_Cy) to on-chain addresses and to the node that can sign for
# them. (Not in the original suggested file list, but stream_writer and
# tx_simulator both need this mapping, so it is factored out here rather than
# duplicated.)
#
#   miner  Mk         : address = miner node k's own address; signer = that node.
#   company Cx        : a fresh address created IN THE ADMIN WALLET (so the admin
#                       can sign transfers from it); signer = the admin node.
#
# Companies are granted send + receive so they can move the simulation asset (which
# is what produces their on-chain activity counter tau).

import config


class ParticipantRegistry(object):
    def __init__(self, network, log):
        self.net = network
        self.log = log
        self._addr = {}     # label -> address
        self._label = {}    # address -> label
        self._node = {}     # label -> Node that can sign for it

    def build(self):
        # miners: address + signer node come straight from the network.
        for m in range(config.NUM_MINERS):
            label = config.miner_id(m)
            node = self.net.miners[m]
            self._register(label, node.address, node)

        # companies: create a fresh address in the admin wallet, grant send/receive.
        admin = self.net.admin
        created = 0
        for m in range(config.NUM_MINERS):
            for c in range(config.COMPANIES_PER_MINER):
                label = config.company_id(m, c)
                addr = admin.cli("getnewaddress")
                admin.cli_ok("grant", addr, "send,receive")
                self._register(label, addr, admin)
                created += 1
        self.log.info("participants: %d miners + %d companies registered" %
                      (config.NUM_MINERS, created))

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

    def all_labels(self):
        return self.miner_labels() + self.company_labels()

    def miner_address_set(self):
        return set(self.address_of(l) for l in self.miner_labels())
