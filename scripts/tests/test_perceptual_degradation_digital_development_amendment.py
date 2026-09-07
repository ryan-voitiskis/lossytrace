from __future__ import annotations

import hashlib
import json
import unittest
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/digital-development-sequence-amendment-20260907.json"
BINDING_PATHS = {
    "research_contract": "docs/research/perceptual-degradation-contract-20260803.md",
    "research_plan": "benchmarks/perceptual-degradation-v1/research-plan.json",
    "strategic_review": "docs/research/perceptual-degradation-strategic-review-20260905.md",
    "historical_objective_audit": "research/toolchains/evidence/perceptual-degradation-objective-completion-audit-20260819-022.json",
    "source_condition_candidates": "benchmarks/perceptual-degradation-v1/source-condition-qualification-plan.json",
    "source_adjudication": "benchmarks/perceptual-degradation-v1/source-trait-adjudication-relationship-plan.json",
    "capture_intake": "benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-clean-capture-live-intake-plan.json",
    "reference_acquisition": "benchmarks/perceptual-degradation-v1/odaq-reference-acquisition-result-20260813.json",
    "reference_delivery": "benchmarks/perceptual-degradation-v1/odaq-reference-delivery-result-20260814.json",
    "retained_drift_negative": "benchmarks/perceptual-degradation-v1/odaq-retained-drift-validation-result-20260817.json",
    "probability_targets": "benchmarks/perceptual-degradation-v1/perceptual-target-semantics-plan.json",
    "nonmateriality_semantics": "benchmarks/perceptual-degradation-v1/nonmateriality-evidence-plan.json",
    "score_free_oracle": "benchmarks/perceptual-degradation-v1/oracle-validity-integration-plan.json",
}


class DigitalDevelopmentAmendmentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads(PLAN.read_text())
        # Only fixed public repository records are read; no path is taken from
        # a private manifest or supplied to any audio/codec/metric runner.
        cls.records = {
            key: json.loads((ROOT / relative).read_text())
            for key, relative in BINDING_PATHS.items() if relative.endswith(".json")
        }

    def test_plan_identity_and_section_inventory(self):
        self.assertIs(type(self.plan["schema_version"]), int)
        self.assertEqual(1, self.plan["schema_version"])
        self.assertEqual("digital-development-sequence-20260907-001", self.plan["amendment_id"])
        self.assertEqual("user_approved_sequence_amendment_execution_not_authorized", self.plan["state"])
        self.assertEqual({"schema_version", "amendment_id", "state", "authority", "objective", "bindings", "sequence_change", "development_cohort", "first_study", "ordered_work", "deferred_not_waived", "resources_and_publication", "claim_boundary"}, set(self.plan))

    def test_all_thirteen_predecessors_are_exact_and_unchanged(self):
        self.assertEqual(set(BINDING_PATHS), set(self.plan["bindings"]))
        for key, relative in BINDING_PATHS.items():
            with self.subTest(binding=key):
                self.assertEqual({"path": relative, "sha256": hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()}, self.plan["bindings"][key])

    def test_objective_is_not_replaced_by_the_development_study(self):
        self.assertEqual(
            "Determine whether LossyTrace can estimate material perceptual degradation caused by lossy audio coding, rather than infer prior codec history. Build a deterministic full-reference perceptual oracle anchored by controlled listening evidence, then train and independently validate a no-reference estimator on grouped source-, domain-, codec- and encoder-held-out evidence. Report impairment severity, estimated audibility, artifact profile, support and uncertainty with explicit abstention. Treat perceptually transparent lossy encodes as non-degraded, preserve difficult natural and production negatives, keep the public CLI verdict-free, and treat a rigorous negative result as successful completion.",
            self.plan["objective"],
        )

    def test_authority_opens_preparation_only(self):
        authority = self.plan["authority"]
        permitted = {"plan_revision_authorized", "public_repository_metadata_review_authorized", "execution_protocol_preparation_authorized"}
        forbidden = {"retained_waveform_or_private_manifest_read_authorized", "codec_generation_authorized", "sample_correction_authorized", "metric_execution_authorized", "playback_or_human_collection_authorized", "provider_processed_condition_or_score_access_authorized", "sealed_evidence_access_authorized", "no_reference_training_authorized", "outreach_authorized", "spending_authorized", "public_verdict_enabled"}
        self.assertEqual(permitted | forbidden | {"source"}, set(authority))
        for key in permitted:
            self.assertIs(authority[key], True, key)
        for key in forbidden:
            self.assertIs(authority[key], False, key)

    def test_capture_dependency_removed_only_for_this_study(self):
        change = self.plan["sequence_change"]
        self.assertEqual("odaq16_digital_development_study", change["applies_only_to"])
        self.assertIs(change["capture_first_dependency_removed_for_this_study"], True)
        self.assertIs(change["complete_seven_trait_manifest_required_before_this_study"], False)
        self.assertIs(change["historical_audit_next_gate_superseded_for_this_study"], True)
        self.assertIs(change["complete_seven_trait_manifest_required_for_full_objective"], True)
        self.assertIs(change["historical_observations_or_numeric_thresholds_changed"], False)
        self.assertIs(change["legacy_execution_plans_or_runners_reauthorized"], False)

    def test_cohort_matches_acquisition_and_delivery_not_a_new_selection(self):
        cohort = self.plan["development_cohort"]
        acquired = self.records["reference_acquisition"]["retained_inventory"]
        delivered = self.records["reference_delivery"]["delivery_inventory"]
        for key in ("sample_rate_hz", "channel_count", "minimum_frame_count", "maximum_frame_count"):
            self.assertIs(type(cohort[key]), int)
            self.assertEqual(acquired[key], cohort[key])
            self.assertEqual(delivered[key], cohort[key])
        self.assertEqual(16, cohort["reference_count"])
        self.assertEqual(acquired["reference_count"], cohort["reference_count"])
        self.assertEqual(delivered["reference_count_per_replay"], cohort["reference_count"])
        self.assertEqual(acquired["completed_inventory_sha256"], cohort["original_inventory_sha256"])
        self.assertEqual(delivered["output_inventory_sha256"], cohort["delivery_inventory_sha256"])
        self.assertEqual({"signed_integer_24_bit": 9, "signed_integer_32_bit": 7}, cohort["retained_delivery_sample_formats"])
        self.assertEqual(delivered["signed_integer_24_bit_reference_count"], cohort["retained_delivery_sample_formats"]["signed_integer_24_bit"])
        self.assertEqual(delivered["signed_integer_32_bit_reference_count"], cohort["retained_delivery_sample_formats"]["signed_integer_32_bit"])
        self.assertIs(cohort["current_file_presence_and_integrity_reverified"], False)

    def test_development_sources_cannot_become_independent_validation(self):
        cohort = self.plan["development_cohort"]
        self.assertEqual(1, cohort["provider_stratum_count"])
        self.assertEqual("odaq_retained_development_only", cohort["development_partition"])
        self.assertIs(cohort["all_cohort_members_and_derivatives_colocated"], True)
        self.assertIs(cohort["source_count_asserts_independent_group_count"], False)
        self.assertIs(cohort["fresh_transfer_or_final_validation_eligible"], False)

    def test_geometry_does_not_invent_eight_seconds_of_active_support(self):
        cohort = self.plan["development_cohort"]
        duration = Fraction(cohort["minimum_frame_count"], cohort["sample_rate_hz"])
        self.assertLess(duration, 8)
        self.assertEqual({"subtle": 4.0, "quality_metric": 8.0}, self.plan["first_study"]["minimum_active_seconds_unchanged"])
        self.assertEqual(self.records["score_free_oracle"]["integration_contract"]["comparison_modes_minimum_active_seconds"], self.plan["first_study"]["minimum_active_seconds_unchanged"])
        self.assertIn("all 16 source identities", self.plan["first_study"]["support_policy"])
        self.assertIn("without replacement, padding, looping", self.plan["first_study"]["support_policy"])

    def test_digital_route_needs_neither_capture_nor_loopback(self):
        study = self.plan["first_study"]
        for key in ("sound_card_loopback_required", "microphone_or_preamp_required", "room_measurement_required", "new_corpus_acquisition_required"):
            self.assertIs(study[key], False)
        self.assertEqual(["verified_existing_digital_reference", "declared_codec_input_view", "bound_encoder", "bound_decoder", "reference_test_comparison"], study["signal_path"])

    def test_candidate_inventory_is_not_frozen_codec_execution(self):
        study = self.plan["first_study"]
        self.assertEqual(set(self.records["source_condition_candidates"]["codec_condition_candidates"]["required_codec_families"]), set(study["candidate_codec_families"]))
        for key in ("exact_conditions_selected", "exact_encoder_decoder_bindings_selected", "case_count_frozen"):
            self.assertIs(study[key], False)
        self.assertIn("44.1 kHz", study["condition_design"])
        self.assertIn("new recipe identities", study["condition_design"])
        self.assertEqual(["identity_comparison", "matched_pcm_only_input_adapter_control"], study["required_controls"])
        self.assertEqual("unavailable_not_zero_or_transparent", study["perceptual_outcomes_before_calibration"])

    def test_work_sequence_has_an_explicit_execution_approval_boundary(self):
        self.assertEqual([
            ("freeze_digital_execution_protocol", "next_authorized_preparation"),
            ("execute_authorized_digital_technical_study", "requires_separate_execution_approval_and_exact_head_ci"),
            ("metric_and_human_development", "separately_gated"),
            ("complete_broad_validation_program", "required_for_full_objective"),
        ], [(item["stage_id"], item["status"]) for item in self.plan["ordered_work"]])

    def test_all_seven_traits_and_four_transfer_axes_remain_required(self):
        deferred = self.plan["deferred_not_waived"]
        self.assertEqual(["natural_bandwidth_limit", "quiet", "sparse", "tonal", "synthetic", "noisy", "clipped"], deferred["required_source_traits"])
        self.assertEqual(self.records["research_plan"]["grouping"]["required_holdout_axes"], deferred["required_transfer_axes"])
        self.assertEqual({"clean_capture", "required_source_traits", "quiet", "clipped", "production_negatives", "retained_drift", "metric_selection", "human_truth", "required_transfer_axes", "odaq_processed_conditions_and_scores"}, set(deferred))

    def test_capture_authority_is_preserved_not_executed_or_expanded(self):
        capture = self.records["capture_intake"]
        self.assertIs(capture["authority_received"]["one_safe_clean_capture_conduct_or_arrange_authorized"], True)
        self.assertIs(capture["authority_received"]["outreach_authorized"], False)
        self.assertIs(capture["authority_received"]["spending_authorized"], False)
        self.assertIs(capture["operational_authorization"]["capture_execution_authorized_by_this_checkpoint"], False)

    def test_all_scientific_and_product_completion_claims_remain_false(self):
        claims = self.plan["claim_boundary"]
        self.assertEqual({"source_manifest_frozen", "source_traits_assigned", "codec_study_executed", "human_calibration_complete", "transparent_lossy_truth_established", "full_reference_oracle_validated", "grouped_transfer_passed", "no_reference_estimator_validated", "final_recommendation_selected", "objective_complete", "public_cli_changed", "public_verdict_enabled"}, set(claims))
        for key, value in claims.items():
            self.assertIs(value, False, key)

    def test_resource_and_publication_limits_are_preserved(self):
        limits = self.plan["resources_and_publication"]
        self.assertEqual(1, limits["maximum_research_workers"])
        self.assertEqual(6, limits["maximum_general_sustained_workers"])
        self.assertEqual(15, limits["minimum_free_disk_gib"])
        self.assertIs(limits["duplicate_retained_corpus_allowed"], False)
        self.assertIs(limits["new_capture_or_derived_pcm_retained_by_this_amendment"], False)
        self.assertEqual(["full_staged_diff_review", "credential_private_path_media_model_cache_and_size_audit", "full_local_ci_equivalent", "deterministic_sbom", "conventional_commit", "existing_branch_push", "successful_exact_head_ci"], limits["publication_checks"])


if __name__ == "__main__":
    unittest.main()
