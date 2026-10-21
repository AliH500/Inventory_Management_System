#!/usr/bin/env python3

import sys
from datetime import date, timedelta
from pathlib import Path

from PyQt6 import QtWidgets, uic
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import (QApplication, QCompleter, QFileDialog, QInputDialog, QListWidgetItem,
                             QMessageBox, QTableWidgetItem)

UI = Path(__file__).parent
POINT_VALUE = 1.0        # Rs value of one redeemed point
POINTS_PER_RS = 100.0    # Rs spent per point earned


# =====================================================================================================
#  Small helpers
# =====================================================================================================
def money(x):   return f"Rs {x:,.2f}"
def fdate(d):   return d.strftime("%d/%m/%Y") if d else "-"
def qdate(d):   return QDate(d.year, d.month, d.day)
def pydate(q):  return date(q.year(), q.month(), q.day())
def load(name): return uic.loadUi(UI / name)

# Message helpers are functions so they are easy to replace when testing.
def info(parent, text):   QMessageBox.information(parent, "Demo", text)
def warn(parent, text):   QMessageBox.warning(parent, "Check this", text)
def ask(parent, text):    return QMessageBox.question(parent, "Confirm", text) == QMessageBox.StandardButton.Yes
def prompt(parent, title, label):
    text, ok = QInputDialog.getText(parent, title, label)
    return text.strip() if ok else None


def fill(table, rows, keys=None, right=(), tints=None, edit_cols=None):
    """Put a list of row-lists into a QTableWidget. keys[i] is stored on row i (read with row_key)."""
    table.blockSignals(True)
    table.setRowCount(0)
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            it = QTableWidgetItem(str(v))
            if c in right:
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if c == 0 and keys is not None:
                it.setData(Qt.ItemDataRole.UserRole, keys[r])
            if edit_cols is not None and c not in edit_cols:
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if tints and tints[r]:
                it.setBackground(QColor(tints[r]))
            table.setItem(r, c, it)
    table.blockSignals(False)


def sel_row(table):
    rows = table.selectionModel().selectedRows()
    return rows[0].row() if rows else -1


def row_key(table):
    r = sel_row(table)
    it = table.item(r, 0) if r >= 0 else None
    return it.data(Qt.ItemDataRole.UserRole) if it else None


def select_key(table, key):
    for r in range(table.rowCount()):
        it = table.item(r, 0)
        if it and it.data(Qt.ItemDataRole.UserRole) == key:
            table.selectRow(r)
            return True
    return False


def stretch(widget):
    for t in widget.findChildren(QtWidgets.QTableWidget):
        t.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)


# =====================================================================================================
#  The "database": lists and dictionaries
# =====================================================================================================
class Store:
    def __init__(self):
        self.reset()

    # ---- seed data ---------------------------------------------------------------------------------
    def reset(self):
        t = date.today()
        self.counters = {"S": 1001, "R": 1, "PO": 1, "D": 1, "C": 1, "E": 1, "SUP": 1}

        # CATEGORY: name, return period (days), tax rate (%), buy limit (max qty of one product per sale)
        self.categories = [
            {"name": "Phones",      "return_days": 14, "tax": 17.0, "limit": 3},
            {"name": "Laptops",     "return_days": 14, "tax": 17.0, "limit": 2},
            {"name": "Audio",       "return_days": 7,  "tax": 17.0, "limit": 5},
            {"name": "Accessories", "return_days": 7,  "tax": 17.0, "limit": 10},
            {"name": "Wearables",   "return_days": 10, "tax": 17.0, "limit": 3},
        ]
        # PRODUCT (reorder = PreorderAmt: when stock falls to this level an order record is auto-created)
        P = lambda *a: dict(zip(("barcode", "name", "desc", "cost", "price", "stock", "reorder", "warranty", "category"), a)) | {"image": None}
        self.products = [
            P("8901001", "Nova X5 Smartphone", "6.5-inch display, 128GB storage, dual camera", 45000, 52999, 14, 5, 12, "Phones"),
            P("8901002", "Nova X5 Lite Smartphone", "6.1-inch display, 64GB storage", 30000, 36999, 8, 5, 12, "Phones"),
            P("8902001", "AeroBook 14 Laptop", "14-inch, 16GB RAM, 512GB SSD", 140000, 164999, 6, 3, 24, "Laptops"),
            P("8902002", "AeroBook Air 13 Laptop", "13-inch ultralight, 8GB RAM, 256GB SSD", 110000, 129999, 4, 3, 24, "Laptops"),
            P("8903001", "PulseBuds Wireless Earbuds", "Bluetooth 5.3, 24h battery with case", 5500, 7999, 12, 10, 6, "Audio"),
            P("8903002", "BassMax Headphones", "Over-ear, active noise cancelling", 9000, 12999, 9, 4, 12, "Audio"),
            P("8904001", "FastCharge 65W Charger", "USB-C GaN charger, folding plug", 1400, 2499, 40, 15, 6, "Accessories"),
            P("8904002", "Braided USB-C Cable 1m", "Durable braided cable, 100W", 250, 799, 120, 30, 3, "Accessories"),
            P("8904003", "Clear Phone Case", "Shockproof transparent case", 300, 999, 3, 10, 0, "Accessories"),
            P("8905001", "FitBand 7 Smartwatch", "AMOLED display, heart-rate monitor", 8500, 11999, 10, 4, 12, "Wearables"),
        ]
        # CUSTOMER (+ LOYALTYCARD nested as 'card'). email/password = online account; card = loyalty card.
        card = lambda code, issue, exp, pts: {"code": code, "issue": t - timedelta(days=issue), "expiry": t + timedelta(days=exp), "points": pts}
        self.customers = [
            {"id": 1, "first": "Ayesha", "last": "Khan",   "contact": "0300-1111111", "email": "ayesha@mail.com", "password": "pass1",
             "reg": t - timedelta(days=300), "card": card("CARD-1001", 290, 440, 450)},
            {"id": 2, "first": "Bilal",  "last": "Ahmed",  "contact": "0301-2222222", "email": "bilal@mail.com", "password": "pass2",
             "reg": t - timedelta(days=120), "card": None},
            {"id": 3, "first": "Sana",   "last": "Malik",  "contact": "0302-3333333", "email": None, "password": None,
             "reg": t - timedelta(days=200), "card": card("CARD-1002", 200, 530, 120)},
            {"id": 4, "first": "Usman",  "last": "Raza",   "contact": "0303-4444444", "email": None, "password": None,
             "reg": t - timedelta(days=800), "card": card("CARD-1003", 790, -60, 80)},      # expired card
            {"id": 5, "first": "Hira",   "last": "Tariq",  "contact": "0304-5555555", "email": "hira@mail.com", "password": "pass5",
             "reg": t - timedelta(days=40), "card": card("CARD-1004", 40, 690, 0)},
        ]
        self.counters["C"] = 6
        self.counters["CARD"] = 1005
        # EMPLOYEE (password is demo-only)
        E = lambda *a: dict(zip(("id", "name", "cnic", "email", "phone", "joined", "role", "salary", "password"), a)) | {"photo": None}
        self.employees = [
            E(1, "Zainab Siddiqui", "35202-1234567-1", "zainab@store.pk", "0311-1000001", t - timedelta(days=700), "Cashier", 55000, "cashier1"),
            E(2, "Hamza Iqbal",     "35202-2345678-3", "hamza@store.pk",  "0311-1000002", t - timedelta(days=400), "Cashier", 52000, "cashier2"),
            E(3, "Faisal Mehmood",  "35202-3456789-5", "faisal@store.pk", "0311-1000003", t - timedelta(days=900), "Stocker", 58000, "stocker1"),
            E(4, "Mariam Aslam",    "35202-4567890-7", "mariam@store.pk", "0311-1000004", t - timedelta(days=1500), "Manager", 120000, "manager1"),
        ]
        self.counters["E"] = 5
        # SUPPLIER
        self.suppliers = [
            {"id": 1, "name": "TechSource Distributors", "email": "sales@techsource.pk", "contact": "0321-5550001"},
            {"id": 2, "name": "Gadget Wholesale Co.",    "email": "orders@gadgetwh.pk",  "contact": "0321-5550002"},
            {"id": 3, "name": "Mobile Hub Traders",      "email": "info@mobilehub.pk",   "contact": "0321-5550003"},
        ]
        self.counters["SUP"] = 4
        # DISCOUNT (max 0 = no maximum order amount)
        all_cats = [c["name"] for c in self.categories]
        self.discounts = [
            {"id": "D-1", "name": "Welcome 10%", "voucher": "WELCOME10", "pct": 10.0, "start": t - timedelta(days=30),
             "end": t + timedelta(days=60), "min": 5000.0, "max": 0.0, "categories": all_cats},
            {"id": "D-2", "name": "Audio Week", "voucher": "AUDIO15", "pct": 15.0, "start": t - timedelta(days=5),
             "end": t + timedelta(days=10), "min": 2000.0, "max": 0.0, "categories": ["Audio"]},
            {"id": "D-3", "name": "Old promo", "voucher": "OLD5", "pct": 5.0, "start": t - timedelta(days=90),
             "end": t - timedelta(days=30), "min": 0.0, "max": 0.0, "categories": all_cats},
        ]
        self.counters["D"] = 4
        self.sales, self.refunds, self.orders = [], [], []
        # Past sales (stock and points are NOT touched for these seeds)
        c1, c2, c3, c5 = (self.customer(i) for i in (1, 2, 3, 5))
        e1, e2 = self.employee(1), self.employee(2)
        self.record_sale([{"barcode": "8903001", "qty": 2}], c1, e1, "In-store", None, "Card", "Paid", when=t - timedelta(days=6), live=False)
        self.record_sale([{"barcode": "8902002", "qty": 1}, {"barcode": "8904001", "qty": 1}], c2, None, "Online",
                         "House 12, Street 4, Gulberg, Lahore", "Bank transfer", "Paid", when=t - timedelta(days=6), live=False)
        self.record_sale([{"barcode": "8905001", "qty": 1}], c3, e2, "In-store", None, "Cash", "Paid", when=t - timedelta(days=12), live=False)
        self.record_sale([{"barcode": "8903002", "qty": 1}], c5, None, "Online", "Flat 5B, Model Town, Lahore",
                         "Cash on delivery", "Pending", when=t - timedelta(days=1), live=False)
        self.record_sale([{"barcode": "8901002", "qty": 1}], c1, None, "Online", "House 7, DHA Phase 5, Lahore",
                         "Card", "Paid", when=t - timedelta(days=2), live=False)
        # One refund: 1 earbud from the first sale
        self.refunds.append({"id": "R-1", "date": t - timedelta(days=4), "sale_id": "S-1001", "barcode": "8903001", "qty": 1, "amount": 7999.0})
        self.counters["R"] = 2
        # PRODUCT_ORDER: one finished order and one auto-generated order waiting for the stocker
        self.orders.append({"id": "PO-1", "barcode": "8904002", "supplier_id": 1, "qty": 100, "total": 55000.0,
                            "placed": t - timedelta(days=20), "employee_id": 3})
        self.orders.append({"id": "PO-2", "barcode": "8904003", "supplier_id": None, "qty": None, "total": None,
                            "placed": None, "employee_id": None})
        self.counters["PO"] = 3

    # ---- lookups -----------------------------------------------------------------------------------
    def product(self, barcode):  return next((p for p in self.products if p["barcode"] == barcode), None)
    def category(self, name):    return next((c for c in self.categories if c["name"] == name), None)
    def customer(self, cid):     return next((c for c in self.customers if c["id"] == cid), None)
    def employee(self, eid):     return next((e for e in self.employees if e["id"] == eid), None)
    def supplier(self, sid):     return next((s for s in self.suppliers if s["id"] == sid), None)
    def sale(self, sid):         return next((s for s in self.sales if s["id"] == sid), None)
    def order(self, oid):        return next((o for o in self.orders if o["id"] == oid), None)
    def discount(self, did):     return next((d for d in self.discounts if d["id"] == did), None)

    def next_id(self, prefix):
        n = self.counters[prefix]
        self.counters[prefix] += 1
        return f"{prefix}-{n}"

    def peek_id(self, prefix):
        return f"{prefix}-{self.counters[prefix]}"

    @staticmethod
    def full_name(c):    return f"{c['first']} {c['last']}" if c else "Walk-in (no record)"
    @staticmethod
    def card_status(card):
        return "-" if not card else ("Active" if card["expiry"] >= date.today() else "Expired")

    def find_customer(self, text):
        """Find by loyalty card code or contact number."""
        t = text.strip().upper()
        digits = "".join(ch for ch in t if ch.isdigit())
        for c in self.customers:
            if c["card"] and c["card"]["code"] == t:
                return c
            if digits and "".join(ch for ch in c["contact"] if ch.isdigit()) == digits:
                return c
        return None

    # ---- writes ------------------------------------------------------------------------------------
    def new_card(self):
        n = self.counters["CARD"]
        self.counters["CARD"] += 1
        return {"code": f"CARD-{n}", "issue": date.today(), "expiry": date.today() + timedelta(days=730), "points": 0}

    def add_customer(self, first, last, contact, email=None, password=None, with_card=False):
        c = {"id": self.counters["C"], "first": first, "last": last, "contact": contact, "email": email,
             "password": password, "reg": date.today(), "card": self.new_card() if with_card else None}
        self.counters["C"] += 1
        self.customers.append(c)
        return c

    def has_open_order(self, barcode):
        return any(o["barcode"] == barcode and o["placed"] is None for o in self.orders)

    def record_sale(self, lines, customer, employee, stype, address, pay_type, pay_status,
                    voucher=None, points=0, when=None, live=True):
        """Create a SALE with its SALE_INFO rows. When live: update stock, loyalty points, auto-create orders."""
        pr = price_lines(lines, voucher, points)
        sale = {"id": self.next_id("S"), "date": when or date.today(),
                "customer_id": customer["id"] if customer else None,
                "employee_id": employee["id"] if employee else None,
                "type": stype, "address": address, "pay_type": pay_type, "pay_status": pay_status,
                "points": points, "total": pr["total"],
                "items": [{"barcode": r["barcode"], "qty": r["qty"], "paid": r["paid"]} for r in pr["rows"]]}
        self.sales.append(sale)
        earned, triggered = 0, []
        if live:
            card = customer["card"] if customer else None
            if card and self.card_status(card) == "Active":
                earned = int(pr["total"] // POINTS_PER_RS)
                card["points"] += earned - points
            for r in pr["rows"]:
                p = self.product(r["barcode"])
                before = p["stock"]
                p["stock"] -= r["qty"]
                if before > p["reorder"] >= p["stock"] and not self.has_open_order(p["barcode"]):
                    self.orders.append({"id": self.next_id("PO"), "barcode": p["barcode"], "supplier_id": None, "qty": None,
                                        "total": None, "placed": None, "employee_id": None})
                    triggered.append(p["name"])
        return sale, earned, triggered


DB = Store.__new__(Store)      # filled by DB.reset() once the pricing functions below exist


# =====================================================================================================
#  PRICING  (shared by the cashier screen and the online checkout)
# =====================================================================================================
def check_qty(barcode, new_qty):
    """Return an error message if the cart quantity is not allowed, else None."""
    p = DB.product(barcode)
    limit = DB.category(p["category"])["limit"]
    if new_qty > p["stock"]:
        return f"Only {p['stock']} of '{p['name']}' in stock."
    if new_qty > limit:
        return f"Buy limit for {p['category']} is {limit} per sale."
    return None


def raw_subtotal(lines):
    return sum(DB.product(l["barcode"])["price"] * l["qty"] for l in lines)


def find_voucher(code, subtotal):
    """Return (discount, message). discount is None when the code can't be used."""
    code = code.strip().upper()
    if not code:
        return None, "Enter a voucher code."
    d = next((x for x in DB.discounts if x["voucher"].upper() == code), None)
    if not d:
        return None, "Unknown voucher code."
    if not d["start"] <= date.today() <= d["end"]:
        return None, f"Voucher is only valid {fdate(d['start'])} to {fdate(d['end'])}."
    if subtotal < d["min"]:
        return None, f"Minimum order for this voucher is {money(d['min'])}."
    if d["max"] and subtotal > d["max"]:
        return None, f"Maximum order for this voucher is {money(d['max'])}."
    return d, f"{d['name']}: {d['pct']:g}% off {', '.join(d['categories'])}"


def price_lines(lines, voucher=None, points=0):
    """Subtotal -> voucher (only on eligible categories) -> points -> tax (per category rate on the net)."""
    rows, sub = [], 0.0
    for l in lines:
        p = DB.product(l["barcode"])
        line = p["price"] * l["qty"]
        sub += line
        rows.append({"barcode": p["barcode"], "name": p["name"], "qty": l["qty"], "unit": p["price"],
                     "line": line, "cat": p["category"]})
    disc = 0.0
    if voucher:
        disc = round(sum(r["line"] for r in rows if r["cat"] in voucher["categories"]) * voucher["pct"] / 100, 2)
    pts_amt = min(points * POINT_VALUE, sub - disc)
    net = sub - disc - pts_amt
    ratio = net / sub if sub else 0
    tax = 0.0
    for r in rows:
        r["paid"] = round(r["line"] * ratio, 2)
        tax += r["paid"] * DB.category(r["cat"])["tax"] / 100
    tax = round(tax, 2)
    return {"sub": sub, "disc": disc, "pts_amt": pts_amt, "tax": tax, "total": round(net + tax, 2), "rows": rows}


def points_available(customer):
    card = customer["card"] if customer else None
    return card["points"] if card and DB.card_status(card) == "Active" else 0


def cart_view(u, cart, voucher, points, customer):
    """Shared by both carts: validate voucher/points, return (pricing, voucher, points, max_points, voucher_msg)."""
    sub = raw_subtotal(cart)
    msg = ""
    if voucher:
        v, msg = find_voucher(voucher["voucher"], sub)
        voucher = v
    pr = price_lines(cart, voucher, 0)
    max_pts = min(points_available(customer), int((pr["sub"] - pr["disc"]) // POINT_VALUE))
    points = min(points, max_pts)
    return price_lines(cart, voucher, points), voucher, points, max_pts, msg


DB.reset()


# =====================================================================================================
#  STAFF APPLICATION
# =====================================================================================================
class SalePage:
    """New in-store sale. Cashier only. Customer is optional; loyalty points and vouchers can be applied."""
    def __init__(self, ui, app):
        self.u, self.app = ui, app
        self.reset_state()
        u = ui
        u.edBarcode.returnPressed.connect(self.add_item)
        u.edBarcode.textChanged.connect(self.preview)
        u.btnAddItem.clicked.connect(self.add_item)
        u.btnRemoveItem.clicked.connect(self.remove_item)
        u.btnClearSale.clicked.connect(self.clear_cart)
        u.edCustomerSearch.returnPressed.connect(self.find_customer)
        u.btnFindCustomer.clicked.connect(self.find_customer)
        u.btnRegisterCustomer.clicked.connect(self.register_customer)
        u.btnApplyPoints.clicked.connect(self.apply_points)
        u.btnApplyVoucher.clicked.connect(self.apply_voucher)
        u.edVoucher.returnPressed.connect(self.apply_voucher)
        u.btnCompleteSale.clicked.connect(self.complete)
        u.btnCancelSale.clicked.connect(self.cancel)
        self.refresh()

    def reset_state(self):
        self.cart, self.customer, self.voucher, self.points = [], None, None, 0

    def refresh(self):
        u = self.u
        u.dteSaleDate.setDate(qdate(date.today()))
        u.lblEmployee.setText(self.app.employee["name"])
        u.lblSaleId.setText(f"(next: {DB.peek_id('S')})")
        comp = QCompleter([p["barcode"] for p in DB.products], u.edBarcode)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        u.edBarcode.setCompleter(comp)
        self.preview(u.edBarcode.text())
        self.recalc()

    def preview(self, text):
        p = DB.product(text.strip())
        if p:
            self.u.lblProductInfo.setText(f"{p['name']}  |  {money(p['price'])}  |  {p['stock']} in stock")
        else:
            self.u.lblProductInfo.setText("No product with that barcode." if text.strip() else "Type a barcode, e.g. 8903001, then press Enter.")

    # ---- cart ----
    def add_item(self):
        u = self.u
        bc = u.edBarcode.text().strip()
        if not DB.product(bc):
            return warn(u, "Unknown barcode. Try 8903001 (earbuds) or 8904001 (charger).")
        ex = next((l for l in self.cart if l["barcode"] == bc), None)
        new_qty = (ex["qty"] if ex else 0) + u.spnQty.value()
        err = check_qty(bc, new_qty)
        if err:
            return warn(u, err)
        if ex: ex["qty"] = new_qty
        else:  self.cart.append({"barcode": bc, "qty": new_qty})
        u.edBarcode.clear()
        u.spnQty.setValue(1)
        u.edBarcode.setFocus()
        self.recalc()

    def remove_item(self):
        r = sel_row(self.u.tblSaleItems)
        if r >= 0:
            del self.cart[r]
            self.recalc()

    def clear_cart(self):
        self.cart = []
        self.recalc()

    # ---- customer, voucher, points ----
    def find_customer(self):
        c = DB.find_customer(self.u.edCustomerSearch.text())
        if not c:
            return warn(self.u, "No customer found. Try card CARD-1001 or contact 0300-1111111, or register a new customer.")
        self.customer, self.points = c, 0
        self.recalc()

    def register_customer(self):
        name = prompt(self.u, "Register customer", "Full name:")
        contact = name and prompt(self.u, "Register customer", "Contact number:")
        if not name or not contact:
            return
        first, _, last = name.partition(" ")
        self.customer = DB.add_customer(first, last, contact, with_card=True)
        self.points = 0
        info(self.u, f"Registered {name} with loyalty card {self.customer['card']['code']}.")
        self.recalc()

    def apply_voucher(self):
        v, msg = find_voucher(self.u.edVoucher.text(), raw_subtotal(self.cart))
        if not v:
            self.voucher = None
            self.u.lblDiscountInfo.setStyleSheet("color: #c0392b;")
            self.u.lblDiscountInfo.setText(msg)
        else:
            self.voucher = v
        self.recalc()

    def apply_points(self):
        self.points = self.u.spnPointsToRedeem.value()
        self.recalc()

    # ---- totals ----
    def recalc(self):
        u = self.u
        pr, self.voucher, self.points, max_pts, vmsg = cart_view(u, self.cart, self.voucher, self.points, self.customer)
        fill(u.tblSaleItems, [[r["barcode"], r["name"], r["qty"], money(r["unit"]), money(r["paid"])] for r in pr["rows"]],
             right=(2, 3, 4))
        if self.voucher:
            u.lblDiscountInfo.setStyleSheet("color: #27ae60;")
            u.lblDiscountInfo.setText(f"{self.voucher['name']}: {self.voucher['pct']:g}% off {', '.join(self.voucher['categories'])}")
        elif vmsg:
            u.lblDiscountInfo.setStyleSheet("color: #c0392b;")
            u.lblDiscountInfo.setText("Voucher removed: " + vmsg)
        c = self.customer
        u.lblCustomerName.setText(DB.full_name(c) if c else "No customer selected")
        card = c["card"] if c else None
        u.lblLoyalty.setText(f"Card: {card['code']}    Status: {DB.card_status(card)}    Points: {card['points']}" if card
                             else ("Customer has no loyalty card" if c else "Card: -    Status: -    Points: -"))
        u.spnPointsToRedeem.setMaximum(max_pts)
        u.spnPointsToRedeem.setValue(self.points)
        u.spnPointsToRedeem.setEnabled(max_pts > 0)
        u.btnApplyPoints.setEnabled(max_pts > 0)
        u.lblPointsValue.setText(f"{self.points} pts = {money(pr['pts_amt'])} off" if self.points else
                                 (f"Up to {max_pts} pts can be redeemed on this sale" if max_pts else ""))
        u.lblSubtotal.setText(money(pr["sub"]))
        u.lblDiscountAmt.setText("- " + money(pr["disc"]))
        u.lblPointsAmt.setText("- " + money(pr["pts_amt"]))
        u.lblTax.setText(money(pr["tax"]))
        u.lblTotal.setText(money(pr["total"]))

    def complete(self):
        u = self.u
        if self.app.employee["role"] != "Cashier":
            return warn(u, "Only a Cashier can complete an in-store sale. Log in as Zainab or Hamza.")
        if not self.cart:
            return warn(u, "The sale has no items.")
        sale, earned, trig = DB.record_sale(self.cart, self.customer, self.app.employee, "In-store", None,
                                            u.cmbPaymentType.currentText(), "Paid", self.voucher, self.points)
        msg = f"Sale {sale['id']} completed.\nTotal: {money(sale['total'])}"
        if earned: msg += f"\nLoyalty points earned: {earned}"
        if trig:   msg += "\nReorder level reached - restock order auto-created for: " + ", ".join(trig)
        info(u, msg)
        self.reset_state()
        u.edCustomerSearch.clear(); u.edVoucher.clear(); u.lblDiscountInfo.clear()
        self.refresh()

    def cancel(self):
        if self.cart and not ask(self.u, "Discard this sale?"):
            return
        self.reset_state()
        self.u.edCustomerSearch.clear(); self.u.edVoucher.clear(); self.u.lblDiscountInfo.clear()
        self.recalc()


class HistoryPage:
    """Browse all sales (in-store and online). Select one to see items; start a refund; show a receipt."""
    def __init__(self, ui, app):
        self.u, self.app = ui, app
        u = ui
        u.dteFrom.setDate(qdate(date.today() - timedelta(days=90)))
        u.dteTo.setDate(qdate(date.today()))
        u.btnSearch.clicked.connect(self.refresh)
        u.edSearch.returnPressed.connect(self.refresh)
        u.tblSales.itemSelectionChanged.connect(self.show_detail)
        u.btnRefundSale.clicked.connect(self.refund)
        u.btnPrintReceipt.clicked.connect(self.receipt)
        self.refresh()

    def refresh(self):
        u = self.u
        key = row_key(u.tblSales)
        lo, hi = pydate(u.dteFrom.date()), pydate(u.dteTo.date())
        text, stype, pay = u.edSearch.text().strip().lower(), u.cmbSaleTypeFilter.currentIndex(), u.cmbPaymentFilter.currentIndex()
        rows = []
        for s in reversed(DB.sales):
            c = DB.customer(s["customer_id"])
            if not lo <= s["date"] <= hi: continue
            if stype and s["type"] != u.cmbSaleTypeFilter.currentText(): continue
            if pay and s["pay_status"] != u.cmbPaymentFilter.currentText(): continue
            hay = f"{s['id']} {DB.full_name(c)} {c['contact'] if c else ''}".lower()
            if text and text not in hay: continue
            e = DB.employee(s["employee_id"])
            rows.append((s["id"], [s["id"], fdate(s["date"]), DB.full_name(c), e["name"] if e else "-", s["type"],
                                   money(s["total"]), s["pay_status"]]))
        fill(u.tblSales, [r[1] for r in rows], keys=[r[0] for r in rows], right=(5,))
        if not (key and select_key(u.tblSales, key)):
            self.show_detail()

    def show_detail(self):
        u = self.u
        s = DB.sale(row_key(u.tblSales))
        for w in (u.lblDetCustomer, u.lblDetEmployee, u.lblDetPoints, u.lblDetAddress, u.lblDetPayment, u.lblDetTotal):
            w.setText("-")
        if not s:
            return fill(u.tblSaleInfoItems, [])
        e = DB.employee(s["employee_id"])
        u.lblDetCustomer.setText(DB.full_name(DB.customer(s["customer_id"])))
        u.lblDetEmployee.setText(e["name"] if e else "Online order (no cashier)")
        u.lblDetPoints.setText(f"{s['points']} pts" if s["points"] else "none")
        u.lblDetAddress.setText(s["address"] or "In-store (no delivery)")
        u.lblDetPayment.setText(f"{s['pay_type']} ({s['pay_status']})")
        u.lblDetTotal.setText(money(s["total"]))
        fill(u.tblSaleInfoItems, [[i["barcode"], DB.product(i["barcode"])["name"], i["qty"], money(i["paid"])] for i in s["items"]], right=(2, 3))

    def refund(self):
        sid = row_key(self.u.tblSales)
        if not sid:
            return warn(self.u, "Select a sale first.")
        self.app.goto(2)
        self.app.controllers[2].lookup_id(sid)

    def receipt(self):
        s = DB.sale(row_key(self.u.tblSales))
        if not s:
            return warn(self.u, "Select a sale first.")
        lines = [f"RECEIPT {s['id']}   {fdate(s['date'])}", "-" * 44]
        lines += [f"{DB.product(i['barcode'])['name'][:26]:<26} x{i['qty']:<3}{money(i['paid']):>12}" for i in s["items"]]
        lines += ["-" * 44, f"{'TOTAL (incl. tax)':<30}{money(s['total']):>14}", f"Paid by: {s['pay_type']}"]
        info(self.u, "\n".join(lines))


class RefundsPage:
    """Look up a sale, type a Return Qty per item, issue a refund. Items past the category return period are blocked."""
    def __init__(self, ui, app):
        self.u, self.app, self.sale = ui, app, None
        ui.btnLookupSale.clicked.connect(lambda: self.lookup_id(ui.edSaleId.text()))
        ui.edSaleId.returnPressed.connect(lambda: self.lookup_id(ui.edSaleId.text()))
        ui.tblReturnItems.itemChanged.connect(self.update_total)
        ui.btnIssueRefund.clicked.connect(self.issue)
        self.refresh()

    def refresh(self):
        self.u.dteRefundDate.setDate(qdate(date.today()))
        self.u.lblRefundId.setText(f"(next: {DB.peek_id('R')})")
        rows = [[r["id"], fdate(r["date"]), r["sale_id"], DB.product(r["barcode"])["name"], r["qty"], money(r["amount"])] for r in reversed(DB.refunds)]
        fill(self.u.tblRefunds, rows, right=(4, 5))
        if self.sale:
            self.lookup_id(self.sale["id"], quiet=True)

    def returned_so_far(self, sale_id, barcode):
        return sum(r["qty"] for r in DB.refunds if r["sale_id"] == sale_id and r["barcode"] == barcode)

    def lookup_id(self, text, quiet=False):
        u = self.u
        sid = text.strip().upper()
        sid = sid if sid.startswith("S-") else f"S-{sid}"
        s = DB.sale(sid)
        if not s:
            self.sale = None
            fill(u.tblReturnItems, [])
            u.lblSaleSummary.setText("")
            return None if quiet else warn(u, "Sale not found. Try S-1001.")
        self.sale = s
        u.edSaleId.setText(s["id"])
        u.lblSaleSummary.setText(f"{DB.full_name(DB.customer(s['customer_id']))}  |  {fdate(s['date'])}  |  {s['type']}  |  {money(s['total'])}")
        rows = []
        for i in s["items"]:
            p = DB.product(i["barcode"])
            ok = s["date"] + timedelta(days=DB.category(p["category"])["return_days"]) >= date.today()
            rows.append([i["barcode"], p["name"], i["qty"], self.returned_so_far(s["id"], i["barcode"]), 0, money(i["paid"]),
                         "Yes" if ok else "No - period over"])
        fill(u.tblReturnItems, rows, right=(2, 3, 4, 5), edit_cols=(4,))
        self.update_total()

    def lines(self):
        """Yield (sale item, product, return qty, within period) for each row, using the typed Return Qty."""
        out = []
        for r, i in enumerate(self.sale["items"]):
            try:
                q = int(self.u.tblReturnItems.item(r, 4).text())
            except (ValueError, AttributeError):
                q = -1
            ok = self.u.tblReturnItems.item(r, 6).text() == "Yes"
            out.append((i, DB.product(i["barcode"]), q, ok))
        return out

    def update_total(self, *_):
        total = 0.0
        if self.sale:
            for i, p, q, ok in self.lines():
                if q > 0:
                    total += i["paid"] * q / i["qty"]
        self.u.lblRefundTotal.setText(money(total))

    def issue(self):
        u = self.u
        if not self.sale:
            return warn(u, "Look up a sale first.")
        picked = []
        for i, p, q, ok in self.lines():
            if q < 0:
                return warn(u, "Return Qty must be a whole number.")
            if q == 0:
                continue
            left = i["qty"] - self.returned_so_far(self.sale["id"], i["barcode"])
            if q > left:
                return warn(u, f"Only {left} of '{p['name']}' can still be returned.")
            if not ok:
                return warn(u, f"'{p['name']}' is past its {p['category']} return period.")
            picked.append((i, p, q))
        if not picked:
            return warn(u, "Enter a Return Qty for at least one item.")
        rid, total = DB.next_id("R"), 0.0
        for i, p, q in picked:
            amt = round(i["paid"] * q / i["qty"], 2)
            total += amt
            DB.refunds.append({"id": rid, "date": date.today(), "sale_id": self.sale["id"], "barcode": p["barcode"], "qty": q, "amount": amt})
            p["stock"] += q
        info(u, f"Refund {rid} issued: {money(total)}. Returned items were added back to stock.")
        self.refresh()


class ProductsPage:
    """Product list with filters and an edit form. Rows at or below the reorder level are tinted red."""
    def __init__(self, ui, app):
        self.u, self.app, self.cur, self.image = ui, app, None, None
        u = ui
        u.edSearch.textChanged.connect(self.refresh)
        u.cmbCategoryFilter.currentIndexChanged.connect(self.refresh)
        u.chkLowStock.toggled.connect(self.refresh)
        u.tblProducts.itemSelectionChanged.connect(self.select)
        u.dspCostPrice.valueChanged.connect(self.margin)
        u.dspSalePrice.valueChanged.connect(self.margin)
        u.btnNew.clicked.connect(self.new)
        u.btnSave.clicked.connect(self.save)
        u.btnDelete.clicked.connect(self.delete)
        u.btnBrowseImage.clicked.connect(self.browse)
        self.refresh()

    def refresh(self):
        u = self.u
        key = row_key(u.tblProducts)
        names = [c["name"] for c in DB.categories]
        for combo, extra in ((u.cmbCategoryFilter, ["All categories"]), (u.cmbCategory, [])):
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear(); combo.addItems(extra + names)
            combo.setCurrentIndex(max(0, combo.findText(current)))
            combo.blockSignals(False)
        text, cat = u.edSearch.text().strip().lower(), u.cmbCategoryFilter.currentText()
        rows, keys, tints = [], [], []
        for p in DB.products:
            low = p["stock"] <= p["reorder"]
            if text and text not in (p["barcode"] + p["name"]).lower(): continue
            if u.cmbCategoryFilter.currentIndex() > 0 and p["category"] != cat: continue
            if u.chkLowStock.isChecked() and not low: continue
            rows.append([p["barcode"], p["name"], p["category"], money(p["cost"]), money(p["price"]), p["stock"], p["reorder"], f"{p['warranty']} mo"])
            keys.append(p["barcode"]); tints.append("#fde8e8" if low else None)
        fill(u.tblProducts, rows, keys=keys, right=(3, 4, 5, 6), tints=tints)
        if not (key and select_key(u.tblProducts, key)):
            self.select()

    def select(self):
        p = DB.product(row_key(self.u.tblProducts))
        if p:
            self.fill_form(p)

    def fill_form(self, p):
        u = self.u
        self.cur, self.image = p["barcode"], p["image"]
        u.edBarcode.setText(p["barcode"]); u.edBarcode.setReadOnly(True)
        u.edName.setText(p["name"]); u.cmbCategory.setCurrentText(p["category"])
        u.pteDescription.setPlainText(p["desc"])
        u.dspCostPrice.setValue(p["cost"]); u.dspSalePrice.setValue(p["price"])
        u.spnStockQty.setValue(p["stock"]); u.spnPreorderAmt.setValue(p["reorder"]); u.spnWarranty.setValue(p["warranty"])
        self.show_image()

    def show_image(self):
        lbl = self.u.lblImagePreview
        pm = QPixmap(self.image) if self.image else QPixmap()
        if pm.isNull():
            lbl.setPixmap(QPixmap()); lbl.setText("No image")
        else:
            lbl.setPixmap(pm.scaled(116, 116, Qt.AspectRatioMode.KeepAspectRatio))

    def margin(self):
        c, s = self.u.dspCostPrice.value(), self.u.dspSalePrice.value()
        self.u.lblMargin.setText(f"Margin: {money(s - c)} ({(s - c) / s * 100:.1f}%)" if s else "")

    def new(self):
        u = self.u
        self.cur, self.image = None, None
        u.tblProducts.clearSelection()
        u.edBarcode.setReadOnly(False)
        for w in (u.edBarcode, u.edName): w.clear()
        u.pteDescription.clear()
        for w in (u.dspCostPrice, u.dspSalePrice, u.spnStockQty, u.spnPreorderAmt, u.spnWarranty): w.setValue(0)
        self.show_image()
        u.edBarcode.setFocus()

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self.u, "Choose image", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self.image = path
            self.show_image()

    def save(self):
        u = self.u
        bc, name = u.edBarcode.text().strip(), u.edName.text().strip()
        if not bc or not name:
            return warn(u, "Barcode and name are required.")
        if not u.cmbCategory.currentText():
            return warn(u, "Create a category first (Categories & Discounts).")
        p = DB.product(self.cur) if self.cur else None
        if not p:
            if DB.product(bc):
                return warn(u, "A product with this barcode already exists.")
            p = {"barcode": bc}
            DB.products.append(p)
        p.update(name=name, category=u.cmbCategory.currentText(), desc=u.pteDescription.toPlainText(), image=self.image,
                 cost=u.dspCostPrice.value(), price=u.dspSalePrice.value(), stock=u.spnStockQty.value(),
                 reorder=u.spnPreorderAmt.value(), warranty=u.spnWarranty.value())
        self.cur = bc
        self.refresh(); select_key(u.tblProducts, bc)
        info(u, f"Saved '{name}'.")

    def delete(self):
        p = DB.product(self.cur)
        if not p:
            return warn(self.u, "Select a product to delete.")
        if any(i["barcode"] == p["barcode"] for s in DB.sales for i in s["items"]):
            return warn(self.u, "This product appears in past sales, so it can't be deleted.")
        if ask(self.u, f"Delete '{p['name']}'?"):
            DB.products.remove(p)
            self.new(); self.refresh()


class CatalogPage:
    """Two tabs: categories (return period, tax, buy limit) and discounts (voucher rules per category)."""
    def __init__(self, ui, app):
        self.u, self.app, self.cat, self.disc = ui, app, None, None
        u = ui
        u.tblCategories.itemSelectionChanged.connect(self.cat_select)
        u.btnCatNew.clicked.connect(self.cat_new)
        u.btnCatSave.clicked.connect(self.cat_save)
        u.btnCatDelete.clicked.connect(self.cat_delete)
        u.tblDiscounts.itemSelectionChanged.connect(self.disc_select)
        u.btnDiscNew.clicked.connect(self.disc_new)
        u.btnDiscSave.clicked.connect(self.disc_save)
        u.btnDiscDelete.clicked.connect(self.disc_delete)
        self.refresh()

    def refresh(self):
        u = self.u
        ck, dk = row_key(u.tblCategories), row_key(u.tblDiscounts)
        fill(u.tblCategories, [[c["name"], f"{c['return_days']} days", f"{c['tax']:g} %", c["limit"]] for c in DB.categories],
             keys=[c["name"] for c in DB.categories], right=(1, 2, 3))
        fill(u.tblDiscounts, [[d["id"], d["name"], d["voucher"], f"{d['pct']:g} %", fdate(d["start"]), fdate(d["end"]),
                               money(d["min"]), money(d["max"]) if d["max"] else "none"] for d in DB.discounts],
             keys=[d["id"] for d in DB.discounts], right=(3, 6, 7))
        if ck: select_key(u.tblCategories, ck)
        if dk: select_key(u.tblDiscounts, dk)
        self.fill_category_list(DB.discount(self.disc)["categories"] if self.disc else [])

    # ---- categories ----
    def cat_select(self):
        c = DB.category(row_key(self.u.tblCategories))
        if c:
            self.cat = c["name"]
            self.u.edCategoryName.setText(c["name"]); self.u.spnReturnPeriod.setValue(c["return_days"])
            self.u.dspTaxRate.setValue(c["tax"]); self.u.spnBuyLimit.setValue(c["limit"])

    def cat_new(self):
        self.cat = None
        self.u.tblCategories.clearSelection(); self.u.edCategoryName.clear()
        for w in (self.u.spnReturnPeriod, self.u.dspTaxRate, self.u.spnBuyLimit): w.setValue(0)
        self.u.edCategoryName.setFocus()

    def cat_save(self):
        u = self.u
        name = u.edCategoryName.text().strip()
        if not name:
            return warn(u, "Category name is required.")
        c = DB.category(self.cat) if self.cat else None
        if (not c or c["name"] != name) and DB.category(name):
            return warn(u, "That category already exists.")
        if not c:
            c = {}
            DB.categories.append(c)
        else:   # rename ripples through products and discounts
            for p in DB.products:
                if p["category"] == c["name"]: p["category"] = name
            for d in DB.discounts:
                d["categories"] = [name if x == c["name"] else x for x in d["categories"]]
        c.update(name=name, return_days=u.spnReturnPeriod.value(), tax=u.dspTaxRate.value(), limit=u.spnBuyLimit.value())
        self.cat = name
        self.refresh(); select_key(u.tblCategories, name)

    def cat_delete(self):
        c = DB.category(self.cat)
        if not c:
            return warn(self.u, "Select a category first.")
        if any(p["category"] == c["name"] for p in DB.products):
            return warn(self.u, "Products still use this category.")
        if ask(self.u, f"Delete category '{c['name']}'?"):
            DB.categories.remove(c)
            self.cat_new(); self.refresh()

    # ---- discounts ----
    def fill_category_list(self, selected):
        lst = self.u.lstCategories
        lst.clear()
        for c in DB.categories:
            it = QListWidgetItem(c["name"])
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if c["name"] in selected else Qt.CheckState.Unchecked)
            lst.addItem(it)

    def disc_select(self):
        d = DB.discount(row_key(self.u.tblDiscounts))
        if d:
            u = self.u
            self.disc = d["id"]
            u.edDiscountName.setText(d["name"]); u.edVoucherCode.setText(d["voucher"])
            u.dteStart.setDate(qdate(d["start"])); u.dteEnd.setDate(qdate(d["end"]))
            u.dspDiscountPct.setValue(d["pct"]); u.dspMinOrder.setValue(d["min"]); u.dspMaxOrder.setValue(d["max"])
            self.fill_category_list(d["categories"])

    def disc_new(self):
        u = self.u
        self.disc = None
        u.tblDiscounts.clearSelection()
        u.edDiscountName.clear(); u.edVoucherCode.clear()
        u.dteStart.setDate(qdate(date.today())); u.dteEnd.setDate(qdate(date.today() + timedelta(days=30)))
        for w in (u.dspDiscountPct, u.dspMinOrder, u.dspMaxOrder): w.setValue(0)
        self.fill_category_list([])

    def disc_save(self):
        u = self.u
        name, code = u.edDiscountName.text().strip(), u.edVoucherCode.text().strip().upper()
        cats = [u.lstCategories.item(i).text() for i in range(u.lstCategories.count())
                if u.lstCategories.item(i).checkState() == Qt.CheckState.Checked]
        if not name or not code or not cats:
            return warn(u, "Name, voucher code and at least one category are required.")
        if pydate(u.dteEnd.date()) < pydate(u.dteStart.date()):
            return warn(u, "End date is before start date.")
        if any(d["voucher"] == code and d["id"] != self.disc for d in DB.discounts):
            return warn(u, "That voucher code is already used.")
        d = DB.discount(self.disc) if self.disc else None
        if not d:
            d = {"id": DB.next_id("D")}
            DB.discounts.append(d)
        d.update(name=name, voucher=code, start=pydate(u.dteStart.date()), end=pydate(u.dteEnd.date()),
                 pct=u.dspDiscountPct.value(), min=u.dspMinOrder.value(), max=u.dspMaxOrder.value(), categories=cats)
        self.disc = d["id"]
        self.refresh(); select_key(u.tblDiscounts, d["id"])

    def disc_delete(self):
        d = DB.discount(self.disc)
        if d and ask(self.u, f"Delete discount '{d['name']}'?"):
            DB.discounts.remove(d)
            self.disc_new(); self.refresh()


class CustomersPage:
    """One customer record can be an online account, a loyalty-card holder, or both."""
    def __init__(self, ui, app):
        self.u, self.app, self.cur = ui, app, None
        u = ui
        u.edSearch.returnPressed.connect(self.refresh)
        u.btnSearch.clicked.connect(self.refresh)
        u.cmbCustomerFilter.currentIndexChanged.connect(self.refresh)
        u.tblCustomers.itemSelectionChanged.connect(self.select)
        u.btnNew.clicked.connect(self.new)
        u.btnSave.clicked.connect(self.save)
        u.btnDelete.clicked.connect(self.delete)
        self.refresh()

    def refresh(self):
        u = self.u
        key = row_key(u.tblCustomers)
        text, mode = u.edSearch.text().strip().lower(), u.cmbCustomerFilter.currentIndex()
        rows, keys = [], []
        for c in DB.customers:
            if mode == 1 and not c["email"]: continue
            if mode == 2 and not c["card"]: continue
            hay = f"{DB.full_name(c)} {c['contact']} {c['email'] or ''} {c['card']['code'] if c['card'] else ''}".lower()
            if text and text not in hay: continue
            rows.append([c["id"], DB.full_name(c), c["contact"], c["email"] or "-", fdate(c["reg"]),
                         c["card"]["code"] if c["card"] else "-", c["card"]["points"] if c["card"] else "-"])
            keys.append(c["id"])
        fill(u.tblCustomers, rows, keys=keys, right=(6,))
        if not (key and select_key(u.tblCustomers, key)):
            self.select()

    def show_card(self, card):
        u = self.u
        u.lblCardCode.setText(card["code"] if card else "(issued on save)")
        u.lblIssueDate.setText(fdate(card["issue"]) if card else "-")
        u.dteExpiry.setDate(qdate(card["expiry"] if card else date.today() + timedelta(days=730)))
        u.lblPoints.setText(str(card["points"]) if card else "0")
        u.lblCardStatus.setText(DB.card_status(card))

    def select(self):
        c = DB.customer(row_key(self.u.tblCustomers))
        if not c:
            return
        u = self.u
        self.cur = c["id"]
        u.lblCustomerId.setText(str(c["id"]))
        u.edFirstName.setText(c["first"]); u.edLastName.setText(c["last"]); u.edContact.setText(c["contact"])
        u.lblRegDate.setText(fdate(c["reg"]))
        u.grpOnline.setChecked(bool(c["email"]))
        u.edEmail.setText(c["email"] or ""); u.edPassword.clear()
        u.grpLoyalty.setChecked(bool(c["card"]))
        self.show_card(c["card"])

    def new(self):
        u = self.u
        self.cur = None
        u.tblCustomers.clearSelection()
        u.lblCustomerId.setText("(auto)"); u.lblRegDate.setText(fdate(date.today()))
        for w in (u.edFirstName, u.edLastName, u.edContact, u.edEmail, u.edPassword): w.clear()
        u.grpOnline.setChecked(False); u.grpLoyalty.setChecked(False)
        self.show_card(None)
        u.edFirstName.setFocus()

    def save(self):
        u = self.u
        first, last, contact = u.edFirstName.text().strip(), u.edLastName.text().strip(), u.edContact.text().strip()
        online, card_on = u.grpOnline.isChecked(), u.grpLoyalty.isChecked()
        email, pw = u.edEmail.text().strip(), u.edPassword.text()
        c = DB.customer(self.cur) if self.cur else None
        if not first or not contact:
            return warn(u, "First name and contact are required.")
        if not online and not card_on:
            return warn(u, "A customer needs an online account, a loyalty card, or both.")
        if online:
            if "@" not in email:
                return warn(u, "Enter a valid email for the online account.")
            if any(x["email"] and x["email"].lower() == email.lower() and x is not c for x in DB.customers):
                return warn(u, "That email is already registered.")
            if not (c and c["password"]) and not pw:
                return warn(u, "Set a password for the new online account.")
        if c and c["card"] and not card_on and c["card"]["points"] and not ask(u, f"Remove the card? {c['card']['points']} points will be lost."):
            return
        if not c:
            c = DB.add_customer(first, last, contact)
        c.update(first=first, last=last, contact=contact)
        c["email"], c["password"] = (email, pw or c["password"]) if online else (None, None)
        if card_on:
            c["card"] = c["card"] or DB.new_card()
            c["card"]["expiry"] = pydate(u.dteExpiry.date())
        else:
            c["card"] = None
        self.cur = c["id"]
        self.refresh(); select_key(u.tblCustomers, c["id"])
        info(u, f"Saved {DB.full_name(c)}.")

    def delete(self):
        c = DB.customer(self.cur)
        if not c:
            return warn(self.u, "Select a customer first.")
        if any(s["customer_id"] == c["id"] for s in DB.sales):
            return warn(self.u, "This customer has sales on record, so they can't be deleted.")
        if ask(self.u, f"Delete {DB.full_name(c)}?"):
            DB.customers.remove(c)
            self.new(); self.refresh()


class SuppliersPage:
    """Restock orders are auto-created at the reorder level. The stocker picks a supplier and fills qty/total."""
    def __init__(self, ui, app):
        self.u, self.app, self.cur_order, self.cur_sup = ui, app, None, None
        u = ui
        u.chkNeedsDetails.toggled.connect(self.refresh)
        u.tblOrders.itemSelectionChanged.connect(self.order_select)
        u.btnConfirmOrder.clicked.connect(self.confirm)
        u.tblSuppliers.itemSelectionChanged.connect(self.sup_select)
        u.btnSupNew.clicked.connect(self.sup_new)
        u.btnSupSave.clicked.connect(self.sup_save)
        u.btnSupDelete.clicked.connect(self.sup_delete)
        self.refresh()

    def refresh(self):
        u = self.u
        ok, sk = row_key(u.tblOrders), row_key(u.tblSuppliers)
        u.cmbSupplier.blockSignals(True)
        u.cmbSupplier.clear(); u.cmbSupplier.addItem("Select supplier...")
        u.cmbSupplier.addItems([s["name"] for s in DB.suppliers])
        u.cmbSupplier.blockSignals(False)
        rows, keys, tints = [], [], []
        for o in reversed(DB.orders):
            if u.chkNeedsDetails.isChecked() and o["placed"]: continue
            p, s = DB.product(o["barcode"]), DB.supplier(o["supplier_id"])
            rows.append([o["id"], p["name"], p["stock"], p["reorder"], s["name"] if s else "-", o["qty"] or "-",
                         money(o["total"]) if o["total"] else "-", fdate(o["placed"]),
                         "Placed" if o["placed"] else "Needs details"])
            keys.append(o["id"]); tints.append(None if o["placed"] else "#fff4d6")
        fill(u.tblOrders, rows, keys=keys, right=(2, 3, 5, 6), tints=tints)
        fill(u.tblSuppliers, [[s["id"], s["name"], s["email"], s["contact"]] for s in DB.suppliers], keys=[s["id"] for s in DB.suppliers])
        if not (ok and select_key(u.tblOrders, ok)): self.order_select()
        if sk: select_key(u.tblSuppliers, sk)

    def order_select(self):
        u = self.u
        o = DB.order(row_key(u.tblOrders))
        self.cur_order = o["id"] if o else None
        if not o:
            for w in (u.lblOrderId, u.lblOrderProduct, u.lblOrderStock, u.lblOrderReorder, u.lblPlacedBy): w.setText("-")
            u.btnConfirmOrder.setEnabled(False)
            return
        p, s, e = DB.product(o["barcode"]), DB.supplier(o["supplier_id"]), DB.employee(o["employee_id"])
        u.lblOrderId.setText(o["id"]); u.lblOrderProduct.setText(p["name"])
        u.lblOrderStock.setText(str(p["stock"])); u.lblOrderReorder.setText(str(p["reorder"]))
        u.cmbSupplier.setCurrentIndex(DB.suppliers.index(s) + 1 if s else 0)
        u.spnOrderQty.setValue(o["qty"] or 0); u.dspOrderTotal.setValue(o["total"] or 0)
        u.dtePlaceDate.setDate(qdate(o["placed"] or date.today()))
        u.lblPlacedBy.setText(e["name"] if e else self.app.employee["name"])
        u.btnConfirmOrder.setEnabled(o["placed"] is None)

    def confirm(self):
        u = self.u
        o = DB.order(self.cur_order)
        if not o or o["placed"]:
            return
        if self.app.employee["role"] != "Stocker":
            return warn(u, "Only a Stocker deals with suppliers. Log in as Faisal.")
        if u.cmbSupplier.currentIndex() == 0 or u.spnOrderQty.value() <= 0 or u.dspOrderTotal.value() <= 0:
            return warn(u, "Choose a supplier and enter the qty and total amount.")
        o.update(supplier_id=DB.suppliers[u.cmbSupplier.currentIndex() - 1]["id"], qty=u.spnOrderQty.value(),
                 total=u.dspOrderTotal.value(), placed=pydate(u.dtePlaceDate.date()), employee_id=self.app.employee["id"])
        info(u, f"Order {o['id']} confirmed with {DB.supplier(o['supplier_id'])['name']}.")
        self.refresh()

    def sup_select(self):
        s = DB.supplier(row_key(self.u.tblSuppliers))
        if s:
            self.cur_sup = s["id"]
            self.u.lblSupplierId.setText(str(s["id"])); self.u.edSupplierName.setText(s["name"])
            self.u.edSupplierEmail.setText(s["email"]); self.u.edSupplierContact.setText(s["contact"])

    def sup_new(self):
        self.cur_sup = None
        self.u.tblSuppliers.clearSelection(); self.u.lblSupplierId.setText("(auto)")
        for w in (self.u.edSupplierName, self.u.edSupplierEmail, self.u.edSupplierContact): w.clear()

    def sup_save(self):
        u = self.u
        name = u.edSupplierName.text().strip()
        if not name:
            return warn(u, "Supplier name is required.")
        s = DB.supplier(self.cur_sup) if self.cur_sup else None
        if not s:
            s = {"id": DB.counters["SUP"]}
            DB.counters["SUP"] += 1
            DB.suppliers.append(s)
        s.update(name=name, email=u.edSupplierEmail.text().strip(), contact=u.edSupplierContact.text().strip())
        self.cur_sup = s["id"]
        self.refresh(); select_key(u.tblSuppliers, s["id"])

    def sup_delete(self):
        s = DB.supplier(self.cur_sup)
        if not s:
            return warn(self.u, "Select a supplier first.")
        if any(o["supplier_id"] == s["id"] for o in DB.orders):
            return warn(self.u, "This supplier has orders on record.")
        if ask(self.u, f"Delete {s['name']}?"):
            DB.suppliers.remove(s)
            self.sup_new(); self.refresh()


class EmployeesPage:
    def __init__(self, ui, app):
        self.u, self.app, self.cur, self.photo = ui, app, None, None
        u = ui
        u.edSearch.textChanged.connect(self.refresh)
        u.cmbRoleFilter.currentIndexChanged.connect(self.refresh)
        u.tblEmployees.itemSelectionChanged.connect(self.select)
        u.btnNew.clicked.connect(self.new)
        u.btnSave.clicked.connect(self.save)
        u.btnDelete.clicked.connect(self.delete)
        u.btnBrowsePicture.clicked.connect(self.browse)
        u.cmbRoleFilter.addItems(["Cashier", "Stocker", "Manager"])
        self.refresh()

    def refresh(self):
        u = self.u
        key = row_key(u.tblEmployees)
        text = u.edSearch.text().strip().lower()
        rows = [[e["id"], e["name"], e["role"], e["email"], e["phone"], fdate(e["joined"])] for e in DB.employees
                if (not text or text in f"{e['name']} {e['cnic']} {e['role']}".lower())
                and (u.cmbRoleFilter.currentIndex() == 0 or e["role"] == u.cmbRoleFilter.currentText())]
        fill(u.tblEmployees, rows, keys=[r[0] for r in rows])
        if not (key and select_key(u.tblEmployees, key)):
            self.select()

    def show_photo(self):
        lbl = self.u.lblProfilePicture
        pm = QPixmap(self.photo) if self.photo else QPixmap()
        if pm.isNull():
            lbl.setPixmap(QPixmap()); lbl.setText("No image")
        else:
            lbl.setPixmap(pm.scaled(116, 116, Qt.AspectRatioMode.KeepAspectRatio))

    def select(self):
        e = DB.employee(row_key(self.u.tblEmployees))
        if not e:
            return
        u = self.u
        self.cur, self.photo = e["id"], e["photo"]
        u.lblEmployeeId.setText(str(e["id"])); u.edName.setText(e["name"]); u.edCnic.setText(e["cnic"])
        u.edEmail.setText(e["email"]); u.edPhone.setText(e["phone"]); u.dteJoinDate.setDate(qdate(e["joined"]))
        u.cmbRole.setCurrentText(e["role"]); u.dspSalary.setValue(e["salary"])
        self.show_photo()

    def new(self):
        u = self.u
        self.cur, self.photo = None, None
        u.tblEmployees.clearSelection(); u.lblEmployeeId.setText("(auto)")
        for w in (u.edName, u.edCnic, u.edEmail, u.edPhone): w.clear()
        u.dteJoinDate.setDate(qdate(date.today())); u.dspSalary.setValue(0)
        self.show_photo()

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self.u, "Choose picture", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self.photo = path
            self.show_photo()

    def save(self):
        u = self.u
        name, email = u.edName.text().strip(), u.edEmail.text().strip()
        if not name or "@" not in email:
            return warn(u, "Name and a valid email are required.")
        e = DB.employee(self.cur) if self.cur else None
        if not e:
            e = {"id": DB.counters["E"], "password": "changeme"}
            DB.counters["E"] += 1
            DB.employees.append(e)
        e.update(name=name, cnic=u.edCnic.text(), email=email, phone=u.edPhone.text().strip(), joined=pydate(u.dteJoinDate.date()),
                 role=u.cmbRole.currentText(), salary=u.dspSalary.value(), photo=self.photo)
        self.cur = e["id"]
        self.refresh(); select_key(u.tblEmployees, e["id"])
        info(u, f"Saved {name}.")

    def delete(self):
        e = DB.employee(self.cur)
        if not e:
            return warn(self.u, "Select an employee first.")
        if e is self.app.employee:
            return warn(self.u, "You can't delete the account you're signed in with.")
        if any(s["employee_id"] == e["id"] for s in DB.sales) or any(o["employee_id"] == e["id"] for o in DB.orders):
            return warn(self.u, "This employee appears in sales or orders, so they can't be deleted.")
        if ask(self.u, f"Delete {e['name']}?"):
            DB.employees.remove(e)
            self.new(); self.refresh()


STAFF_PAGES = [("sale_page.ui", SalePage), ("sales_history_page.ui", HistoryPage), ("refunds_page.ui", RefundsPage),
               ("products_page.ui", ProductsPage), ("categories_discounts_page.ui", CatalogPage),
               ("customers_page.ui", CustomersPage), ("suppliers_restock_page.ui", SuppliersPage),
               ("employees_page.ui", EmployeesPage)]
# Which nav rows (0 = New Sale ... 7 = Employees) each role can see. Adjust to your rules.
ROLE_ACCESS = {"Cashier": {0, 1, 2, 5}, "Stocker": {3, 6}, "Manager": set(range(8))}


def staff_login():
    """Show login.ui. Returns the signed-in employee dict, or None."""
    dlg = load("login.ui")
    dlg.employee = None
    dlg.chkShowPassword.toggled.connect(lambda on: dlg.edPassword.setEchoMode(
        QtWidgets.QLineEdit.EchoMode.Normal if on else QtWidgets.QLineEdit.EchoMode.Password))

    def attempt():
        e = next((x for x in DB.employees if x["email"].lower() == dlg.edEmail.text().strip().lower()), None)
        if not e or e["password"] != dlg.edPassword.text():
            dlg.lblError.setText("Wrong email or password.")
            dlg.lblError.setVisible(True)
            return
        dlg.employee = e
        dlg.accept()
    dlg.btnLogin.clicked.connect(attempt)
    dlg.exec()
    return dlg.employee


class StaffApp:
    def __init__(self, employee):
        self.employee = employee
        self.win = load("main_window.ui")
        self.win.setWindowTitle(f"Retail Manager - {employee['name']} ({employee['role']})")
        self.controllers = []
        for filename, cls in STAFF_PAGES:
            page = load(filename)
            stretch(page)
            self.controllers.append(cls(page, self))
            self.win.pageStack.addWidget(page)
        self.win.pageStack.currentChanged.connect(lambda i: self.controllers[i].refresh())
        allowed = ROLE_ACCESS[employee["role"]]
        for row in range(self.win.navList.count()):
            self.win.navList.item(row).setHidden(row not in allowed)
        self.win.lblCurrentUser.setText(f"Signed in as: {employee['name']} ({employee['role']})")
        self.win.btnLogout.clicked.connect(self.win.close)
        self.win.navList.setCurrentRow(min(allowed))
        self.controllers[min(allowed)].refresh()
        self.win.show()

    def goto(self, row):
        self.win.navList.setCurrentRow(row)


# =====================================================================================================
#  ONLINE STORE
# =====================================================================================================
def shop_login():
    """Show shop_login.ui (sign in / create account). Returns the customer dict or None."""
    dlg = load("shop_login.ui")
    dlg.customer = None

    def fail(msg):
        dlg.lblError.setText(msg)
        dlg.lblError.setVisible(True)

    def sign_in():
        c = next((x for x in DB.customers if x["email"] and x["email"].lower() == dlg.edEmail.text().strip().lower()), None)
        if not c or c["password"] != dlg.edPassword.text():
            return fail("Wrong email or password.")
        dlg.customer = c
        dlg.accept()

    def register():
        first, last = dlg.edRegFirstName.text().strip(), dlg.edRegLastName.text().strip()
        email, contact = dlg.edRegEmail.text().strip(), dlg.edRegContact.text().strip()
        pw = dlg.edRegPassword.text()
        if not first or not contact or "@" not in email:
            return fail("Name, a valid email and contact are required.")
        if len(pw) < 4 or pw != dlg.edRegConfirm.text():
            return fail("Passwords must match and be at least 4 characters.")
        if any(x["email"] and x["email"].lower() == email.lower() for x in DB.customers):
            return fail("That email is already registered.")
        dlg.customer = DB.add_customer(first, last, contact, email, pw)
        dlg.accept()
    dlg.btnSignIn.clicked.connect(sign_in)
    dlg.btnRegister.clicked.connect(register)
    dlg.exec()
    return dlg.customer


class StorefrontApp:
    def __init__(self, customer):
        self.me = customer
        self.cart, self.voucher, self.points = [], None, 0
        w = self.win = load("storefront.ui")
        stretch(w)
        w.setWindowTitle(f"Online Store - {customer['first']}")
        w.lblWelcome.setText(f"Welcome, {customer['first']}")
        w.cmbCategory.addItems([c["name"] for c in DB.categories])
        w.edSearch.textChanged.connect(self.refresh_products)
        w.cmbCategory.currentIndexChanged.connect(self.refresh_products)
        w.tblShopProducts.itemSelectionChanged.connect(self.show_product)
        w.btnAddToCart.clicked.connect(self.add_to_cart)
        w.btnRemoveFromCart.clicked.connect(self.remove_from_cart)
        w.btnApplyVoucher.clicked.connect(self.apply_voucher)
        w.edVoucher.returnPressed.connect(self.apply_voucher)
        w.btnApplyPoints.clicked.connect(self.apply_points)
        w.btnPlaceOrder.clicked.connect(self.place_order)
        w.tblMyOrders.itemSelectionChanged.connect(self.show_order)
        w.btnSaveAccount.clicked.connect(self.save_account)
        w.btnLogout.clicked.connect(w.close)
        w.tabs.currentChanged.connect(lambda _: self.refresh_all())
        self.refresh_all()
        w.show()

    def refresh_all(self):
        self.refresh_products(); self.recalc(); self.refresh_orders(); self.refresh_account()

    # ---- shop ----
    def refresh_products(self, *_):
        w = self.win
        key = row_key(w.tblShopProducts)
        text, idx, cat = w.edSearch.text().strip().lower(), w.cmbCategory.currentIndex(), w.cmbCategory.currentText()
        rows, keys = [], []
        for p in DB.products:
            if text and text not in p["name"].lower(): continue
            if idx > 0 and p["category"] != cat: continue
            avail = "Out of stock" if p["stock"] <= 0 else ("Low stock" if p["stock"] <= p["reorder"] else "In stock")
            rows.append([p["name"], p["category"], money(p["price"]), f"{p['warranty']} months" if p["warranty"] else "none", avail])
            keys.append(p["barcode"])
        fill(w.tblShopProducts, rows, keys=keys, right=(2,))
        if not (key and select_key(w.tblShopProducts, key)):
            self.show_product()

    def show_product(self):
        w = self.win
        p = DB.product(row_key(w.tblShopProducts))
        if not p:
            return
        w.lblProductName.setText(p["name"]); w.lblProductPrice.setText(money(p["price"]))
        w.lblProductWarranty.setText(f"Warranty: {p['warranty']} months" if p["warranty"] else "No warranty")
        w.lblProductDescription.setText(p["desc"])
        pm = QPixmap(p["image"]) if p["image"] else QPixmap()
        w.lblProductImage.setPixmap(pm.scaled(116, 116, Qt.AspectRatioMode.KeepAspectRatio) if not pm.isNull() else QPixmap())
        if pm.isNull(): w.lblProductImage.setText("No image")

    def add_to_cart(self):
        w = self.win
        bc = row_key(w.tblShopProducts)
        if not bc:
            return warn(w, "Select a product first.")
        ex = next((l for l in self.cart if l["barcode"] == bc), None)
        new_qty = (ex["qty"] if ex else 0) + w.spnShopQty.value()
        err = check_qty(bc, new_qty)
        if err:
            return warn(w, err)
        if ex: ex["qty"] = new_qty
        else:  self.cart.append({"barcode": bc, "qty": new_qty})
        w.statusbar.showMessage(f"Added to cart: {DB.product(bc)['name']}", 3000)
        w.spnShopQty.setValue(1)
        self.recalc()

    # ---- cart / checkout ----
    def remove_from_cart(self):
        r = sel_row(self.win.tblCart)
        if r >= 0:
            del self.cart[r]
            self.recalc()

    def apply_voucher(self):
        w = self.win
        v, msg = find_voucher(w.edVoucher.text(), raw_subtotal(self.cart))
        self.voucher = v
        w.lblVoucherInfo.setStyleSheet("color: #27ae60;" if v else "color: #c0392b;")
        w.lblVoucherInfo.setText(msg)
        self.recalc()

    def apply_points(self):
        self.points = self.win.spnPointsToRedeem.value()
        self.recalc()

    def recalc(self):
        w = self.win
        pr, self.voucher, self.points, max_pts, vmsg = cart_view(w, self.cart, self.voucher, self.points, self.me)
        fill(w.tblCart, [[r["name"], r["qty"], money(r["unit"]), money(r["line"])] for r in pr["rows"]], right=(1, 2, 3))
        w.tabs.setTabText(1, f"Cart && Checkout ({sum(l['qty'] for l in self.cart)})")
        card = self.me["card"]
        w.lblPointsAvailable.setText(
            "No loyalty card on this account" if not card else
            f"Card {card['code']} ({DB.card_status(card)}): {card['points']} points = {money(card['points'] * POINT_VALUE)}")
        w.spnPointsToRedeem.setMaximum(max_pts); w.spnPointsToRedeem.setValue(self.points)
        w.spnPointsToRedeem.setEnabled(max_pts > 0); w.btnApplyPoints.setEnabled(max_pts > 0)
        w.lblPointsValue.setText(f"{self.points} pts = {money(pr['pts_amt'])} off" if self.points else "")
        if vmsg and not self.voucher:
            w.lblVoucherInfo.setStyleSheet("color: #c0392b;")
            w.lblVoucherInfo.setText("Voucher removed: " + vmsg)
        w.lblSubtotal.setText(money(pr["sub"])); w.lblDiscountAmt.setText("- " + money(pr["disc"]))
        w.lblPointsAmt.setText("- " + money(pr["pts_amt"])); w.lblTax.setText(money(pr["tax"]))
        w.lblTotal.setText(money(pr["total"]))

    def place_order(self):
        w = self.win
        address = w.pteDeliveryAddress.toPlainText().strip()
        if not self.cart:
            return warn(w, "Your cart is empty.")
        if len(address) < 10:
            return warn(w, "Enter a delivery address.")
        pay = w.cmbPaymentType.currentText()
        sale, earned, trig = DB.record_sale(self.cart, self.me, None, "Online", address, pay,
                                            "Pending" if pay == "Cash on delivery" else "Paid", self.voucher, self.points)
        msg = f"Order {sale['id']} placed. Total: {money(sale['total'])}"
        if earned: msg += f"\nYou earned {earned} loyalty points."
        info(w, msg)
        self.cart, self.voucher, self.points = [], None, 0
        w.edVoucher.clear(); w.lblVoucherInfo.clear(); w.pteDeliveryAddress.clear()
        self.refresh_all()
        w.tabs.setCurrentIndex(2)

    # ---- orders / account ----
    def my_sales(self):
        return [s for s in reversed(DB.sales) if s["customer_id"] == self.me["id"] and s["type"] == "Online"]

    def refresh_orders(self):
        w = self.win
        key = row_key(w.tblMyOrders)
        sales = self.my_sales()
        fill(w.tblMyOrders, [[s["id"], fdate(s["date"]), money(s["total"]), s["pay_status"], s["address"]] for s in sales],
             keys=[s["id"] for s in sales], right=(2,))
        if not (key and select_key(w.tblMyOrders, key)):
            self.show_order()

    def show_order(self):
        w = self.win
        s = DB.sale(row_key(w.tblMyOrders))
        if not s:
            fill(w.tblMyOrderItems, [])
            for l in (w.lblOrdPayment, w.lblOrdPoints, w.lblOrdTotal): l.setText("-")
            return
        fill(w.tblMyOrderItems, [[DB.product(i["barcode"])["name"], i["qty"], money(i["paid"])] for i in s["items"]], right=(1, 2))
        w.lblOrdPayment.setText(f"{s['pay_type']} ({s['pay_status']})")
        w.lblOrdPoints.setText(f"{s['points']} pts" if s["points"] else "none")
        w.lblOrdTotal.setText(money(s["total"]))

    def refresh_account(self):
        w, c = self.win, self.me
        w.lblAccEmail.setText(c["email"])
        for edit, val in ((w.edAccFirstName, c["first"]), (w.edAccLastName, c["last"]), (w.edAccContact, c["contact"])):
            if not edit.hasFocus(): edit.setText(val)
        card = c["card"]
        w.lblAccCardCode.setText(card["code"] if card else "No card")
        w.lblAccExpiry.setText(fdate(card["expiry"]) if card else "-")
        w.lblAccPoints.setText(str(card["points"]) if card else "0")
        w.lblAccCardStatus.setText(DB.card_status(card))

    def save_account(self):
        w, c = self.win, self.me
        if not w.edAccFirstName.text().strip() or not w.edAccContact.text().strip():
            return warn(w, "First name and contact are required.")
        c.update(first=w.edAccFirstName.text().strip(), last=w.edAccLastName.text().strip(), contact=w.edAccContact.text().strip())
        if w.edAccNewPassword.text():
            c["password"] = w.edAccNewPassword.text()
            w.edAccNewPassword.clear()
        w.lblWelcome.setText(f"Welcome, {c['first']}")
        info(w, "Account updated.")


# =====================================================================================================
#  LAUNCHER
# =====================================================================================================
class Launcher(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Retail UI demo launcher")
        self.keep = []                       # keeps opened windows alive
        lay = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel("Retail UI demo")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        lay.addWidget(title)
        lay.addWidget(QtWidgets.QLabel("All data lives in memory and resets when you close the program."))

        staff = QtWidgets.QGroupBox("Staff application")
        sl = QtWidgets.QVBoxLayout(staff)
        b = QtWidgets.QPushButton("Open staff login screen"); b.clicked.connect(self.open_staff_login); sl.addWidget(b)
        row = QtWidgets.QHBoxLayout(); row.addWidget(QtWidgets.QLabel("Skip login as:"))
        for role, eid in (("Cashier", 1), ("Stocker", 3), ("Manager", 4)):
            btn = QtWidgets.QPushButton(role)
            btn.clicked.connect(lambda _=False, i=eid: self.open_staff(DB.employee(i)))
            row.addWidget(btn)
        sl.addLayout(row)
        lay.addWidget(staff)

        shop = QtWidgets.QGroupBox("Online store")
        hl = QtWidgets.QVBoxLayout(shop)
        b = QtWidgets.QPushButton("Open store login screen"); b.clicked.connect(self.open_shop_login); hl.addWidget(b)
        row = QtWidgets.QHBoxLayout(); row.addWidget(QtWidgets.QLabel("Skip login as:"))
        for label, cid in (("Ayesha (card, 450 pts)", 1), ("Bilal (no card)", 2)):
            btn = QtWidgets.QPushButton(label)
            btn.clicked.connect(lambda _=False, i=cid: self.open_shop(DB.customer(i)))
            row.addWidget(btn)
        hl.addLayout(row)
        lay.addWidget(shop)

        raw = QtWidgets.QGroupBox("Raw .ui preview (no logic, just the layout)")
        rl = QtWidgets.QHBoxLayout(raw)
        self.combo = QtWidgets.QComboBox()
        self.combo.addItems(sorted(p.name for p in UI.glob("*.ui")))
        rl.addWidget(self.combo, 1)
        b = QtWidgets.QPushButton("Preview"); b.clicked.connect(self.preview_raw); rl.addWidget(b)
        lay.addWidget(raw)

        self.cheat = QtWidgets.QPlainTextEdit()
        self.cheat.setReadOnly(True)
        self.cheat.setStyleSheet("font-family: monospace;")
        lay.addWidget(QtWidgets.QLabel("Demo logins and things to try:"))
        lay.addWidget(self.cheat, 1)
        b = QtWidgets.QPushButton("Reset demo data"); b.clicked.connect(self.reset); lay.addWidget(b)
        self.update_cheatsheet()
        self.resize(560, 760)

    def update_cheatsheet(self):
        t = ["STAFF (email / password)"]
        t += [f"  {e['role']:<8} {e['email']:<18} {e['password']}" for e in DB.employees]
        t += ["", "ONLINE CUSTOMERS (email / password)"]
        t += [f"  {c['email']:<18} {c['password']}   card: {c['card']['code'] if c['card'] else '-'}" for c in DB.customers if c["email"]]
        t += ["", "IN-STORE LOOKUP (cashier 'Customer' box): card code or contact"]
        t += [f"  {c['card']['code']}  {c['contact']}  {DB.full_name(c)}  {c['card']['points']} pts ({DB.card_status(c['card'])})" for c in DB.customers if c["card"]]
        t += ["", "VOUCHERS: WELCOME10 (min Rs 5,000)  AUDIO15 (audio only, min Rs 2,000)  OLD5 (expired)", "",
              "BARCODES"] + [f"  {p['barcode']}  {p['name']}  stock {p['stock']} (reorder {p['reorder']})" for p in DB.products]
        t += ["", "TRY THIS", "  Cashier: sell 3x 8903001 -> stock hits reorder level -> a restock order appears for the Stocker.",
              "  Stocker: open Suppliers & Restock, pick 'Needs details', choose a supplier, qty, total, Confirm.",
              "  Online store: Ayesha adds items, applies points + AUDIO15, places an order; the cashier sees it in Sales History.",
              "  Refunds: S-1001 (1 earbud already returned, 1 can still go back); S-1003 is past its return period."]
        self.cheat.setPlainText("\n".join(t))

    def open_staff_login(self):
        e = staff_login()
        if e: self.open_staff(e)

    def open_staff(self, e):
        self.keep.append(StaffApp(e))

    def open_shop_login(self):
        c = shop_login()
        if c: self.open_shop(c)

    def open_shop(self, c):
        self.keep.append(StorefrontApp(c))

    def preview_raw(self):
        w = load(self.combo.currentText())
        w.show()
        self.keep.append(w)

    def reset(self):
        for k in self.keep:
            (k.win if hasattr(k, "win") else k).close()
        self.keep.clear()
        DB.reset()
        self.update_cheatsheet()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet((UI / "style.qss").read_text())
    launcher = Launcher()
    launcher.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
