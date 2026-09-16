# ADR — the RANDAO fold returns to the bare XOR of Definition 5.3

> **Status:** accepted, implemented.
> **Scope:** `RandaoAccumulator::Fold` ([../../randao_accumulator.h](../../randao_accumulator.h)),
> thesis Def. 5.3 / §5.4 (global accumulator update). The seed derivation `seed[n+1] =
> H(R_tot[n-k] ‖ h[n] ‖ n+1)` is untouched.
> **Register: technical-direct.** Decision record: the problem, the options weighed, the
> decision and its consequences. Module reference:
> [../randao-accumulator.md](../randao-accumulator.md); design context:
> [../phase3b-implementation-guide.md §5.1](../phase3b-implementation-guide.md#51-the-fold-is-the-thesis-def-53-itself-a-bare-xor).

---

## 1. The problem

The thesis states the accumulator in one line (Def. 5.3):

```
R_tot[n] = R_tot[n-1] ⊕ R[n]
```

and proves on *that* form that all honest nodes observing the same sequence of valid
blocks compute the same `R_tot[n]` (Prop. 5.1). The implementation folded something else —
the hardened variant the implementation chapter describes:

```
R_tot[n] = H( R_tot[n-1] ⊕ H(R[n]) )
```

An earlier pass over this module confirmed the deviation was deliberate rather than drift,
and documented it in the header and the guides. But a documented deviation is still a
deviation: the specification is the thesis, the code is what runs, and the two disagreed on
the single formula that determines every proposer election. The question this ADR settles
is not whether the deviation was *recorded* — it was — but whether the hardening earns the
divergence it costs.

## 2. Options considered

### Option A — keep the hardened fold, keep documenting the deviation
The status quo. Two extra SHA-256 calls per block, and a permanent footnote in every
document that states the accumulator.

### Option B — implement Def. 5.3 literally
One byte-wise XOR per block. The code and the specification state the same recurrence, and
the regression guard changes sides: instead of pinning a deviation, it pins conformance.

### Option C — make the fold selectable at runtime
A flag choosing bare or hardened.

## 3. Analysis

### 3.1 The outer hash protects a property nothing consumes

The outer `H(·)` exists to make `R_tot` itself look uniform. But **nothing reads `R_tot`
raw.** Its only consumer is `DeriveSeed`, which computes `H(R_tot[n-k] ‖ h[n] ‖ n+1)` — a
SHA-256 over the accumulator and two more fields. The bytes the Efraimidis–Spirakis
selector actually scores are a digest under either fold. Hashing at the fold *and* at the
seed does not make the seed more uniform; it makes it hashed twice.

### 3.2 The linearity argument does not apply to a VRF reveal

A bare XOR accumulator is linear, so a participant who **chooses** the last contribution
can solve for a value that cancels everything before it. That is the classical argument
against a bare RANDAO XOR, and it is sound where the contribution is a freely chosen
preimage.

It does not describe this beacon. `R[n]` is a VRF output over the parent hash: by
uniqueness (see [../vrf-wrapper.md](../vrf-wrapper.md)) exactly one `(output, proof)` pair
is valid for a given key and input, and `VerifyBlockMinerWPoA` rejects any other value
before the fold is ever reached. A validator has no freedom to pick its reveal, so there is
no algebraic handle for the outer hash to remove. What a validator *can* still do — refuse
to produce a block at all — is unaffected by either fold; that is last-revealer bias, and
it is bounded per Cleve and addressed in Phase 5, not here.

### 3.3 The inner hash has nothing to normalize

Hashing the reveal first was justified by a reveal of variable length. On the wire it is
fixed: `WPoAVRF::OUTPUT_SIZE` is 32 bytes and `WPoAVRF::Verify` rejects anything else, so a
governed block's reveal is always exactly one accumulator word. `Fold` still takes a length
and stays total for off-size buffers (short reveals touch their prefix, long ones wrap),
but no consensus path produces one.

### 3.4 Option C would add a second way to fork

The fold is consensus-critical: nodes that fold differently elect different proposers. A
runtime switch does not avoid the incompatibility, it relocates it into an operator's hands
and adds a params.dat field that must match everywhere. There is no scenario in which two
folds are both wanted on one chain.

## 4. Decision

**Option B.** `Fold` computes `R_tot_prev ⊕ reveal`, Def. 5.3 verbatim, byte-wise over 32
bytes, with in/out aliasing still permitted. `Genesis`, `DeriveSeed`, the lookback `k`, the
block-hash-keyed memoization and both call sites are unchanged.

The unit suite inverts its guard: `fold_is_the_bare_xor_of_definition_5_3` checks the fold
against hand-written bytes *and* against the old hardened formula, so reintroducing
`H(R_tot ⊕ H(R))` fails the build rather than silently changing every seed.

## 5. Consequences

### Positive

- The code and the thesis state the same recurrence. Prop. 5.1's proof now applies to the
  implementation as written, with no bridging argument required.
- Two SHA-256 calls per governed block disappear from the fold, and the accumulator's
  behaviour is inspectable by hand.
- Every document that states the accumulator states one formula.

### Negative, and accepted

- **This is a consensus break.** The fold defines every seed, so the same reveals now elect
  different proposers. A chain already running with `-enablewpoarandao` must be restarted
  from genesis; it cannot be upgraded in place. Acceptable here because no production chain
  runs this fork, and the in-memory accumulator cache is rebuilt on restart anyway.
- **`R_tot` is order-independent.** XOR is commutative, so `R_tot[n]` is a function of the
  multiset of reveals, not of their sequence. A chain fixes the order of its own blocks, so
  two orderings of one branch's reveals do not exist; and position is re-bound one step
  later, since `seed[n+1]` commits to `h[n]` and `n+1`.
- **A repeated reveal would cancel itself.** XOR is self-inverse. Unreachable on a branch:
  the Phase-3a VRF input is the parent hash `h[n-1]`, distinct at every height, so a given
  key cannot legitimately produce the same reveal twice on one chain.
- **A single reveal no longer diffuses across the accumulator.** Under the hardened fold one
  reveal bit changed every `R_tot` bit; under XOR it changes one. Diffusion happens in
  `DeriveSeed`, which is where the selector reads — so the seed still avalanches on any
  input change, as its own tests check.

Both algebraic properties are pinned by `accumulator_algebra_is_known_and_bounded`, stated
as known rather than left to be rediscovered as suspected bugs.

## 6. Relationship to the thesis text

Def. 5.3 and the implementation chapter give two different accumulators; the code cannot
satisfy both. This ADR resolves the conflict in favour of the formal definition — the one
Prop. 5.1 is proved over — and records why the implementation chapter's extra hashes are
not load-bearing in a beacon whose contributions are VRF outputs. The implementation
chapter's description of the accumulator should be aligned with Def. 5.3 in the text.
