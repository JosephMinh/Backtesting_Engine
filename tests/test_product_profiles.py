import json
import math
import unittest
from pathlib import Path

from shared.policy.posture import APPROVED_POSTURE
from shared.policy.product_profiles import (
    ACCOUNT_RISK_PROFILES,
    PRODUCT_PROFILES,
    BindingStatus,
    BrokerContractDescriptor,
    OperatingPosture,
    ProductLane,
    ProfileBindingRequest,
    VALIDATION_ERRORS,
    account_risk_profiles_by_id,
    product_profiles_by_id,
    validate_profile_binding,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "product_profiles.json"
)


def load_binding_cases() -> list[dict[str, object]]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)["binding_cases"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"product profile fixture failed to load: {exc}") from exc


class ProductProfileContractTest(unittest.TestCase):
    def test_profile_catalog_has_no_validation_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_initial_product_profiles_are_present_and_explicit(self) -> None:
        profiles = product_profiles_by_id()
        self.assertEqual({"mgc_comex_v1", "oneoz_comex_v1"}, set(profiles))

        mgc = profiles["mgc_comex_v1"]
        self.assertEqual("MGC", mgc.contract_specification.symbol)
        self.assertEqual("COMEX", mgc.contract_specification.exchange)
        self.assertEqual(10, mgc.contract_specification.contract_size_oz)
        self.assertEqual(0.10, mgc.contract_specification.minimum_price_fluctuation_usd_per_oz)
        self.assertEqual(1.0, mgc.contract_specification.tick_value_usd)
        self.assertEqual((ProductLane.RESEARCH,), mgc.supported_lanes)
        self.assertTrue(mgc.approved_data_profile_releases)

        oneoz = profiles["oneoz_comex_v1"]
        self.assertEqual(APPROVED_POSTURE.execution_symbol, oneoz.contract_specification.symbol)
        self.assertEqual("COMEX", oneoz.contract_specification.exchange)
        self.assertEqual(1, oneoz.contract_specification.contract_size_oz)
        self.assertEqual(0.25, oneoz.contract_specification.minimum_price_fluctuation_usd_per_oz)
        self.assertEqual(0.25, oneoz.contract_specification.tick_value_usd)
        self.assertIn(ProductLane.LIVE, oneoz.supported_lanes)
        self.assertEqual(
            "compiled_exchange_calendars",
            oneoz.session_policy.exchange_calendar_source,
        )
        self.assertEqual(
            "resolved_context_bundles",
            oneoz.session_policy.event_window_source,
        )

    def test_initial_account_profile_matches_small_account_posture(self) -> None:
        account = account_risk_profiles_by_id()["solo_small_gold_ibkr_5000_v1"]
        self.assertEqual(APPROVED_POSTURE.broker, account.broker)
        self.assertEqual(APPROVED_POSTURE.max_account_value_usd, account.approved_starting_equity_usd)
        self.assertEqual((APPROVED_POSTURE.execution_symbol,), account.approved_symbols)
        self.assertEqual(1, account.approved_starting_size_by_symbol[APPROVED_POSTURE.execution_symbol])
        self.assertEqual(1, account.max_position_size_by_symbol[APPROVED_POSTURE.execution_symbol])
        self.assertEqual(0.25, account.max_initial_margin_fraction)
        self.assertEqual(0.35, account.max_maintenance_margin_fraction)
        self.assertEqual(0.025, account.daily_loss_lockout_fraction)
        self.assertEqual(0.15, account.max_drawdown_fraction)
        self.assertEqual(0.05, account.overnight_gap_stress_fraction)
        self.assertEqual(
            OperatingPosture.INTRADAY_FLAT_DEFAULT,
            account.default_operating_posture,
        )
        self.assertTrue(account.overnight_only_with_strict_class)

    def test_binding_fixture_cases_emit_expected_status_and_reason_codes(self) -> None:
        for payload in load_binding_cases():
            with self.subTest(case_id=payload["case_id"]):
                request = ProfileBindingRequest(
                    case_id=payload["case_id"],
                    product_profile_id=payload["product_profile_id"],
                    account_profile_id=payload["account_profile_id"],
                    requested_lane=ProductLane(payload["requested_lane"]),
                    requested_symbol=payload["requested_symbol"],
                    requested_broker=payload["requested_broker"],
                    requested_data_profile_release_id=payload["requested_data_profile_release_id"],
                    requested_contract_count=payload["requested_contract_count"],
                    requested_initial_margin_fraction=payload["requested_initial_margin_fraction"],
                    requested_maintenance_margin_fraction=payload["requested_maintenance_margin_fraction"],
                    requested_operating_posture=OperatingPosture(payload["requested_operating_posture"]),
                    overnight_requested=payload["overnight_requested"],
                    broker_contract_descriptor=BrokerContractDescriptor(
                        **payload["broker_contract_descriptor"]
                    ),
                )
                report = validate_profile_binding(request)
                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)
                self.assertEqual(
                    sorted(payload["expected_difference_keys"]),
                    sorted(report.differences.keys()),
                )

    def test_binding_reports_are_structured_and_operator_readable(self) -> None:
        request = ProfileBindingRequest(
            case_id="report_shape",
            product_profile_id="oneoz_comex_v1",
            account_profile_id="solo_small_gold_ibkr_5000_v1",
            requested_lane=ProductLane.LIVE,
            requested_symbol="1OZ",
            requested_broker="IBKR",
            requested_data_profile_release_id="ibkr_1oz_comex_bars_1m_v1",
            requested_contract_count=1,
            requested_initial_margin_fraction=0.2,
            requested_maintenance_margin_fraction=0.3,
            requested_operating_posture=OperatingPosture.INTRADAY_FLAT_DEFAULT,
            overnight_requested=False,
            broker_contract_descriptor=BrokerContractDescriptor(
                symbol="1OZ",
                exchange="COMEX",
                currency="USD",
                contract_size_oz=1,
                minimum_price_fluctuation_usd_per_oz=0.25,
                settlement_type="cash_settled",
                session_calendar_id="comex_metals_globex_v1",
            ),
        )

        report = validate_profile_binding(request)
        payload = report.to_dict()
        self.assertEqual(BindingStatus.PASS.value, report.status)
        self.assertTrue(
            {
                "case_id",
                "status",
                "reason_code",
                "product_profile_id",
                "account_profile_id",
                "differences",
                "remediation",
                "explanation",
                "timestamp",
            }.issubset(payload.keys())
        )
        self.assertIn("admissible", report.explanation.lower())

    def test_binding_rejects_negative_or_inverted_margin_requests(self) -> None:
        negative_initial = validate_profile_binding(
            ProfileBindingRequest(
                case_id="negative_initial_margin",
                product_profile_id="oneoz_comex_v1",
                account_profile_id="solo_small_gold_ibkr_5000_v1",
                requested_lane=ProductLane.LIVE,
                requested_symbol="1OZ",
                requested_broker="IBKR",
                requested_data_profile_release_id="ibkr_1oz_comex_bars_1m_v1",
                requested_contract_count=1,
                requested_initial_margin_fraction=-0.1,
                requested_maintenance_margin_fraction=0.3,
                requested_operating_posture=OperatingPosture.INTRADAY_FLAT_DEFAULT,
                overnight_requested=False,
                broker_contract_descriptor=BrokerContractDescriptor(
                    symbol="1OZ",
                    exchange="COMEX",
                    currency="USD",
                    contract_size_oz=1,
                    minimum_price_fluctuation_usd_per_oz=0.25,
                    settlement_type="cash_settled",
                    session_calendar_id="comex_metals_globex_v1",
                ),
            )
        )
        self.assertEqual(BindingStatus.INCOMPATIBLE.value, negative_initial.status)
        self.assertIn(
            "requested_initial_margin_fraction",
            negative_initial.differences,
        )

        inverted_margins = validate_profile_binding(
            ProfileBindingRequest(
                case_id="inverted_margin_pair",
                product_profile_id="oneoz_comex_v1",
                account_profile_id="solo_small_gold_ibkr_5000_v1",
                requested_lane=ProductLane.LIVE,
                requested_symbol="1OZ",
                requested_broker="IBKR",
                requested_data_profile_release_id="ibkr_1oz_comex_bars_1m_v1",
                requested_contract_count=1,
                requested_initial_margin_fraction=0.2,
                requested_maintenance_margin_fraction=0.1,
                requested_operating_posture=OperatingPosture.INTRADAY_FLAT_DEFAULT,
                overnight_requested=False,
                broker_contract_descriptor=BrokerContractDescriptor(
                    symbol="1OZ",
                    exchange="COMEX",
                    currency="USD",
                    contract_size_oz=1,
                    minimum_price_fluctuation_usd_per_oz=0.25,
                    settlement_type="cash_settled",
                    session_calendar_id="comex_metals_globex_v1",
                ),
            )
        )
        self.assertEqual(BindingStatus.INCOMPATIBLE.value, inverted_margins.status)
        self.assertIn(
            "requested_maintenance_margin_fraction",
            inverted_margins.differences,
        )

    def test_binding_rejects_non_finite_margin_requests(self) -> None:
        nan_initial = validate_profile_binding(
            ProfileBindingRequest(
                case_id="nan_initial_margin",
                product_profile_id="oneoz_comex_v1",
                account_profile_id="solo_small_gold_ibkr_5000_v1",
                requested_lane=ProductLane.LIVE,
                requested_symbol="1OZ",
                requested_broker="IBKR",
                requested_data_profile_release_id="ibkr_1oz_comex_bars_1m_v1",
                requested_contract_count=1,
                requested_initial_margin_fraction=math.nan,
                requested_maintenance_margin_fraction=0.3,
                requested_operating_posture=OperatingPosture.INTRADAY_FLAT_DEFAULT,
                overnight_requested=False,
                broker_contract_descriptor=BrokerContractDescriptor(
                    symbol="1OZ",
                    exchange="COMEX",
                    currency="USD",
                    contract_size_oz=1,
                    minimum_price_fluctuation_usd_per_oz=0.25,
                    settlement_type="cash_settled",
                    session_calendar_id="comex_metals_globex_v1",
                ),
            )
        )
        self.assertEqual(BindingStatus.INCOMPATIBLE.value, nan_initial.status)
        self.assertIn(
            "requested_initial_margin_fraction",
            nan_initial.differences,
        )

        nan_maintenance = validate_profile_binding(
            ProfileBindingRequest(
                case_id="nan_maintenance_margin",
                product_profile_id="oneoz_comex_v1",
                account_profile_id="solo_small_gold_ibkr_5000_v1",
                requested_lane=ProductLane.LIVE,
                requested_symbol="1OZ",
                requested_broker="IBKR",
                requested_data_profile_release_id="ibkr_1oz_comex_bars_1m_v1",
                requested_contract_count=1,
                requested_initial_margin_fraction=0.2,
                requested_maintenance_margin_fraction=math.nan,
                requested_operating_posture=OperatingPosture.INTRADAY_FLAT_DEFAULT,
                overnight_requested=False,
                broker_contract_descriptor=BrokerContractDescriptor(
                    symbol="1OZ",
                    exchange="COMEX",
                    currency="USD",
                    contract_size_oz=1,
                    minimum_price_fluctuation_usd_per_oz=0.25,
                    settlement_type="cash_settled",
                    session_calendar_id="comex_metals_globex_v1",
                ),
            )
        )
        self.assertEqual(BindingStatus.INCOMPATIBLE.value, nan_maintenance.status)
        self.assertIn(
            "requested_maintenance_margin_fraction",
            nan_maintenance.differences,
        )

    def test_catalog_counts_remain_narrow_and_explicit(self) -> None:
        self.assertEqual(2, len(PRODUCT_PROFILES))
        self.assertEqual(1, len(ACCOUNT_RISK_PROFILES))


if __name__ == "__main__":
    unittest.main()
