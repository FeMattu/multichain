// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — Stage W1: unit tests for the pure authorization policy
// of the weight-engine input streams (src/weight_engine/weight_authorization.h).
//
// Self-contained: depends only on Boost.Test (header-only "included" variant), NOT on
// the wallet / node runtime — the policy is a decision table over booleans, precisely
// so it can be exercised without a running chain. Build & run with
// src/weight_engine/test/run_unit_tests.sh.
//
// WHAT THE NODE-COUPLED HALF STILL OWNS, and is therefore NOT covered here: reading
// the permission bits off chain (IsCertificationAuthority in weight_publisher.cpp,
// via mc_Permissions::CanCustom on the bit derived from the role's wire name) and the
// per-stream CanWrite check in WeightPublishTo. Those need a live permission DB and
// are covered by functional_test_weight_engine.sh. What is tested here is the policy
// they feed: given those facts, is the write authorized, and with which reason.

#define BOOST_TEST_MODULE WeightAuthorizationTests
#include <boost/test/included/unit_test.hpp>

#include <string>

#include "weight_engine/weight_authorization.h"

// ---- the authorized case -------------------------------------------------

BOOST_AUTO_TEST_CASE(certification_authority_with_stream_write_may_publish)
{
    BOOST_CHECK_EQUAL(mc_WeightEsgWriteDecision(true, true, true),
                      MC_WEIGHT_ESG_WRITE_OK);
    // The authorized case carries no message: nothing to explain.
    BOOST_CHECK_EQUAL(std::string(mc_WeightEsgWriteDecisionText(MC_WEIGHT_ESG_WRITE_OK)),
                      std::string(""));
}

// ---- a plain address, and a global administrator that is not a CA -------

// A generic network address holds neither role: refused for not being a CA.
BOOST_AUTO_TEST_CASE(generic_address_may_not_publish)
{
    BOOST_CHECK_EQUAL(mc_WeightEsgWriteDecision(false, false, true),
                      MC_WEIGHT_ESG_WRITE_NOT_CA);
}

// THE POINT OF THE ROLE. A global administrator that has not been granted the CA
// permission is refused exactly like any other address. The policy is a pure function
// of (is_ca, has_write), with no admin input at all — administering the network and
// certifying ESG scores are separate competences, and the administrator *confers* the
// role rather than holding it automatically.
//
// Both of an admin's possible states are pinned: with .write but no CA it is refused,
// and it is refused for the CA reason rather than for a permission reason.
BOOST_AUTO_TEST_CASE(global_admin_without_ca_role_may_not_publish)
{
    BOOST_CHECK_EQUAL(mc_WeightEsgWriteDecision(false, true, true),
                      MC_WEIGHT_ESG_WRITE_NOT_CA);
    BOOST_CHECK_EQUAL(mc_WeightEsgWriteDecision(false, false, true),
                      MC_WEIGHT_ESG_WRITE_NOT_CA);
}

// An admin that grants itself the CA role becomes authorized — the two roles are
// distinguishable, not mutually exclusive.
BOOST_AUTO_TEST_CASE(admin_that_grants_itself_ca_may_publish)
{
    BOOST_CHECK_EQUAL(mc_WeightEsgWriteDecision(true, true, true),
                      MC_WEIGHT_ESG_WRITE_OK);
}

// ---- revocation ---------------------------------------------------------

// REVOCATION BITES INDEPENDENTLY OF `.write`. An address whose CA permission was
// revoked is refused even though it still holds stream write permission — the two
// grants are independent, and the CA check does not wait for `.write` to be revoked
// too. (Revoking `.write` as well is still recommended, because it closes the raw
// publishfrom route; it is simply not what makes this decision refuse.)
BOOST_AUTO_TEST_CASE(revoked_ca_is_refused_even_while_stream_write_remains)
{
    // before revocation
    BOOST_CHECK_EQUAL(mc_WeightEsgWriteDecision(true, true, true),
                      MC_WEIGHT_ESG_WRITE_OK);
    // after `revoke <address> high1`, with weight-engine-esg.write still granted
    BOOST_CHECK_EQUAL(mc_WeightEsgWriteDecision(false, true, true),
                      MC_WEIGHT_ESG_WRITE_NOT_CA);
}

// ---- the stream-permission half ----------------------------------------

// A genuine CA that was never granted `.write` is refused, and told so specifically:
// the on-chain gate is independent of the role.
BOOST_AUTO_TEST_CASE(certification_authority_without_stream_write_is_refused)
{
    BOOST_CHECK_EQUAL(mc_WeightEsgWriteDecision(true, false, true),
                      MC_WEIGHT_ESG_WRITE_NO_STREAM_PERM);
}

// CA-first ordering: when BOTH are missing the caller is told the real problem — that
// the address is not a certifier — rather than being led to grant more permissions.
BOOST_AUTO_TEST_CASE(missing_both_reports_the_ca_reason_not_the_permission_reason)
{
    BOOST_CHECK_EQUAL(mc_WeightEsgWriteDecision(false, false, true),
                      MC_WEIGHT_ESG_WRITE_NOT_CA);
}

// ---- edge case: a chain too old to express the role --------------------

// FAIL CLOSED. MultiChain custom permissions require protocol >= 20004. On an older
// chain the CA role cannot be expressed, and the decision refuses rather than falling
// back to an admin check — a silent fallback would re-conflate the two competences the
// role exists to separate. It refuses even for an address that would otherwise pass.
BOOST_AUTO_TEST_CASE(chain_without_custom_permissions_fails_closed)
{
    BOOST_CHECK_EQUAL(mc_WeightEsgWriteDecision(true, true, false),
                      MC_WEIGHT_ESG_WRITE_NO_CA_SUPPORT);
    BOOST_CHECK_EQUAL(mc_WeightEsgWriteDecision(false, false, false),
                      MC_WEIGHT_ESG_WRITE_NO_CA_SUPPORT);
    // The support check precedes the role check, so the message names the real cause.
    BOOST_CHECK_EQUAL(mc_WeightEsgWriteDecision(true, false, false),
                      MC_WEIGHT_ESG_WRITE_NO_CA_SUPPORT);
}

// ---- every refusal carries an actionable message -----------------------

BOOST_AUTO_TEST_CASE(every_refusal_has_a_non_empty_message)
{
    const WeightEsgWriteDecision refusals[] = {
        MC_WEIGHT_ESG_WRITE_NOT_CA,
        MC_WEIGHT_ESG_WRITE_NO_STREAM_PERM,
        MC_WEIGHT_ESG_WRITE_NO_CA_SUPPORT
    };
    for (size_t i = 0; i < sizeof(refusals) / sizeof(refusals[0]); i++)
    {
        BOOST_CHECK(std::string(mc_WeightEsgWriteDecisionText(refusals[i])).size() > 0);
    }
}

// The "not a CA" message must tell the operator the exact grant to issue, including
// the role's wire name — otherwise the refusal is not actionable.
BOOST_AUTO_TEST_CASE(not_ca_message_names_the_grant_to_issue)
{
    std::string msg = mc_WeightEsgWriteDecisionText(MC_WEIGHT_ESG_WRITE_NOT_CA);
    BOOST_CHECK(msg.find(MC_WEIGHT_CA_PERMISSION_NAME) != std::string::npos);
    BOOST_CHECK(msg.find("grant") != std::string::npos);
}

// The CA role is carried by a HIGH custom slot, because only those require `admin`
// (rather than `activate`) to grant — which is what guarantees that only the
// administrator may confer CA status. A change to a low slot would silently weaken
// that, so the choice is pinned here.
BOOST_AUTO_TEST_CASE(ca_role_uses_a_high_custom_permission_slot)
{
    std::string name = MC_WEIGHT_CA_PERMISSION_NAME;
    BOOST_CHECK_MESSAGE(name.compare(0, 4, "high") == 0,
                        "the CA role must sit in a high1..high3 slot: the low slots are "
                        "grantable by an `activate` holder, so only the high slots keep "
                        "CA status conferrable by `admin` alone");
}
