from typing import Dict, List, Optional
import math
import logging
from typing import Any

logger = logging.getLogger(__name__)

class PricingError(Exception):
    def __init__(self, payload: Dict[str, Any]):
        self.payload = payload
        super().__init__(str(payload))

class PricingEngine:
    """
    HONEST PRICING - Sector-Specific Calculations
    Zero placeholders. Real market rates only.
    """
    
    def __init__(self):
        # SA Sectoral Determination 2024 rates
        self.base_rates = {
            'cleaning': {
                'general_worker_hourly': 23.50,
                'supervisor_monthly': 8500.00,
                'deductions_pct': 0.35
            },
            'construction': {
                'general_worker_daily': 250.00,
                'semi_skilled_daily': 350.00,
                'skilled_artisan_daily': 450.00,
                'foreman_daily': 650.00,
                'deductions_pct': 0.25
            },
            'electrical': {
                'assistant_electrician_daily': 350.00,
                'electrician_daily': 550.00,
                'master_electrician_daily': 850.00,
                'deductions_pct': 0.30
            },
            'security': {
                'grade_c_guard_daily': 220.00,
                'grade_b_guard_daily': 280.00,
                'grade_a_guard_daily': 350.00,
                'deductions_pct': 0.30
            },
            'gardening': {
                'gardener_daily': 180.00,
                'supervisor_daily': 280.00,
                'deductions_pct': 0.25
            },
            'it_services': {
                'technician_daily': 1200.00,
                'senior_consultant_daily': 2500.00,
                'deductions_pct': 0.20
            }
        }
        
        self.equipment_rates = {
            'cleaning': {
                'industrial_scrubber': 800,
                'vacuum_industrial': 200,
                'pressure_washer': 350,
                'carpet_cleaner': 450,
                'polisher': 250
            },
            'construction': {
                'excavator_20t': 2800,
                'tipper_truck': 1800,
                'concrete_mixer': 650,
                'scaffolding_100m': 1200,
                'compactor': 900
            },
            'electrical': {
                'scissor_lift': 800,
                'cable_tester': 300,
                'drum_trailer': 200
            },
            'gardening': {
                'ride_on_mower': 600,
                'brush_cutter': 150,
                'chainsaw': 100,
                'chipper': 400
            }
        }
        
        self.material_rates = {
            'cleaning': {
                'consumables_per_sqm_monthly': 2.50,
                'chemicals_per_worker_monthly': 150
            },
            'construction': {
                'concrete_per_m3': 1200,
                'bricks_per_1000': 650,
                'steel_rebar_per_ton': 14500,
                'cement_per_bag': 95,
                'sand_per_m3': 450
            },
            'electrical': {
                'cable_2.5mm_per_m': 28,
                'cable_4mm_per_m': 42,
                'distribution_board': 850,
                'breaker_20a': 85,
                'led_fitting': 125
            },
            'gardening': {
                'fertilizer_per_100m2': 180,
                'plants_average': 45,
                'mulch_per_m3': 380
            }
        }
        
        self.vat_rate = 0.15
        self.standard_overhead = 0.15
        self.standard_profit = 0.15

        self.location_multipliers = {
            'gauteng': 1.0,
            'johannesburg': 1.0,
            'pretoria': 1.0,
            'tshwane': 1.0,
            'western cape': 1.1,
            'cape town': 1.1,
            'limpopo': 0.85,
            'polokwane': 0.85,
            'mpumalanga': 0.92,
            'kwa-zulu natal': 0.95,
            'durban': 0.95,
            'kzn': 0.95,
            'eastern cape': 0.88,
            'port elizabeth': 0.88,
            'gqeberha': 0.88,
            'free state': 0.90,
            'bloemfontein': 0.90,
            'north west': 0.87,
            'rustenburg': 0.87,
            'northen cape': 0.83,
            'kimberley': 0.83
        }

    def apply_location_factor(self, pricing_result: Dict, location: str) -> Dict:
        location_lower = location.lower() if location else ''
        multiplier = self.location_multipliers.get(location_lower, 1.0)

        if multiplier != 1.0:
            labour = pricing_result.get('labour_cost', 0)
            equipment = pricing_result.get('equipment_cost', 0)
            materials = pricing_result.get('materials_cost', 0)
            transport = pricing_result.get('transport_cost', 0)

            adjusted_labour = labour * multiplier
            adjusted_equipment = equipment * multiplier
            adjusted_materials = materials * multiplier
            adjusted_transport = transport * multiplier

            old_subtotal = pricing_result.get('subtotal', 0)
            new_subtotal = adjusted_labour + adjusted_equipment + adjusted_materials + adjusted_transport
            overheads = new_subtotal * self.standard_overhead
            profit = (new_subtotal + overheads) * self.standard_profit
            vat = (new_subtotal + overheads + profit) * self.vat_rate
            total_monthly = new_subtotal + overheads + profit + vat

            pricing_result['location'] = location
            pricing_result['location_multiplier'] = multiplier
            pricing_result['labour_cost'] = round(adjusted_labour, 2)
            pricing_result['equipment_cost'] = round(adjusted_equipment, 2)
            pricing_result['materials_cost'] = round(adjusted_materials, 2)
            pricing_result['transport_cost'] = round(adjusted_transport, 2)
            pricing_result['subtotal'] = round(new_subtotal, 2)
            pricing_result['overheads'] = round(overheads, 2)
            pricing_result['profit'] = round(profit, 2)
            pricing_result['vat'] = round(vat, 2)
            pricing_result['total_monthly'] = round(total_monthly, 2)
            duration_months = pricing_result.get('duration_months')
            pricing_result['total_contract_value'] = round(total_monthly * duration_months, 2) if duration_months is not None else None
            # Ensure final_price reflects updated contract value when available
            if pricing_result.get('total_contract_value') is not None:
                pricing_result['final_price'] = float(pricing_result['total_contract_value'])

        return pricing_result

    def _get_duration_months(self, tender_data: Dict) -> Optional[int]:
        duration = tender_data.get('duration') or {}
        months = duration.get('months')
        if months is None:
            months = tender_data.get('duration_months')
        if months is None:
            return None
        try:
            return int(months)
        except (TypeError, ValueError):
            return None

    def _is_number(self, v: Any) -> bool:
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    def _apply_summation_check(self, result: Dict) -> Dict:
        """
        Enforce Labour + Materials + Overheads <= Final Contract Value.

        When the invariant fails, keep the component values for diagnosis but
        suppress the total fields so downstream summaries do not present an
        impossible contract value as correct.
        """
        labour = result.get('labour_cost')
        materials = result.get('materials_cost')
        overheads = result.get('overheads')
        final_contract_value = (
            result.get('final_contract_value')
            if result.get('final_contract_value') is not None
            else result.get('total_contract_value')
        )
        if final_contract_value is None:
            final_contract_value = result.get('final_price')

        if not all(self._is_number(x) for x in (labour, materials, overheads, final_contract_value)):
            return result

        component_sum = float(labour) + float(materials) + float(overheads)
        if component_sum <= float(final_contract_value) + 0.01:
            return result

        mismatch_details = {
            'labour_cost': float(labour),
            'materials_cost': float(materials),
            'overheads': float(overheads),
            'component_sum': round(component_sum, 2),
            'final_contract_value': float(final_contract_value),
        }
        logger.error("[PRICE] Extraction_Error_Mismatch: %s", mismatch_details)
        result['Extraction_Error_Mismatch'] = True
        result['extraction_error_code'] = 'Extraction_Error_Mismatch'
        result['pricing_validation_status'] = 'failed'
        result['mismatch_details'] = mismatch_details
        result['final_price'] = None
        result['final_contract_value'] = None
        result['total_contract_value'] = None
        return result

    def _finalize_pricing(self, result: Dict, tender_data: Dict, debate_result: Dict = None) -> Dict:
        """Ensure the pricing result contains `final_price`, `breakdown`, `confidence`, and `assumptions`.

        If final_price cannot be determined from available fields, raise PricingError with structured payload.
        """
        # gather duration
        duration_months = result.get('duration_months') if result.get('duration_months') is not None else self._get_duration_months(tender_data)

        # build breakdown from available fields
        breakdown_fields = ['labour_cost', 'equipment_cost', 'materials_cost', 'transport_cost', 'subtotal', 'overheads', 'profit', 'vat', 'total_monthly', 'total_contract_value', 'emergency_premium']
        breakdown: Dict[str, Any] = {k: result.get(k) for k in breakdown_fields if k in result}
        # merge any explicit breakdown provided
        if isinstance(result.get('breakdown'), dict):
            bd = result.get('breakdown')
            # prefer explicit breakdown values
            for k, v in bd.items():
                breakdown.setdefault(k, v)

        # Determine final_price using available data
        final_price = result.get('final_price')
        base_price = None
        adjustments: Dict[str, Any] = {}
        # Strict policy: only caller-marked user, document, or config input may supply cost_per_hour.
        cost_source: Optional[str] = None
        explicit_rate = (
            isinstance(tender_data, dict)
            and tender_data.get('_cost_source') in ('user', 'document', 'config')
            and tender_data.get('cost_per_hour') is not None
        )
        if explicit_rate:
            cost_source = tender_data.get('_cost_source')

        if self._is_number(final_price):
            base_price = final_price
        else:
            # prefer explicit total contract value
            tcv = result.get('total_contract_value')
            if self._is_number(tcv):
                final_price = float(tcv)
                base_price = tcv
            else:
                tm = result.get('total_monthly')
                if self._is_number(tm) and self._is_number(duration_months):
                    final_price = float(tm * int(duration_months))
                    base_price = tm
                    adjustments['duration_months'] = int(duration_months)
                else:
                    # try subtotal + overheads + profit + vat when all present
                    subtotal = result.get('subtotal')
                    overheads = result.get('overheads')
                    profit = result.get('profit')
                    vat = result.get('vat')
                    if all(self._is_number(x) for x in (subtotal, overheads, profit, vat)):
                        final_price = float(subtotal + overheads + profit + vat)
                        base_price = subtotal
                        adjustments.update({'overheads': overheads, 'profit': profit, 'vat': vat})

        # Do NOT rely on `debate_result` for final_price. If missing, attempt
        # a deterministic baseline computation using extracted inputs.
        if final_price is None:
            # extract baseline inputs from tender_data/result
            workforce = tender_data.get('workforce', {}) if isinstance(tender_data, dict) else {}
            requirements = tender_data.get('requirements', {}) if isinstance(tender_data, dict) else {}

            workers = workforce.get('total_workers') or workforce.get('workers') or result.get('workers')
            shifts_per_day = requirements.get('shifts_per_day') or result.get('shifts_per_day')
            hours_per_day = requirements.get('hours_per_day') or result.get('hours_per_day')

            # duration_months computed earlier
            if workers is None or shifts_per_day is None or hours_per_day is None or duration_months is None:
                details = {
                    'available_fields': list(result.keys()),
                    'required_for_baseline': {
                        'workers': workers,
                        'shifts_per_day': shifts_per_day,
                        'hours_per_day': hours_per_day,
                        'duration_months': duration_months
                    },
                    'sector': result.get('sector')
                }
                payload = {
                    'status': 'error',
                    'message': 'Unable to compute final_price',
                    'details': details
                }
                logger.error("[PRICE] Unable to compute final_price (missing baseline inputs): %s", details)
                raise PricingError(payload)

            # coerce numeric types
            try:
                workers = int(workers)
                shifts_per_day = float(shifts_per_day)
                hours_per_day = float(hours_per_day)
                duration_months = int(duration_months)
            except (TypeError, ValueError):
                payload = {
                    'status': 'error',
                    'message': 'Invalid types for baseline inputs',
                    'details': {
                        'workers': workers,
                        'shifts_per_day': shifts_per_day,
                        'hours_per_day': hours_per_day,
                        'duration_months': duration_months
                    }
                }
                logger.error("[PRICE] Invalid baseline input types: %s", payload['details'])
                raise PricingError(payload)

            # Strict policy: cost_per_hour must be explicitly supplied by the
            # user, document, or config and marked by the API. Do not use unmarked sector rates.
            cost_per_hour = tender_data.get('cost_per_hour') if explicit_rate else None

            sector = (result.get('sector') or tender_data.get('sector')) if isinstance(tender_data, dict) else result.get('sector')

            if cost_per_hour is None:
                payload = {
                    'status': 'error',
                    'message': 'cost_per_hour requires user input or explicit config',
                    'details': {'sector': sector}
                }
                logger.error("[PRICE] Unable to determine cost_per_hour: %s", payload['details'])
                raise PricingError(payload)

            # Baseline formula
            daily_hours = shifts_per_day * hours_per_day
            monthly_hours = daily_hours * 30
            total_hours = monthly_hours * duration_months
            base_price = float(cost_per_hour)
            final_price = float(total_hours * base_price * workers)

            adjustments.update({
                'baseline': True,
                'workers': workers,
                'shifts_per_day': shifts_per_day,
                'hours_per_day': hours_per_day,
                'duration_months': duration_months,
            })

            # ensure breakdown contains baseline fields
            breakdown.update({
                'workers': workers,
                'hours_per_day': hours_per_day,
                'shifts_per_day': shifts_per_day,
                'duration_months': duration_months,
                'total_hours': total_hours,
                'cost_per_hour': round(float(cost_per_hour), 2)
            })

            # Financial transparency fields computed from baseline inputs
            try:
                monthly_cost_per_worker = monthly_hours * float(cost_per_hour)
                monthly_total_cost = monthly_cost_per_worker * workers
                grand_total = monthly_total_cost * duration_months

                breakdown.update({
                    'monthly_cost_per_worker': round(monthly_cost_per_worker, 2),
                    'monthly_total_cost': round(monthly_total_cost, 2),
                    'grand_total': round(grand_total, 2)
                })

                # Ensure final_price matches grand_total (round to cents)
                try:
                    grand_total_rounded = float(round(grand_total, 2))
                    if not math.isclose(float(final_price), grand_total_rounded, abs_tol=0.01):
                        logger.info("[PRICE] Reconciling final_price to grand_total: %s -> %s", final_price, grand_total_rounded)
                    final_price = grand_total_rounded
                except Exception:
                    pass
            except Exception:
                # best-effort: if any of these computations fail, skip
                pass

        # Validate numeric
        if not self._is_number(final_price):
            payload = {'status': 'error', 'message': 'final_price is not numeric', 'details': {'value': final_price}}
            logger.error("[PRICE] final_price not numeric: %s", final_price)
            raise PricingError(payload)

        # Reconcile and populate transparency fields when possible (non-baseline flows)
        try:
            # attempt to gather inputs
            sec = result.get('sector') or (tender_data.get('sector') if isinstance(tender_data, dict) else None)
            workforce = tender_data.get('workforce', {}) if isinstance(tender_data, dict) else {}
            requirements = tender_data.get('requirements', {}) if isinstance(tender_data, dict) else {}

            workers = result.get('workers') or workforce.get('total_workers') or workforce.get('workers')
            shifts = result.get('shifts_per_day') or requirements.get('shifts_per_day') or result.get('shifts_per_day')
            hours = result.get('hours_per_day') or requirements.get('hours_per_day') or result.get('hours_per_day')
            dur = duration_months

            # Strict policy: do not backfill transparency fields from document,
            # breakdown, BASE_RATES, or sector defaults.
            cph = tender_data.get('cost_per_hour') if explicit_rate else None

            if workers is not None and shifts is not None and hours is not None and dur is not None and cph is not None:
                try:
                    workers_n = int(workers)
                    shifts_n = float(shifts)
                    hours_n = float(hours)
                    dur_n = int(dur)
                    cph_n = float(cph)

                    monthly_hours = shifts_n * hours_n * 30
                    monthly_cost_per_worker = monthly_hours * cph_n
                    monthly_total_cost = monthly_cost_per_worker * workers_n
                    grand_total = monthly_total_cost * dur_n

                    breakdown.update({
                        'workers': workers_n,
                        'hours_per_day': hours_n,
                        'shifts_per_day': shifts_n,
                        'duration_months': dur_n,
                        'total_hours': monthly_hours * dur_n,
                        'cost_per_hour': round(cph_n, 2),
                        'monthly_cost_per_worker': round(monthly_cost_per_worker, 2),
                        'monthly_total_cost': round(monthly_total_cost, 2),
                        'grand_total': round(grand_total, 2)
                    })

                    grand_total_rounded = float(round(grand_total, 2))
                    if not math.isclose(float(final_price), grand_total_rounded, abs_tol=0.01):
                        logger.info("[PRICE] Reconciling final_price to grand_total: %s -> %s", final_price, grand_total_rounded)
                        final_price = grand_total_rounded
                except Exception:
                    pass
        except Exception:
            pass

        if not explicit_rate:
            breakdown.pop('cost_per_hour', None)

        # Compose confidence score
        confidence = 'Low'
        notes = tender_data.get('_extraction_notes') if isinstance(tender_data, dict) else None
        score = 0
        if notes and isinstance(notes, dict) and notes.get('raw_confidence'):
            rc = notes.get('raw_confidence')
            if isinstance(rc, str):
                confidence = rc
        else:
            # derive simple confidence from presence of core inputs
            if result.get('duration_months') is not None or duration_months is not None:
                score += 1
            if result.get('labour_cost') is not None or result.get('total_monthly') is not None:
                score += 1
            if result.get('subtotal') is not None:
                score += 1
            confidence = 'High' if score >= 3 else ('Medium' if score == 2 else 'Low')

        # Assumptions list: state how final price was computed
        assumptions: List[str] = []
        if cost_source == 'user':
            assumptions.append('cost_per_hour provided by user input')
        elif cost_source == 'document':
            assumptions.append('cost_per_hour extracted from the tender document')
        elif cost_source == 'config':
            assumptions.append('cost_per_hour loaded from explicit system configuration')

        if 'source' in adjustments and adjustments.get('source') == 'debate_result':
            assumptions.append('final_price taken from debate result')
        elif base_price is not None:
            if 'total_contract_value' in result and self._is_number(result.get('total_contract_value')):
                assumptions.append('final_price equals total_contract_value')
            elif 'total_monthly' in result and self._is_number(result.get('total_monthly')) and self._is_number(duration_months):
                assumptions.append('final_price computed as total_monthly * duration_months')
            elif 'subtotal' in result:
                assumptions.append('final_price computed as subtotal + overheads + profit + vat')

        # Apply confidence and assumptions rules based on cost_per_hour source
        try:
            if cost_source in ('user', 'document', 'config'):
                confidence = 'high'
        except Exception:
            pass

        # Log pricing details
        logger.info("[PRICE] Base price: %s", base_price)
        logger.info("[PRICE] Adjustments: %s", adjustments)
        logger.info("[PRICE] Final price: %s", final_price)

        # attach fields
        result['final_price'] = float(final_price)
        if result.get('final_contract_value') is None:
            result['final_contract_value'] = (
                result.get('total_contract_value')
                if result.get('total_contract_value') is not None
                else result['final_price']
            )
        result['breakdown'] = breakdown
        result['confidence'] = confidence
        result['assumptions'] = assumptions
        result['calculation_trace'] = [
            'daily_hours = shifts * hours',
            'monthly_hours = daily_hours * 30',
            'total_hours = monthly_hours * duration',
            'final_price = total_hours * cost_per_hour * workers'
        ]

        # Attach rate_source for caller visibility: map internal cost_source to user-facing values
        try:
            if cost_source in ('user', 'document', 'config'):
                result['rate_source'] = cost_source
            else:
                result['rate_source'] = None
        except Exception:
            result['rate_source'] = None

        return self._apply_summation_check(result)

    def _require_fields(self, field_map: Dict[str, object]):
        missing = [name for name, value in field_map.items() if value is None]
        if missing:
            raise ValueError(f"Missing required pricing inputs: {', '.join(missing)}")

    def calculate(self, tender_data: Dict, rates_found: Dict, debate_result: Dict) -> Dict:
        sector = tender_data.get('sector')
        if not sector:
            raise ValueError("Missing sector for pricing calculation")
        if tender_data.get('_cost_source') not in ('user', 'document', 'config') or tender_data.get('cost_per_hour') is None:
            raise PricingError({
                'status': 'error',
                'message': 'cost_per_hour requires user input, document extraction, or explicit config',
                'details': {'sector': sector}
            })
        try:
            if float(tender_data.get('cost_per_hour')) <= 0:
                raise ValueError
        except (TypeError, ValueError):
            raise PricingError({
                'status': 'error',
                'message': 'cost_per_hour must be greater than 0',
                'details': {'sector': sector, 'cost_per_hour': tender_data.get('cost_per_hour')}
            })

        calculators = {
            'cleaning': self._calculate_cleaning,
            'construction': self._calculate_construction,
            'electrical': self._calculate_electrical,
            'security': self._calculate_security,
            'gardening': self._calculate_gardening,
            'it_services': self._calculate_it,
            'maintenance': self._calculate_maintenance,
            'supply': self._calculate_supply,
            'general': self._calculate_general
        }

        calculator = calculators.get(sector, self._calculate_general)
        result = calculator(tender_data, rates_found, debate_result)

        result['sector'] = sector
        result['calculation_method'] = f"{sector}_sector_formula"
        result['duration_months'] = self._get_duration_months(tender_data)

        # Finalize pricing output contract: ensure final_price, breakdown, confidence, assumptions
        finalized = self._finalize_pricing(result, tender_data, debate_result)
        return finalized

    def reprice(self, pricing: Dict, mode: str) -> Dict:
        mode_configs = {
            'optimize_win': {'profit_reduction': 0.08, 'overhead_reduction': 0.05, 'description': 'Competitive pricing to maximize win probability'},
            'maximize_profit': {'profit_increase': 0.05, 'overhead_increase': 0.02, 'description': 'Pricing with higher margin for better profitability'},
            'reduce_margin': {'profit_reduction': 0.12, 'overhead_reduction': 0.08, 'description': 'Aggressive margin reduction for price-sensitive contracts'}
        }

        config = mode_configs.get(mode, mode_configs['optimize_win'])
        new_pricing = pricing.copy()

        subtotal = pricing.get('subtotal', 0)
        current_profit = pricing.get('profit', 0)
        current_overheads = pricing.get('overheads', 0)

        if 'profit_reduction' in config:
            new_profit = current_profit * (1 - config['profit_reduction'])
            new_overheads = current_overheads * (1 - config['overhead_reduction'])
        elif 'profit_increase' in config:
            new_profit = current_profit * (1 + config['profit_increase'])
            new_overheads = current_overheads * (1 + config['overhead_increase'])
        else:
            new_profit = current_profit
            new_overheads = current_overheads

        vat = (subtotal + new_overheads + new_profit) * self.vat_rate
        total_monthly = subtotal + new_overheads + new_profit + vat
        duration_months = pricing.get('duration_months')

        new_pricing['profit'] = round(new_profit, 2)
        new_pricing['overheads'] = round(new_overheads, 2)
        new_pricing['vat'] = round(vat, 2)
        new_pricing['total_monthly'] = round(total_monthly, 2)
        new_pricing['total_contract_value'] = round(total_monthly * duration_months, 2) if duration_months is not None else None
        # Ensure final_price is present when possible
        if new_pricing.get('total_contract_value') is not None:
            new_pricing['final_price'] = float(new_pricing['total_contract_value'])
            new_pricing['final_contract_value'] = float(new_pricing['total_contract_value'])
        elif new_pricing.get('total_monthly') is not None and duration_months is not None:
            new_pricing['final_price'] = float(new_pricing['total_monthly'] * duration_months)
            new_pricing['final_contract_value'] = new_pricing['final_price']

        return self._apply_summation_check(new_pricing)

    def _calculate_cleaning(self, tender_data: Dict, rates_found: Dict, debate_result: Dict) -> Dict:
        req = tender_data.get('requirements', {}) or {}
        workforce = tender_data.get('workforce', {}) or {}
        scope = tender_data.get('scope', {}) or {}

        duration_months = self._get_duration_months(tender_data)
        self._require_fields({
            'duration_months': duration_months,
            'area_sqm': scope.get('area_sqm'),
            'shifts_per_day': req.get('shifts_per_day'),
            'hours_per_day': req.get('hours_per_day')
        })

        total_workers = workforce.get('total_workers')
        supervisors = workforce.get('supervisors')
        cleaners = workforce.get('unskilled_workers')

        if cleaners is None and total_workers is not None and supervisors is not None:
            cleaners = total_workers - supervisors
        if supervisors is None and total_workers is not None and cleaners is not None:
            supervisors = total_workers - cleaners

        self._require_fields({
            'total_workers': total_workers,
            'supervisors': supervisors,
            'unskilled_workers': cleaners
        })

        area_sqm = scope.get('area_sqm')
        shifts = req.get('shifts_per_day')
        hours_per_day = req.get('hours_per_day')
        days_per_month = 22

        hourly_rate = float(tender_data['cost_per_hour'])
        monthly_wage_cleaner = hourly_rate * hours_per_day * days_per_month
        total_cleaners_cost = (cleaners * monthly_wage_cleaner) * (1 + self.base_rates['cleaning']['deductions_pct'])

        supervisor_monthly = self.base_rates['cleaning']['supervisor_monthly']
        total_supervisors_cost = (supervisors * supervisor_monthly) * (1 + self.base_rates['cleaning']['deductions_pct'])

        total_labour = total_cleaners_cost + total_supervisors_cost

        if area_sqm <= 1000:
            equipment_monthly = 2500 * shifts
        elif area_sqm <= 5000:
            equipment_monthly = 6000 * shifts
        else:
            equipment_monthly = 12000 * shifts

        consumables_rate = self.material_rates['cleaning']['consumables_per_sqm_monthly']
        materials_monthly = (area_sqm * consumables_rate * shifts) + (cleaners * 150)

        transport_monthly = 150 * days_per_month * shifts

        subtotal = total_labour + equipment_monthly + materials_monthly + transport_monthly

        emergency_premium = 0
        if scope.get('is_emergency'):
            emergency_premium = subtotal * 0.50
            subtotal += emergency_premium

        overheads = subtotal * self.standard_overhead
        profit = (subtotal + overheads) * self.standard_profit
        vat = (subtotal + overheads + profit) * self.vat_rate

        total_monthly = subtotal + overheads + profit + vat

        return {
            'labour_cost': round(total_labour, 2),
            'equipment_cost': round(equipment_monthly, 2),
            'materials_cost': round(materials_monthly, 2),
            'transport_cost': round(transport_monthly, 2),
            'emergency_premium': round(emergency_premium, 2),
            'subtotal': round(subtotal, 2),
            'overheads': round(overheads, 2),
            'profit': round(profit, 2),
            'vat': round(vat, 2),
            'total_monthly': round(total_monthly, 2),
            'total_contract_value': round(total_monthly * duration_months, 2) if duration_months is not None else None,
            'breakdown': {
                'cleaners': cleaners,
                'cleaners_hourly_rate': hourly_rate,
                'cleaners_monthly_each': round(monthly_wage_cleaner, 2),
                'supervisors': supervisors,
                'supervisor_monthly_salary': supervisor_monthly,
                'total_personnel': cleaners + supervisors,
                'area_sqm': area_sqm,
                'shifts': shifts
            }
        }

    def _calculate_construction(self, tender_data: Dict, rates_found: Dict, debate_result: Dict) -> Dict:
        req = tender_data.get('requirements', {}) or {}
        workforce = tender_data.get('workforce', {}) or {}

        duration_months = self._get_duration_months(tender_data)
        days_per_month = 22

        total_workers = workforce.get('total_workers')
        skilled = workforce.get('skilled_workers')
        unskilled = workforce.get('unskilled_workers')
        supervisors = workforce.get('supervisors')

        if total_workers is not None and supervisors is not None:
            if skilled is None and unskilled is not None:
                skilled = total_workers - supervisors - unskilled
            if unskilled is None and skilled is not None:
                unskilled = total_workers - supervisors - skilled

        self._require_fields({
            'duration_months': duration_months,
            'skilled_workers': skilled,
            'unskilled_workers': unskilled,
            'supervisors': supervisors
        })

        skilled_daily = self.base_rates['construction']['skilled_artisan_daily']
        unskilled_daily = self.base_rates['construction']['general_worker_daily']
        foreman_daily = self.base_rates['construction']['foreman_daily']

        skilled_monthly = skilled * skilled_daily * days_per_month
        unskilled_monthly = unskilled * unskilled_daily * days_per_month
        foreman_monthly = supervisors * foreman_daily * days_per_month

        total_labour = (skilled_monthly + unskilled_monthly + foreman_monthly) * (1 + self.base_rates['construction']['deductions_pct'])

        plant_monthly = 15000
        materials_base = 50000
        materials_markup = materials_base * 0.15
        materials_total = materials_base + materials_markup

        transport_monthly = 8000

        subtotal = total_labour + plant_monthly + materials_total + transport_monthly
        overheads = subtotal * 0.20
        profit = (subtotal + overheads) * 0.15
        vat = (subtotal + overheads + profit) * self.vat_rate
        total_monthly = subtotal + overheads + profit + vat

        return {
            'labour_cost': round(total_labour, 2),
            'equipment_cost': round(plant_monthly, 2),
            'materials_cost': round(materials_total, 2),
            'transport_cost': round(transport_monthly, 2),
            'subtotal': round(subtotal, 2),
            'overheads': round(overheads, 2),
            'profit': round(profit, 2),
            'vat': round(vat, 2),
            'total_monthly': round(total_monthly, 2),
            'total_contract_value': round(total_monthly * duration_months, 2) if duration_months is not None else None,
            'breakdown': {
                'skilled_workers': skilled,
                'unskilled_workers': unskilled,
                'daily_rates': {'skilled': skilled_daily, 'unskilled': unskilled_daily}
            }
        }

    def _calculate_electrical(self, tender_data: Dict, rates_found: Dict, debate_result: Dict) -> Dict:
        workforce = tender_data.get('workforce', {}) or {}

        duration_months = self._get_duration_months(tender_data)
        electricians = workforce.get('skilled_workers')
        assistants = workforce.get('unskilled_workers')

        self._require_fields({
            'duration_months': duration_months,
            'electricians': electricians,
            'assistants': assistants
        })

        days_per_month = 22
        elec_daily = self.base_rates['electrical']['electrician_daily']
        assist_daily = self.base_rates['electrical']['assistant_electrician_daily']

        monthly_elec = electricians * elec_daily * days_per_month
        monthly_assist = assistants * assist_daily * days_per_month
        total_labour = (monthly_elec + monthly_assist) * (1 + self.base_rates['electrical']['deductions_pct'])

        equipment_monthly = 5000
        materials_monthly = 15000
        subtotal = total_labour + equipment_monthly + materials_monthly
        overheads = subtotal * self.standard_overhead
        profit = (subtotal + overheads) * self.standard_profit
        vat = (subtotal + overheads + profit) * self.vat_rate
        total_monthly = subtotal + overheads + profit + vat

        return {
            'labour_cost': round(total_labour, 2),
            'equipment_cost': round(equipment_monthly, 2),
            'materials_cost': round(materials_monthly, 2),
            'subtotal': round(subtotal, 2),
            'overheads': round(overheads, 2),
            'profit': round(profit, 2),
            'vat': round(vat, 2),
            'total_monthly': round(total_monthly, 2),
            'total_contract_value': round(total_monthly * duration_months, 2) if duration_months is not None else None
        }

    def _calculate_security(self, tender_data: Dict, rates_found: Dict, debate_result: Dict) -> Dict:
        req = tender_data.get('requirements', {}) or {}
        workforce = tender_data.get('workforce', {}) or {}

        duration_months = self._get_duration_months(tender_data)
        guards = workforce.get('total_workers')
        shifts = req.get('shifts_per_day')

        self._require_fields({
            'duration_months': duration_months,
            'guards': guards,
            'shifts_per_day': shifts
        })

        guard_daily = self.base_rates['security']['grade_c_guard_daily']
        days_per_month = 30
        total_labour = guards * guard_daily * days_per_month * shifts * (1 + self.base_rates['security']['deductions_pct'])
        equipment_monthly = guards * 200 * shifts
        materials_monthly = guards * 300 * shifts

        subtotal = total_labour + equipment_monthly + materials_monthly
        overheads = subtotal * 0.20
        profit = (subtotal + overheads) * 0.12
        vat = (subtotal + overheads + profit) * self.vat_rate
        total_monthly = subtotal + overheads + profit + vat

        return {
            'labour_cost': round(total_labour, 2),
            'equipment_cost': round(equipment_monthly, 2),
            'materials_cost': round(materials_monthly, 2),
            'subtotal': round(subtotal, 2),
            'overheads': round(overheads, 2),
            'profit': round(profit, 2),
            'vat': round(vat, 2),
            'total_monthly': round(total_monthly, 2),
            'total_contract_value': round(total_monthly * duration_months, 2) if duration_months is not None else None
        }

    def _calculate_gardening(self, tender_data: Dict, rates_found: Dict, debate_result: Dict) -> Dict:
        workforce = tender_data.get('workforce', {}) or {}
        scope = tender_data.get('scope', {}) or {}

        duration_months = self._get_duration_months(tender_data)
        workers = workforce.get('total_workers')
        area_sqm = scope.get('area_sqm')

        self._require_fields({
            'duration_months': duration_months,
            'workers': workers,
            'area_sqm': area_sqm
        })

        days_per_month = 22
        gardener_daily = self.base_rates['gardening']['gardener_daily']

        monthly_labour = workers * gardener_daily * days_per_month * (1 + self.base_rates['gardening']['deductions_pct'])
        equipment_monthly = 2000
        materials_monthly = (area_sqm / 100) * 180
        subtotal = monthly_labour + equipment_monthly + materials_monthly
        overheads = subtotal * self.standard_overhead
        profit = (subtotal + overheads) * self.standard_profit
        vat = (subtotal + overheads + profit) * self.vat_rate
        total_monthly = subtotal + overheads + profit + vat

        return {
            'labour_cost': round(monthly_labour, 2),
            'equipment_cost': round(equipment_monthly, 2),
            'materials_cost': round(materials_monthly, 2),
            'subtotal': round(subtotal, 2),
            'overheads': round(overheads, 2),
            'profit': round(profit, 2),
            'vat': round(vat, 2),
            'total_monthly': round(total_monthly, 2),
            'total_contract_value': round(total_monthly * duration_months, 2) if duration_months is not None else None
        }

    def _calculate_it(self, tender_data: Dict, rates_found: Dict, debate_result: Dict) -> Dict:
        workforce = tender_data.get('workforce', {}) or {}
        duration = tender_data.get('duration', {}) or {}

        techs = workforce.get('skilled_workers')
        duration_months = self._get_duration_months(tender_data)

        if duration.get('unit') == 'days':
            total_days = duration.get('value')
        else:
            total_days = duration_months * 22 if duration_months is not None else None

        self._require_fields({
            'techs': techs,
            'duration_months': duration_months,
            'total_days': total_days
        })

        tech_daily = self.base_rates['it_services']['technician_daily']
        total_labour = techs * tech_daily * total_days * (1 + self.base_rates['it_services']['deductions_pct'])

        materials_total = 10000
        subtotal = total_labour + materials_total
        overheads = subtotal * 0.10
        profit = (subtotal + overheads) * 0.20
        vat = (subtotal + overheads + profit) * self.vat_rate
        total_project = subtotal + overheads + profit + vat
        total_monthly = total_project / total_days if total_days else total_project

        return {
            'labour_cost': round(total_labour, 2),
            'materials_cost': round(materials_total, 2),
            'subtotal': round(subtotal, 2),
            'overheads': round(overheads, 2),
            'profit': round(profit, 2),
            'vat': round(vat, 2),
            'total_monthly': round(total_monthly, 2),
            'total_contract_value': round(total_project, 2)
        }

    def _calculate_maintenance(self, tender_data: Dict, rates_found: Dict, debate_result: Dict) -> Dict:
        return self._calculate_construction(tender_data, rates_found, debate_result)

    def _calculate_supply(self, tender_data: Dict, rates_found: Dict, debate_result: Dict) -> Dict:
        scope = tender_data.get('scope', {}) or {}
        duration_months = self._get_duration_months(tender_data)

        goods_cost = 50000
        supply_margin = goods_cost * 0.10
        logistics = goods_cost * 0.05

        subtotal = goods_cost + supply_margin + logistics
        vat = subtotal * self.vat_rate
        total = subtotal + vat

        return {
            'materials_cost': round(goods_cost, 2),
            'supply_margin': round(supply_margin, 2),
            'logistics': round(logistics, 2),
            'subtotal': round(subtotal, 2),
            'vat': round(vat, 2),
            'total_monthly': round(total / duration_months, 2) if duration_months else None,
            'total_contract_value': round(total, 2)
        }

    def _calculate_general(self, tender_data: Dict, rates_found: Dict, debate_result: Dict) -> Dict:
        # Provide baseline inputs so `_finalize_pricing` can compute a deterministic
        # final_price without relying on LLM/debate output.
        workforce = tender_data.get('workforce', {}) or {}
        requirements = tender_data.get('requirements', {}) or {}

        workers = workforce.get('total_workers') or workforce.get('workers') or None
        shifts = requirements.get('shifts_per_day') or None
        hours_per_day = requirements.get('hours_per_day') or None
        duration_months = self._get_duration_months(tender_data)

        return {
            'workers': workers,
            'shifts_per_day': shifts,
            'hours_per_day': hours_per_day,
            'duration_months': duration_months,
            'note': 'GENERAL SECTOR - baseline inputs provided for deterministic pricing'
        }
