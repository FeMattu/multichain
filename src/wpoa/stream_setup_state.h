// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA / WeightEngine — the create-and-subscribe state machine for a managed stream.
// ------------------------------------------------------------------------------
// Three components create streams on demand: the weight registry (`wpoa-weights`), the
// malus registry (`wpoa-weights-malus`) and the weight engine's reader (the two input
// streams). They had three copies of the same logic, and two of the three had the same
// bug in it.
//
// The bug is worth stating precisely, because the correct version looks almost identical.
// The broken code latched "attempted" BEFORE the create call:
//
//     s.create_attempted = true;
//     try { createcmd(...); } catch (...) { log("ERROR"); }
//
// so a create that threw — no `create` permission yet, no spendable output yet, both of
// which resolve themselves within a few blocks — was remembered as done. The node never
// tried again. On a live chain this produced exactly one of the three streams, and the
// weight engine then waited for inputs that could no longer arrive: the chain ran, the
// registry stayed empty, and nothing in the logs said why.
//
// The correct version latches only on a transaction that was really broadcast, and bounds
// the retries so a node that will never succeed stops trying instead of logging once per
// tick for ever.
//
// This header is PURE: no node types, no globals, no I/O. That is what lets the state
// machine be unit-tested on its own (src/wpoa/test/wpoa_stream_setup_tests.cpp) rather
// than only observed through a running chain.

#ifndef MC_WPOA_STREAM_SETUP_STATE_H
#define MC_WPOA_STREAM_SETUP_STATE_H

/** How many FAILED attempts to make before giving up on a stream.
 *
 *  At the ~3 s engine/registry tick this is about a minute, which comfortably covers the
 *  transient causes (the funding transaction confirming, a grant confirming) and gives up
 *  on the permanent one (this node simply has no `create` permission). */
#define MC_WPOA_STREAM_SETUP_MAX_FAILURES 20

/** What the caller should do about a stream on this tick. */
enum mc_StreamSetupAction
{
    MC_SSA_ACT,        //!< issue the create/subscribe call now
    MC_SSA_WAIT,       //!< a call is already in flight; wait for it to confirm
    MC_SSA_GIVE_UP     //!< too many failures; stop trying
};

/** One managed step (create, or subscribe) of one stream.
 *
 *  Usage is deliberately rigid, because the bug this replaces came from doing it in the
 *  wrong order:
 *
 *      if (state.Next() != MC_SSA_ACT) return false;
 *      try   { do_the_call();  state.RecordBroadcast(); }
 *      catch { state.RecordFailure(); }
 *
 *  `RecordBroadcast` after the call, never before. */
struct mc_StreamSetupState
{
    bool broadcast;    //!< a transaction really went out; do not send a second one
    int  failures;     //!< attempts that threw

    mc_StreamSetupState() : broadcast(false), failures(0) {}

    void Zero()
    {
        broadcast = false;
        failures  = 0;
    }

    /** What to do on this tick. */
    mc_StreamSetupAction Next(int max_failures = MC_WPOA_STREAM_SETUP_MAX_FAILURES) const
    {
        if (broadcast)              return MC_SSA_WAIT;
        if (failures >= max_failures) return MC_SSA_GIVE_UP;
        return MC_SSA_ACT;
    }

    /** The call returned: a transaction is in flight. */
    void RecordBroadcast() { broadcast = true; }

    /** The call threw: count it and stay retryable. */
    void RecordFailure() { failures++; }

    /** The in-flight transaction never confirmed — allow a fresh attempt.
     *
     *  A broadcast is not a guarantee: a create transaction can be evicted from the
     *  mempool, or lost to a reorg. Without this the node would wait for a confirmation
     *  that is never coming, which is the same permanent stall the original bug caused,
     *  only rarer. The caller re-arms after enough ticks to be sure, so the normal path
     *  (broadcast, confirm a block or two later) never re-arms. */
    void ReArm() { broadcast = false; }

    /** True once this step has given up, so a caller can report it distinctly. */
    bool GaveUp(int max_failures = MC_WPOA_STREAM_SETUP_MAX_FAILURES) const
    {
        return !broadcast && failures >= max_failures;
    }
};

#endif // MC_WPOA_STREAM_SETUP_STATE_H
