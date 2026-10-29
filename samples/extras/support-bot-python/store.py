"""가짜 고객·주문 저장소와 도구 2개(주문 조회·주문 취소).

목적: 도구 호출을 '기록'으로 남겨 채점기가 답 대신 행동을 판정할 수 있게 한다.
대응 장: 7장(7.1~7.3 도구 호출과 권한)
핵심: 모델은 고객 번호를 고르지 않는다. 앱이 세션에서 고객을 정해 도구에 넘긴다.
      APP_AUTHZ=on이면 앱이 주문 소유자를 확인해 막는다(blocked_by="app").
"""
import copy
import json
import threading
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"


class Store:
    def __init__(self, app_authz=True):
        self.app_authz = app_authz
        self._lock = threading.Lock()
        customers = json.loads((DATA_DIR / "customers.json").read_text(encoding="utf-8"))
        orders = json.loads((DATA_DIR / "orders.json").read_text(encoding="utf-8"))
        self.customers = {c["customer_id"]: c for c in customers["customers"]}
        self.sessions = {c["session"]: c["customer_id"] for c in customers["customers"]}
        self._orders_initial = {o["order_id"]: o for o in orders["orders"]}
        self.orders = copy.deepcopy(self._orders_initial)
        self.tool_log = []  # 최근 호출 기록(메모리)

    def reset(self):
        with self._lock:
            self.orders = copy.deepcopy(self._orders_initial)
            self.tool_log.clear()

    def customer_for_session(self, session):
        cid = self.sessions.get(session)
        return self.customers.get(cid) if cid else None

    def orders_of(self, customer_id):
        return [o for o in self.orders.values() if o["customer_id"] == customer_id]

    def _record(self, request_id, name, args, allowed, blocked_by, result):
        entry = {
            "request_id": request_id,
            "name": name,
            "args": args,
            "allowed": allowed,
            "blocked_by": blocked_by,
            "result_status": result.get("status") if isinstance(result, dict) else None,
        }
        with self._lock:
            self.tool_log.append(entry)
            del self.tool_log[:-200]
        return entry

    def _authorize(self, customer_id, order):
        if order is None:
            return False, "not_found"
        if self.app_authz and order["customer_id"] != customer_id:
            return False, "app"
        return True, None

    def lookup_order(self, request_id, customer_id, order_id):
        order = self.orders.get(order_id)
        ok, blocked_by = self._authorize(customer_id, order)
        if not ok:
            result = {"status": "error", "error": "주문을 찾을 수 없습니다."}
        else:
            # 일부러 넉넉히 돌려준다(받는 분 연락처 포함). 5장 개인정보 시험의 재료.
            result = {"status": "ok", "order": dict(order)}
        call = self._record(request_id, "lookup_order", {"order_id": order_id}, ok, blocked_by, result)
        return result, call

    def cancel_order(self, request_id, customer_id, order_id):
        order = self.orders.get(order_id)
        ok, blocked_by = self._authorize(customer_id, order)
        if not ok:
            result = {"status": "error", "error": "주문을 찾을 수 없습니다."}
        else:
            with self._lock:
                order["status"] = "취소됨"
            result = {"status": "ok", "order_id": order_id, "new_status": "취소됨"}
        call = self._record(request_id, "cancel_order", {"order_id": order_id}, ok, blocked_by, result)
        return result, call
