#!/usr/bin/env python3
"""Validate the score-blind GstPEAQ proxy public-record disposition."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DISPOSITION = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "gstpeaq-proxy-score-blind-disposition.json"
)
DISPOSITION_ID = (
    "perceptual-degradation-gstpeaq-proxy-score-blind-disposition-20260814-001"
)
OBSERVATION_ID = (
    "perceptual-degradation-gstpeaq-public-legal-observation-20260814-001"
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(disposition: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if (
        disposition.get("schema_version") != 1
        or disposition.get("disposition_id") != DISPOSITION_ID
    ):
        errors.append("disposition identity differs")
    if disposition.get("state") != (
        "public_record_insufficient_for_execution_current_two_family_candidate_stopped"
    ):
        errors.append("disposition state differs")

    bound: dict[str, dict[str, Any]] = {}
    for binding_id, binding in disposition.get("bindings", {}).items():
        path = root / str(binding.get("path", ""))
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"bound file hash differs: {binding_id}")
        elif path.suffix == ".json":
            bound[binding_id] = load_json(path)

    observation = bound.get("public_legal_observation", {})
    if observation.get("observation_id") != OBSERVATION_ID:
        errors.append("public legal observation identity differs")

    research = bound.get("research_plan", {})
    proxy_family = next(
        (
            family
            for family in research.get("primary_metric_families", [])
            if family.get("family_id") == "gstpeaq_proxy_v0_6_1"
        ),
        {},
    )
    if (
        proxy_family.get("legal_gate_required") is not True
        or proxy_family.get("conformance")
        != "upstream_declares_output_outside_ITU_tolerance"
    ):
        errors.append("frozen proxy research boundary differs")

    contract_path = root / disposition["bindings"]["research_contract"]["path"]
    contract = contract_path.read_text(encoding="utf-8")
    if "the legal/conformance boundary for the proxy is unresolved" not in contract:
        errors.append("contract stop condition differs")

    metric_gate = bound.get("metric_execution_gate", {})
    metric_proxy = metric_gate.get("metric_families", {}).get(
        "gstpeaq_proxy_v0_6_1", {}
    )
    if (
        metric_gate.get("perceptual_metric_execution_authorized") is not False
        or metric_proxy.get("execution_authorized") is not False
        or metric_proxy.get("research_use_legal_record_present") is not False
    ):
        errors.append("predecessor metric gate is not closed")

    completion = bound.get("objective_completion_audit", {})
    if completion.get("summary", {}).get("objective_complete") is not False:
        errors.append("candidate stop cannot follow a completed objective")

    expected_access = {
        "public_primary_sources_read": True,
        "legal_advice_obtained": False,
        "licence_negotiation_authorized": False,
        "rights_holder_contact_authorized": False,
        "gstpeaq_download_authorized": False,
        "gstpeaq_build_authorized": False,
        "gstpeaq_execution_authorized": False,
        "audio_access_authorized": False,
        "perceptual_metric_execution_authorized": False,
        "metric_score_access_authorized": False,
        "listening_score_access_authorized": False,
        "human_collection_authorized": False,
        "sealed_evidence_access_authorized": False,
        "no_reference_training_authorized": False,
        "public_verdict_enabled": False,
    }
    if disposition.get("access_boundary") != expected_access:
        errors.append("access boundary differs")

    observation_access = observation.get("access_boundary", {})
    if observation_access.get("public_legal_and_repository_metadata_read") is not True:
        errors.append("public legal metadata read must be explicit")
    for key in (
        "gstpeaq_source_or_binary_downloaded_to_research_storage",
        "gstpeaq_built",
        "gstpeaq_executed",
        "audio_accessed",
        "metric_score_opened",
        "listening_score_opened",
        "sealed_evidence_opened",
        "legal_advice_obtained",
    ):
        if observation_access.get(key) is not False:
            errors.append(f"observation access boundary must remain false: {key}")

    repository = observation.get("gstpeaq_repository", {})
    if repository.get("frozen_commit") != (
        "c6e8b23d3374dbc937ef9f7cfbdb3b3f4c864352"
    ):
        errors.append("GstPEAQ commit differs")
    if repository.get("readme_sha256") != (
        "bf2a8afc21a8cb27b1270aff34525abdf67d01b85e3a85987f34408377ab8ce1"
    ):
        errors.append("GstPEAQ README binding differs")
    if repository.get("copying_sha256") != (
        "94b03f1a60a7fd5007149530626a895a6ef5a8b9342abfd56860c5f3956f5d23"
    ):
        errors.append("GstPEAQ COPYING binding differs")
    if repository.get("readme_declares_values_outside_allowed_itu_tolerance") is not True:
        errors.append("GstPEAQ nonconformance declaration differs")
    for key in (
        "software_copyright_licence_is_patent_consent",
        "software_copyright_licence_proves_itu_technology_clearance",
    ):
        if repository.get(key) is not False:
            errors.append(f"software licence boundary must remain false: {key}")

    recommendation = observation.get("itu_recommendation", {})
    if (
        recommendation.get("recommendation") != "ITU-R BS.1387-2"
        or recommendation.get("status") != "in_force_main"
        or recommendation.get("document_sha256")
        != "ffe3ce073c483fb29c573a3158aa73c6536856468a9539e8b292ef9a0389f135"
    ):
        errors.append("in-force ITU recommendation binding differs")
    for key in (
        "document_says_technology_protected_by_international_patents",
        "document_says_prior_owner_consent_by_licence_is_mandatory",
        "document_directs_implementers_to_itu_r_patent_database_or_br_secretariat",
    ):
        if recommendation.get(key) is not True:
            errors.append(f"ITU recommendation finding differs: {key}")

    patent_database = observation.get("itu_patent_database", {})
    if (
        patent_database.get("returned_record_count") != 8
        or patent_database.get("returned_policy") != "2.2"
        or patent_database.get("response_sha256")
        != "018a0e2e7953e86a82004de271f42be1b3a5c5f24451e893dc793aa154545fe7"
    ):
        errors.append("ITU patent database observation differs")
    if patent_database.get("returned_organizations") != [
        "Berkom",
        "CCETT",
        "CRC",
        "Fraunhofer",
        "IRT",
        "KPN NV",
        "OPTICOM",
        "TU Berlin",
    ]:
        errors.append("ITU declaration organizations differ")
    for key in (
        "database_certified_accurate",
        "database_certified_complete",
        "database_proves_current_patent_validity_or_scope",
        "database_proves_a_licence_was_granted_to_lossytrace",
    ):
        if patent_database.get(key) is not False:
            errors.append(f"ITU database limit must remain false: {key}")

    experimental = observation.get("australian_experimental_use_context", {})
    if experimental.get("provision") != "Patents Act 1990 section 119C":
        errors.append("Australian experimental-use provision differs")
    if experimental.get(
        "provision_contains_exemption_for_experimental_purposes_relating_to_subject_matter_of_invention"
    ) is not True:
        errors.append("Australian experimental-use text finding differs")
    for key in (
        "using_metric_as_tool_is_experiment_on_subject_matter_established",
        "provision_clears_lossytrace_use_without_fact_specific_legal_review",
        "jurisdictions_outside_australia_addressed",
    ):
        if experimental.get(key) is not False:
            errors.append(f"experimental-use limit must remain false: {key}")

    findings = disposition.get("findings", {})
    expected_true = (
        "software_copyright_licence_identified",
        "software_copyright_licence_is_separate_from_itu_technology_consent",
        "upstream_declares_nonconformance_to_itu_tolerance",
        "in_force_recommendation_requires_prior_owner_consent_by_licence",
        "itu_database_returns_eight_policy_2_2_declarations",
    )
    expected_false = (
        "policy_2_2_is_automatic_permission",
        "lossytrace_has_evidence_of_negotiated_licence",
        "itu_database_can_authoritatively_resolve_current_validity_and_scope",
        "public_sources_clear_internal_research_execution",
        "public_sources_clear_binary_redistribution",
        "australian_experimental_use_clearly_applies_to_metric_as_research_tool",
        "fact_specific_legal_review_complete",
    )
    for key in expected_true:
        if findings.get(key) is not True:
            errors.append(f"finding must remain true: {key}")
    for key in expected_false:
        if findings.get(key) is not False:
            errors.append(f"finding must remain false: {key}")

    frozen = disposition.get("frozen_disposition", {})
    for key in (
        "gstpeaq_proxy_legal_gate_passed",
        "gstpeaq_proxy_conformance_gate_passed",
        "gstpeaq_proxy_execution_eligible",
        "gstpeaq_proxy_redistribution_eligible",
        "current_two_primary_family_candidate_may_advance",
        "proxy_failure_is_full_objective_negative_result",
        "full_reference_oracle_rejected_by_human_evidence",
        "no_reference_work_eligible",
        "final_recommendation_frozen",
    ):
        if frozen.get(key) is not False:
            errors.append(f"frozen disposition must remain false: {key}")
    if frozen.get("current_two_primary_family_candidate_stop_condition_triggered") is not True:
        errors.append("current two-family stop condition must be triggered")

    options = disposition.get("successor_options", [])
    if [option.get("option_id") for option in options] != [
        "qualified_legal_clearance",
        "preregister_simpler_full_reference_successor",
        "reject_current_full_reference_candidate",
    ]:
        errors.append("successor options differ")
    for option in options:
        if option.get("requires_responsible_human_authority") is not True:
            errors.append(f"successor option lacks human authority: {option.get('option_id')}")
        if option.get("execution_authorized_by_this_disposition") is not False:
            errors.append(f"successor option prematurely authorizes execution: {option.get('option_id')}")

    decision = disposition.get("decision", {})
    if decision.get("selected_successor_option") is not None:
        errors.append("successor option was prematurely selected")
    if decision.get("current_metric_gate_remains_closed") is not True:
        errors.append("current metric gate must remain closed")
    if decision.get("silent_family_replacement_forbidden") is not True:
        errors.append("silent family replacement must remain forbidden")
    if decision.get("post_hoc_replacement_after_outcomes_forbidden") is not True:
        errors.append("post-hoc family replacement must remain forbidden")
    if decision.get("rights_holder_contact_or_legal_spend_authorized") is not False:
        errors.append("rights-holder contact or legal spend was prematurely authorized")

    for key, value in disposition.get("claim_boundary", {}).items():
        if value is not False:
            errors.append(f"claim boundary must remain false: {key}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--disposition", type=Path, default=DEFAULT_DISPOSITION)
    args = parser.parse_args()
    errors = validate(load_json(args.disposition))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"validated {args.disposition}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
