from app.use_cases.kyc_kyb.data_generation import write_artifacts
from app.use_cases.kyc_kyb.extraction import extract_packages
from app.use_cases.kyc_kyb.raw_data import load_packages
from app.use_cases.kyc_kyb.rules import evaluate_all_rules


def _package_with_flag(flag: str):
    return next(package for package in load_packages() if flag in package.expected_rule_flags)


def test_kyc_kyb_rules_detect_individual_failures() -> None:
    write_artifacts()
    packages = [
        _package_with_flag("expired_identity_document"),
        _package_with_flag("missing_tax_certification"),
        _package_with_flag("address_mismatch"),
        _package_with_flag("high_risk_jurisdiction"),
    ]
    documents, stats = extract_packages(packages)
    findings = evaluate_all_rules(packages, documents)

    failed_by_package = {
        package.package_id: {finding.rule_id for finding in findings if finding.package_id == package.package_id and finding.status == "failed"}
        for package in packages
    }
    assert "expired_identity_document" in failed_by_package[packages[0].package_id]
    assert "missing_tax_certification" in failed_by_package[packages[1].package_id]
    assert "address_mismatch" in failed_by_package[packages[2].package_id]
    assert "high_risk_jurisdiction" in failed_by_package[packages[3].package_id]
    assert stats.fallback_count == 0


def test_kyc_kyb_rules_detect_business_failures() -> None:
    write_artifacts()
    packages = [
        _package_with_flag("missing_beneficial_owner"),
        _package_with_flag("signatory_id_expired"),
        _package_with_flag("risk_attestation_missing"),
    ]
    documents, _ = extract_packages(packages)
    findings = evaluate_all_rules(packages, documents)

    failed = {
        package.package_id: {finding.rule_id for finding in findings if finding.package_id == package.package_id and finding.status == "failed"}
        for package in packages
    }
    assert "missing_beneficial_owner" in failed[packages[0].package_id]
    assert "signatory_id_expired" in failed[packages[1].package_id]
    assert "risk_attestation_missing" in failed[packages[2].package_id]
