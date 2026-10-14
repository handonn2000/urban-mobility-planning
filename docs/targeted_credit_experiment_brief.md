# Campaign brief - Targeted congestion credit test

**Hypothesis.** Offering a $1.50 future-ride credit to eligible users with a pre-test history of short, low-fare zone trips increases contribution at lower organic-trip subsidy cost than blanket issuance.

**Eligibility and assignment.** Define eligibility from the preceding 28 days before assignment; do not classify users from post-treatment fares or trips. Randomly assign 90% of eligible users to treatment and 10% to holdout. Keep assignment stable per user. The public TLC data has no user IDs, so this is a proposed design, not an executed test or generated targeting list. Trip coverage s=30% is an assumption to validate, not 30% of users.

**Primary metric.** Zone trips per assigned eligible user, including zero-trip users, analyzed by intention to treat. Uplift is (treatment rate/control rate)-1 on the eligible-user denominator. Also measure all Lyft trips per user to detect displacement outside the zone. Do not compare eligible-user uplift directly with a whole-market 10% threshold.

**Economics and guardrails.** Measure actual credit issued/redeemed and contribution using approved internal cost definitions. Primary economic outcome: incremental contribution per assigned user after redeemed-credit cost. Guardrails: waiting time, cancellation rate and contribution per trip. Marketplace spillovers may affect the holdout; random assignment reduces confounding but does not remove every interference assumption. Margin/redemption/cancellation metrics require internal platform data.

**Duration and sample.** At least 14 issuance days for two of every weekday, plus a redemption follow-up covering the seven-day credit validity and issuance timing. Final duration and user count come from a power calculation using pre-test variance and a prespecified minimum detectable effect; public aggregate TLC data cannot supply a defensible sample-size calculation.

**Decision.** Before launch, agree sample size, guardrail limits, contribution definition and a fixed analysis date. Expand only if the confidence interval for incremental net contribution supports a positive effect and guardrails remain within agreed limits; otherwise do not expand and stop or redesign the campaign. Under m=$6, c=$1.50, redemption=100%, and all extra trips credited, the illustrative break-even is 33.33% eligible uplift. If eligible baseline trips are 30% of all baseline trips, that equals 10% whole-base uplift. Recompute the threshold from measured margin/redemption; do not treat either number as an unconditional launch rule.

This brief is a design deliverable. No live campaign, customer messaging or account changes were made.
