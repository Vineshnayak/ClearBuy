from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

from models.schemas import RequestRow, FinancialProfile, FinancialEvent, PaymentOption

class CashFlowForecast:
    def __init__(self, start_date_str: str, initial_balance_cents: int, min_balance_cents: int):
        self.start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        self.end_date = self.start_date + timedelta(days=90)
        self.min_balance = min_balance_cents
        
        self.initial_balance = initial_balance_cents
        self.daily_net = defaultdict(int)
        
    def clone(self):
        c = CashFlowForecast(self.start_date.strftime('%Y-%m-%d'), self.initial_balance, self.min_balance)
        c.daily_net = self.daily_net.copy()
        return c
        
    def add_flow(self, date_str: str, amount_cents: int, direction: str):
        d = datetime.strptime(date_str, '%Y-%m-%d')
        if self.start_date <= d <= self.end_date:
            if direction == 'credit':
                self.daily_net[d] += amount_cents
            else:
                self.daily_net[d] -= amount_cents
                
    def get_lowest_balance(self, initial_deduction: int = 0) -> int:
        bal = self.initial_balance - initial_deduction
        lowest = bal
        curr = self.start_date
        while curr <= self.end_date:
            bal += self.daily_net.get(curr, 0)
            if bal < lowest:
                lowest = bal
            curr += timedelta(days=1)
        return lowest
        
    def is_safe(self, initial_deduction: int = 0) -> bool:
        return self.get_lowest_balance(initial_deduction) >= self.min_balance

class FinancialEngine:
    def __init__(self, request: RequestRow, profile: FinancialProfile, events: List[FinancialEvent], payment_options: List[PaymentOption], exchange_rates: List[dict]):
        self.request = request
        self.profile = profile
        self.events = events
        self.payment_options = payment_options
        self.rates = exchange_rates
        
    def _convert_to_home(self, amount_cents: int, currency: str, date_str: str) -> int:
        if currency == self.profile.home_currency:
            return amount_cents
        # Naive lookup for exchange rate if needed
        # Since hackathon says output is in home_currency, we apply rate here
        for r in self.rates:
            if r.rate_date == date_str and r.from_currency == currency and r.to_currency == self.profile.home_currency:
                return int(round(amount_cents * float(r.rate)))
        return amount_cents # Fallback
        
    def _project_recurring_events(self, fc: CashFlowForecast, groups: dict, stopped_events: set, reduced_events: dict):
        import statistics
        for (cat, direction), items in groups.items():
            if len(items) >= 2:
                items.sort(key=lambda x: datetime.strptime(x.settlement_date if x.settlement_date else x.event_date, '%Y-%m-%d'))
                last_item = items[-1]
                
                if last_item.event_id in stopped_events:
                    continue
                    
                dates = [datetime.strptime(i.settlement_date if i.settlement_date else i.event_date, '%Y-%m-%d') for i in items]
                diffs = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                med_diff = statistics.median(diffs) if diffs else 0
                
                # Determine safe amount
                amts = [self._convert_to_home(i.amount_cents, i.currency, i.settlement_date if i.settlement_date else i.event_date) for i in items]
                proj_amt = max(amts) if direction == 'debit' else min(amts)
                
                if last_item.event_id in reduced_events:
                    proj_amt = reduced_events[last_item.event_id]
                    
                if 25 <= med_diff <= 35:
                    days = [d.day for d in dates]
                    best_day = max(set(days), key=days.count)
                    curr = fc.start_date
                    while curr <= fc.end_date:
                        if curr.day == best_day:
                            fc.add_flow(curr.strftime('%Y-%m-%d'), proj_amt, direction)
                        curr += timedelta(days=1)
                elif 6 <= med_diff <= 8:
                    weekdays = [d.weekday() for d in dates]
                    best_weekday = max(set(weekdays), key=weekdays.count)
                    curr = fc.start_date
                    while curr <= fc.end_date:
                        if curr.weekday() == best_weekday:
                            fc.add_flow(curr.strftime('%Y-%m-%d'), proj_amt, direction)
                        curr += timedelta(days=1)

    def _project_variable_events(self, fc: CashFlowForecast, groups: dict):
        import statistics
        var_groups = []
        for (cat, direction), items in groups.items():
            if len(items) >= 2:
                dates = [datetime.strptime(i.settlement_date if i.settlement_date else i.event_date, '%Y-%m-%d') for i in items]
                diffs = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                med_diff = statistics.median(diffs) if diffs else 0
                if not (25 <= med_diff <= 35) and not (6 <= med_diff <= 8) and direction == 'debit':
                    var_groups.append((cat, items, dates))
                    
        # Sum all variable expenses within the last 90 days of events
        req_date = datetime.strptime(self.request.request_date, '%Y-%m-%d')
        cutoff = req_date - timedelta(days=90)
        
        daily_var_drain = 0
        for cat, items, dates in var_groups:
            recent_amts = []
            for i, d in zip(items, dates):
                if cutoff <= d <= req_date:
                    amt = self._convert_to_home(i.amount_cents, i.currency, i.settlement_date if i.settlement_date else i.event_date)
                    recent_amts.append(amt)
            if recent_amts:
                daily_var_drain += int(sum(recent_amts) / 90)
                
        curr = fc.start_date
        while curr <= fc.end_date:
            fc.add_flow(curr.strftime('%Y-%m-%d'), daily_var_drain, 'debit')
            curr += timedelta(days=1)

    def build_base_forecast(self, stopped_events=None, reduced_events=None) -> CashFlowForecast:
        """
        Builds the 90 day cash flow forecast.
        Applies recurring expenses and confirmed scheduled/pending events.
        """
        if stopped_events is None: stopped_events = set()
        if reduced_events is None: reduced_events = {}
        
        fc = CashFlowForecast(
            self.request.request_date, 
            self.profile.current_available_balance_cents, 
            self.profile.minimum_balance_to_keep_cents
        )
        
        # 1. Parse history for recurring events
        groups = defaultdict(list)
        for e in self.events:
            if e.status in ['cancelled', 'failed', 'estimate']: continue
            if e.amount_cents is None: continue
            
            # Use settlement date for history, or event_date if not set
            d_str = e.settlement_date if e.settlement_date else e.event_date
            if not d_str: continue
            
            if e.status in ['settled', 'scheduled', 'pending']:
                groups[(e.category, e.direction)].append(e)
                
            if e.status in ['scheduled', 'pending']:
                # Future confirmed
                amt = self._convert_to_home(e.amount_cents, e.currency, d_str)
                # Apply reductions if requested
                if e.event_id in stopped_events:
                    continue
                if e.event_id in reduced_events:
                    amt = reduced_events[e.event_id]
                fc.add_flow(d_str, amt, e.direction)
                
        self._project_recurring_events(fc, groups, stopped_events, reduced_events)
        self._project_variable_events(fc, groups)
                        
        return fc

    def calculate_amount_safe_to_pay(self) -> int:
        fc = self.build_base_forecast()
        # amount_safe_to_pay is the most user can pay on request_date without going below min_balance
        lowest = fc.get_lowest_balance()
        margin = lowest - self.profile.minimum_balance_to_keep_cents
        if margin <= 0:
            return 0
        req_cents = self.request.requested_amount_cents
        return min(margin, req_cents)
        
    def get_earliest_date_full_payment(self) -> Optional[str]:
        fc = self.build_base_forecast()
        req_cents = self.request.requested_amount_cents
        curr = fc.start_date
        while curr <= fc.end_date:
            # what if we pay on curr?
            # we need to check if the lowest balance from curr onwards is >= min_balance
            # so we clone and add deduction on curr
            test_fc = fc.clone()
            test_fc.add_flow(curr.strftime('%Y-%m-%d'), req_cents, 'debit')
            if test_fc.is_safe():
                return curr.strftime('%Y-%m-%d')
            curr += timedelta(days=1)
        return None
        
    def _format_amt(self, amt: float) -> str:
        return f"{amt:.2f}".rstrip('0').rstrip('.')
        
    def evaluate(self) -> dict:
        # Check amount_safe_to_pay and earliest_date_for_full_payment
        safe_to_pay = self.calculate_amount_safe_to_pay()
        earliest_full = self.get_earliest_date_full_payment()
        req_cents = self.request.requested_amount_cents
        
        # User accepted payment methods
        accepted_methods = [m.strip() for m in self.profile.payment_methods_user_will_consider.split(',')]
        
        plans = [] # List of tuples: (plan_dict, is_safe)
        
        # We need to test various payment methods
        # 1. Full Payment
        if "full_payment" in accepted_methods:
            fc = self.build_base_forecast()
            test_fc = fc.clone()
            test_fc.add_flow(self.request.request_date, req_cents, 'debit')
            safe = test_fc.is_safe()
            completion_date = self.request.request_date
            
            plans.append({
                "method": "full_payment",
                "plan_str": f"{self.request.request_date}:{self._format_amt(self.request.requested_amount)}",
                "completion_date": completion_date,
                "total_paid": req_cents,
                "num_payments": 1,
                "start_date": self.request.request_date,
                "is_safe": safe,
                "option_id": "",
                "requires_spending_changes": False
            })
            
        # 2. Wait
        if "full_payment" in accepted_methods and earliest_full: # if wait is basically full payment later
            plans.append({
                "method": "wait",
                "plan_str": f"{earliest_full}:{self._format_amt(self.request.requested_amount)}",
                "completion_date": earliest_full,
                "total_paid": req_cents,
                "num_payments": 1,
                "start_date": earliest_full,
                "is_safe": True,
                "option_id": "",
                "requires_spending_changes": False
            })
            
        # 3. Partial Payment
        if "partial_payment" in accepted_methods and self.request.allows_partial_payment:
            if 0 < safe_to_pay < req_cents and earliest_full and earliest_full <= self.request.desired_completion_date:
                amount_1 = safe_to_pay
                amount_2 = req_cents - safe_to_pay
                
                fc = self.build_base_forecast()
                test_fc = fc.clone()
                test_fc.add_flow(self.request.request_date, amount_1, 'debit')
                test_fc.add_flow(earliest_full, amount_2, 'debit')
                
                if test_fc.is_safe():
                    amt1_float = amount_1 / 100.0
                    amt2_float = amount_2 / 100.0
                    plans.append({
                        "method": "partial_payment",
                        "plan_str": f"{self.request.request_date}:{self._format_amt(amt1_float)}|{earliest_full}:{self._format_amt(amt2_float)}",
                        "completion_date": earliest_full,
                        "total_paid": req_cents,
                        "num_payments": 2,
                        "start_date": self.request.request_date,
                        "is_safe": True,
                        "option_id": "",
                        "requires_spending_changes": False
                    })
                    
        # 4. Installments
        if "installments" in accepted_methods:
            for opt in self.payment_options:
                fc = self.build_base_forecast()
                test_fc = fc.clone()
                
                curr = datetime.strptime(opt.first_payment_date, '%Y-%m-%d')
                days_gap = opt.payment_frequency_days or 30
                
                safe = True
                payment_strings = []
                for i in range(opt.number_of_payments):
                    d_str = curr.strftime('%Y-%m-%d')
                    test_fc.add_flow(d_str, opt.payment_amount_cents, 'debit')
                    payment_strings.append(f"{d_str}:{self._format_amt(opt.payment_amount)}")
                    curr += timedelta(days=days_gap)
                    
                safe = test_fc.is_safe()
                completion = (curr - timedelta(days=days_gap)).strftime('%Y-%m-%d')
                
                plans.append({
                    "method": "installments",
                    "plan_str": "|".join(payment_strings),
                    "completion_date": completion,
                    "total_paid": opt.total_payable_amount_cents,
                    "num_payments": opt.number_of_payments,
                    "start_date": opt.first_payment_date,
                    "is_safe": safe,
                    "option_id": opt.payment_option_id,
                    "requires_spending_changes": False
                })
                
        # Filter safe plans
        safe_plans = [p for p in plans if p["is_safe"]]
        
        # If no safe plans, attempt spending changes on stoppable/reducible recurring
        spending_changes_str = "none"
        if not safe_plans:
            # We must try reducing/stopping flexible expenses.
            # Not fully implemented in this minimal engine yet, but stubbed.
            pass
            
        if not safe_plans:
            return {
                "amount_safe_to_pay": safe_to_pay / 100.0,
                "affordability_status": "not_affordable",
                "recommended_payment_method": "not_recommended",
                "payment_plan": "none",
                "earliest_date_for_full_payment": earliest_full if earliest_full else "",
                "spending_changes_needed": "none",
                "decision_explanation": "Insufficient funds to maintain minimum balance safely."
            }
            
        # Rank safe plans
        def rank_key(p):
            # 1. Complete by desired_completion_date (bool, True is better -> use not complete as False/True)
            completes_in_time = p["completion_date"] <= self.request.desired_completion_date
            
            # 2. No spending changes (bool)
            no_changes = not p["requires_spending_changes"]
            
            # 3. Minimize total paid (int)
            total_paid = p["total_paid"]
            
            # 4. Start earlier
            start_dt = datetime.strptime(p["start_date"], '%Y-%m-%d')
            
            # 5. Fewer payments
            num_payments = p["num_payments"]
            
            # 6. Lowest option ID
            opt_id = p["option_id"] if p["option_id"] else ""
            
            return (not completes_in_time, not no_changes, total_paid, start_dt, num_payments, opt_id)
            
        safe_plans.sort(key=rank_key)
        best_plan = safe_plans[0]
        
        status = "affordable_now" if best_plan["method"] == "full_payment" else ("affordable_with_plan" if best_plan["method"] in ["installments", "partial_payment"] else "affordable_later")
        
        return {
            "amount_safe_to_pay": safe_to_pay / 100.0,
            "affordability_status": status,
            "recommended_payment_method": best_plan["method"],
            "payment_plan": best_plan["plan_str"],
            "earliest_date_for_full_payment": earliest_full if earliest_full else "",
            "spending_changes_needed": spending_changes_str,
            "decision_explanation": f"Recommended {best_plan['method']}."
        }
