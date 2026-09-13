import csv
import os
from typing import Dict, List, Optional
from config import config
from models.schemas import (
    RequestRow, FinancialProfile, FinancialEvent, ExchangeRate,
    PaymentOption, Message, ImageRecord
)

class DataLoader:
    def __init__(self):
        self.dataset_dir = config.DATASET_DIR
        self.requests: Dict[str, RequestRow] = {}
        self.profiles: Dict[str, FinancialProfile] = {}
        self.events: Dict[str, List[FinancialEvent]] = {}
        self.exchange_rates: List[ExchangeRate] = []
        self.payment_options: Dict[str, List[PaymentOption]] = {}
        self.messages: Dict[str, List[Message]] = {}
        self.images: Dict[str, List[ImageRecord]] = {}

    def load_all(self):
        self._load_requests()
        self._load_profiles()
        self._load_events()
        self._load_exchange_rates()
        self._load_payment_options()
        self._load_messages()
        self._load_images()

    def _read_csv(self, filename: str) -> List[Dict]:
        filepath = os.path.join(self.dataset_dir, filename)
        if not os.path.exists(filepath):
            return []
        
        results = []
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                results.append(row)
        return results
        
    def _parse_float_opt(self, val: str) -> Optional[float]:
        return float(val) if val.strip() else None

    def _parse_int_opt(self, val: str) -> Optional[int]:
        return int(val) if val.strip() else None

    def _load_requests(self):
        for row in self._read_csv('requests.csv'):
            row['allows_partial_payment'] = row['allows_partial_payment'].lower() == 'true'
            row['requested_amount'] = float(row['requested_amount'])
            req = RequestRow(**row)
            self.requests[req.request_id] = req
            
    def _load_profiles(self):
        for row in self._read_csv('financial_profiles.csv'):
            row['current_available_balance'] = float(row['current_available_balance'])
            row['minimum_balance_to_keep'] = float(row['minimum_balance_to_keep'])
            row['max_installment_months'] = self._parse_int_opt(row['max_installment_months'])
            prof = FinancialProfile(**row)
            self.profiles[prof.user_id] = prof
            
    def _load_events(self):
        for row in self._read_csv('financial_events.csv'):
            row['amount'] = self._parse_float_opt(row['amount'])
            row['linked_event_id'] = row['linked_event_id'] if row['linked_event_id'].strip() else None
            row['minimum_allowed_amount'] = self._parse_float_opt(row['minimum_allowed_amount'])
            event = FinancialEvent(**row)
            if event.user_id not in self.events:
                self.events[event.user_id] = []
            self.events[event.user_id].append(event)
            
    def _load_exchange_rates(self):
        for row in self._read_csv('exchange_rates.csv'):
            row['rate'] = float(row['rate'])
            self.exchange_rates.append(ExchangeRate(**row))
            
    def _load_payment_options(self):
        for row in self._read_csv('request_payment_options.csv'):
            row['payment_amount'] = float(row['payment_amount'])
            row['number_of_payments'] = int(row['number_of_payments'])
            row['payment_frequency_days'] = self._parse_int_opt(row['payment_frequency_days'])
            row['financing_fee'] = float(row['financing_fee'])
            row['total_payable_amount'] = float(row['total_payable_amount'])
            opt = PaymentOption(**row)
            if opt.request_id not in self.payment_options:
                self.payment_options[opt.request_id] = []
            self.payment_options[opt.request_id].append(opt)
            
    def _load_messages(self):
        for row in self._read_csv('messages.csv'):
            row['request_id'] = row['request_id'] if row['request_id'].strip() else None
            row['related_event_id'] = row['related_event_id'] if row['related_event_id'].strip() else None
            msg = Message(**row)
            link_id = msg.related_event_id or msg.request_id or msg.user_id
            if link_id not in self.messages:
                self.messages[link_id] = []
            self.messages[link_id].append(msg)
            
    def _load_images(self):
        for row in self._read_csv('images.csv'):
            row['request_id'] = row['request_id'] if row['request_id'].strip() else None
            row['related_event_id'] = row['related_event_id'] if row['related_event_id'].strip() else None
            img = ImageRecord(**row)
            link_id = img.related_event_id or img.request_id or img.user_id
            if link_id not in self.images:
                self.images[link_id] = []
            self.images[link_id].append(img)
