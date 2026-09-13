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
            if r['rate_date'] == date_str and r['from_currency'] == currency and r['to_currency'] == self.profile.home_currency:
                return int(round(amount_cents * float(r['rate'])))
        return amount_cents # Fallback
        
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
            
            if e.status == 'settled':
                groups[e.description].append(e)
            elif e.status in ['scheduled', 'pending']:
                # Future confirmed
                amt = self._convert_to_home(e.amount_cents, e.currency, d_str)
                # Apply reductions if requested
                if e.event_id in stopped_events:
                    continue
                if e.event_id in reduced_events:
                    amt = reduced_events[e.event_id]
                fc.add_flow(d_str, amt, e.direction)
                
        # 2. Project recurring
        for desc, items in groups.items():
            if len(items) >= 2:
                # Need to check if there's a scheduled event that covers this already to avoid double counting
                # A robust check is if a scheduled event with same description exists in future
                has_scheduled_future = any(e.status in ['scheduled', 'pending'] and e.description == desc for e in self.events)
                if has_scheduled_future:
                    continue # handled above
                    
                items.sort(key=lambda x: datetime.strptime(x.settlement_date if x.settlement_date else x.event_date, '%Y-%m-%d'))
                last_item = items[-1]
                
                # Check if it's stoppable and currently stopped
                if last_item.event_id in stopped_events:
                    continue
                    
                amts = [self._convert_to_home(i.amount_cents, i.currency, i.settlement_date if i.settlement_date else i.event_date) for i in items]
                max_amt = max(amts)
                
                if last_item.event_id in reduced_events:
                    max_amt = reduced_events[last_item.event_id]
                
                dates = [datetime.strptime(i.settlement_date if i.settlement_date else i.event_date, '%Y-%m-%d') for i in items]
                diffs = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                avg_diff = statistics.mean(diffs) if diffs else 0
                import statistics
                avg_diff = sum(diffs)/len(diffs) if diffs else 0
                
                # Monthly
                if 25 <= avg_diff <= 35:
                    day = dates[-1].day
                    curr = fc.start_date
                    while curr <= fc.end_date:
                        if curr.day == day:
                            fc.add_flow(curr.strftime('%Y-%m-%d'), max_amt, last_item.direction)
                        curr += timedelta(days=1)
                # Weekly
                elif 6 <= avg_diff <= 8:
                    weekday = dates[-1].weekday()
                    curr = fc.start_date
                    while curr <= fc.end_date:
                        if curr.weekday() == weekday:
                            fc.add_flow(curr.strftime('%Y-%m-%d'), max_amt, last_item.direction)
                        curr += timedelta(days=1)
                        
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
