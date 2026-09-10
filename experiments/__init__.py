"""POESIA / wPoA real-network emulation harness.

Runs the *real* MultiChain binaries of this fork on an emulated network
(CORE Network Emulator or plain Linux network namespaces) and produces the
same analytical artefacts the previous Shadow suite produced.

Nothing in this package simulates the protocol: every block, every stream
record and every RPC answer comes from a real ``multichaind`` process.
"""

__version__ = "1.0.0"
