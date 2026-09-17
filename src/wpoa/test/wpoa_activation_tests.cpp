// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Unit tests for the two rules that decide WHEN wPoA governs a height, and for the
// create/subscribe state machine that decides when a managed stream is retried.
//
// Both are pure — no node, no chain, no wallet — which is the point: each replaces a
// behaviour that could previously only be observed by running a network for a few minutes
// and noticing what had failed to happen.
//
//   ./src/wpoa/test/run_unit_tests.sh activation
//
// Every case below FAILS on the code before the deferred-activation fix and the
// latch-after-broadcast fix, and passes after them.

#define BOOST_TEST_MODULE wpoa_activation_tests
#include <boost/test/included/unit_test.hpp>

#include "wpoa/wpoa_selector.h"        // WPoAGateAtHeight
#include "wpoa/stream_setup_state.h"   // mc_StreamSetupState

BOOST_AUTO_TEST_SUITE(wpoa_activation)

// -------------------------------------------------------------------------------------
// The deferred-activation fallback
// -------------------------------------------------------------------------------------

// THE REGRESSION. wPoA governs the height by the clock, but the registry has never
// carried a positive weight: scoring fails, no proposer is elected, and the old code
// slept an hour. A clean chain therefore stopped one block short of setup-first-blocks
// and never recovered -- the thing it waited for (a published weight) needed the blocks
// it was refusing to produce. The round must go back to the native rules instead.
BOOST_AUTO_TEST_CASE(no_proposer_and_never_activated_falls_back_to_native)
{
    BOOST_CHECK_EQUAL(WPoAShouldFallBackToNative(false, false), true);
}

// Once wPoA has elected somebody even once, "nobody eligible" is a real outcome of a
// weighted sortition whose weights have gone to zero -- not a bootstrap problem. The
// chain stopping there is the protocol working, and must NOT be routed around.
BOOST_AUTO_TEST_CASE(no_proposer_after_activation_does_not_fall_back)
{
    BOOST_CHECK_EQUAL(WPoAShouldFallBackToNative(false, true), false);
}

// A proposer was elected: use it, whatever the history.
BOOST_AUTO_TEST_CASE(a_proposer_is_always_used)
{
    BOOST_CHECK_EQUAL(WPoAShouldFallBackToNative(true, true),  false);
    BOOST_CHECK_EQUAL(WPoAShouldFallBackToNative(true, false), false);
}

// The latch is what separates the two "no proposer" cases, so the decision must depend
// on it and on nothing else once the proposer is absent.
BOOST_AUTO_TEST_CASE(the_latch_is_the_only_thing_that_separates_the_two_cases)
{
    BOOST_CHECK_NE(WPoAShouldFallBackToNative(false, false),
                   WPoAShouldFallBackToNative(false, true));
}

// -------------------------------------------------------------------------------------
// The stream create/subscribe state machine
// -------------------------------------------------------------------------------------

BOOST_AUTO_TEST_CASE(fresh_state_acts)
{
    mc_StreamSetupState s;
    BOOST_CHECK_EQUAL(s.Next(), MC_SSA_ACT);
    BOOST_CHECK_EQUAL(s.broadcast, false);
    BOOST_CHECK_EQUAL(s.failures, 0);
}

// THE REGRESSION. The old code marked the stream "attempted" BEFORE calling create, so a
// single throw — no create permission yet, no spendable output yet, both transient —
// meant the node never tried again and the stream never appeared.
BOOST_AUTO_TEST_CASE(a_failed_attempt_is_retried_not_remembered_as_done)
{
    mc_StreamSetupState s;
    BOOST_CHECK_EQUAL(s.Next(), MC_SSA_ACT);
    s.RecordFailure();                       // the create call threw
    BOOST_CHECK_EQUAL(s.Next(), MC_SSA_ACT); // ...and we try again
    s.RecordFailure();
    BOOST_CHECK_EQUAL(s.Next(), MC_SSA_ACT);
    BOOST_CHECK_EQUAL(s.failures, 2);
    BOOST_CHECK_EQUAL(s.broadcast, false);
}

// A transaction that really went out must not be sent twice: a duplicate stream name is
// rejected at best, and races the first at worst.
BOOST_AUTO_TEST_CASE(a_real_broadcast_latches)
{
    mc_StreamSetupState s;
    s.RecordBroadcast();
    BOOST_CHECK_EQUAL(s.Next(), MC_SSA_WAIT);
    // Still waiting no matter how long, until the caller re-arms or the stream appears.
    BOOST_CHECK_EQUAL(s.Next(), MC_SSA_WAIT);
}

// Retrying is bounded: a node with no `create` permission will never succeed, and should
// stop rather than log once per tick for the life of the process.
BOOST_AUTO_TEST_CASE(retries_are_bounded_then_give_up)
{
    mc_StreamSetupState s;
    for (int i = 0; i < MC_WPOA_STREAM_SETUP_MAX_FAILURES; i++)
    {
        BOOST_CHECK_EQUAL(s.Next(), MC_SSA_ACT);
        s.RecordFailure();
    }
    BOOST_CHECK_EQUAL(s.Next(), MC_SSA_GIVE_UP);
    BOOST_CHECK_EQUAL(s.GaveUp(), true);
}

// A broadcast that never confirms — evicted from the mempool, or lost to a reorg — would
// otherwise wait for ever, which is the same permanent stall the original bug caused.
BOOST_AUTO_TEST_CASE(re_arming_recovers_a_broadcast_that_never_confirmed)
{
    mc_StreamSetupState s;
    s.RecordBroadcast();
    BOOST_CHECK_EQUAL(s.Next(), MC_SSA_WAIT);
    s.ReArm();
    BOOST_CHECK_EQUAL(s.Next(), MC_SSA_ACT);
    BOOST_CHECK_EQUAL(s.GaveUp(), false);
}

// A latched broadcast outranks the failure count: having given up earlier must not stop
// the node waiting for a create that did eventually go out.
BOOST_AUTO_TEST_CASE(broadcast_outranks_the_failure_count)
{
    mc_StreamSetupState s;
    for (int i = 0; i < MC_WPOA_STREAM_SETUP_MAX_FAILURES; i++) s.RecordFailure();
    BOOST_CHECK_EQUAL(s.Next(), MC_SSA_GIVE_UP);
    s.RecordBroadcast();
    BOOST_CHECK_EQUAL(s.Next(), MC_SSA_WAIT);
    BOOST_CHECK_EQUAL(s.GaveUp(), false);
}

BOOST_AUTO_TEST_CASE(zero_resets_everything)
{
    mc_StreamSetupState s;
    s.RecordFailure();
    s.RecordBroadcast();
    s.Zero();
    BOOST_CHECK_EQUAL(s.Next(), MC_SSA_ACT);
    BOOST_CHECK_EQUAL(s.failures, 0);
    BOOST_CHECK_EQUAL(s.broadcast, false);
}

BOOST_AUTO_TEST_SUITE_END()
