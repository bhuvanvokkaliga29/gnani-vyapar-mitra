import sqlite3
import json
import uuid
from datetime import datetime, timedelta

def seed_orders():
    conn = sqlite3.connect('test.db')
    cur = conn.cursor()

    # Clear previous orders to have a clean, realistic Vastram history
    cur.execute("DELETE FROM payments")
    cur.execute("DELETE FROM orders")

    now = datetime(2026, 10, 17, 20, 30, 0)

    # Catalog of mock orders across dates
    mock_orders = [
        # =========================================================================
        # TODAY: 17 OCT 2026
        # =========================================================================
        {
            "id": "ord_vast_9841",
            "amount_paise": 189900,
            "status": "PAID",
            "payment_method": "UPI (PhonePe)",
            "channel": "WhatsApp Direct",
            "channel_code": "WHATSAPP",
            "customer_name": "Rahul Sharma",
            "customer_phone": "+91 98451 22891",
            "customer_city": "Indiranagar, Bengaluru",
            "product_name": "Vastram Classic White Oxford Cotton Shirt",
            "sku": "VAST-SH-01",
            "size": "40 (M)",
            "qty": 1,
            "cost_paise": 65000,
            "image": "/clothing/white_oxford.jpg",
            "delivery_status": "Out for Delivery",
            "created_at": "2026-10-17 19:42:15"
        },
        {
            "id": "ord_vast_9840",
            "amount_paise": 229900,
            "status": "COD",
            "payment_method": "Cash on Delivery (COD)",
            "channel": "Website Store",
            "channel_code": "DIRECT_WEB",
            "customer_name": "Priya Nair",
            "customer_phone": "+91 94480 33124",
            "customer_city": "Koramangala, Bengaluru",
            "product_name": "Vastram Tailored Khaki Chino Trousers",
            "sku": "VAST-TR-01",
            "size": "32",
            "qty": 1,
            "cost_paise": 85000,
            "image": "/clothing/khaki_chino.jpg",
            "delivery_status": "Packed & Dispatched",
            "created_at": "2026-10-17 18:15:30"
        },
        {
            "id": "ord_vast_9839",
            "amount_paise": 389900,
            "status": "PAID",
            "payment_method": "UPI (Google Pay)",
            "channel": "WhatsApp Direct",
            "channel_code": "WHATSAPP",
            "customer_name": "Vikramaditya Rao",
            "customer_phone": "+91 98201 44589",
            "customer_city": "Bandra West, Mumbai",
            "product_name": "Executive Bundle: Oxford Shirt + Khaki Chinos",
            "sku": "VAST-BNDL-01",
            "size": "42 (L) / 34",
            "qty": 2,
            "cost_paise": 150000,
            "image": "/clothing/white_oxford.jpg",
            "delivery_status": "Shipped (BlueDart)",
            "created_at": "2026-10-17 16:50:00"
        },
        {
            "id": "ord_vast_9838",
            "amount_paise": 249900,
            "status": "PAID",
            "payment_method": "UPI (Paytm)",
            "channel": "Myntra Store",
            "channel_code": "MYNTRA",
            "customer_name": "Amit Patel",
            "customer_phone": "+91 99099 88123",
            "customer_city": "Navrangpura, Ahmedabad",
            "product_name": "Vastram Pure Olive Linen Casual Shirt",
            "sku": "VAST-SH-03",
            "size": "40 (M)",
            "qty": 1,
            "cost_paise": 92000,
            "image": "/clothing/linen_shirt.jpg",
            "delivery_status": "In Transit",
            "created_at": "2026-10-17 15:10:45"
        },
        {
            "id": "ord_vast_9837",
            "amount_paise": 219900,
            "status": "CANCELLED",
            "payment_method": "Cash on Delivery (COD)",
            "channel": "Website Store",
            "channel_code": "DIRECT_WEB",
            "customer_name": "Sneha Kulkarni",
            "customer_phone": "+91 97654 11200",
            "customer_city": "Kothrud, Pune",
            "product_name": "Vastram Classic Jet Black Formal Trousers",
            "sku": "VAST-TR-03",
            "size": "30",
            "qty": 1,
            "cost_paise": 79000,
            "image": "/clothing/black_trouser.jpg",
            "delivery_status": "Cancelled by Buyer (Size Change)",
            "created_at": "2026-10-17 13:25:00"
        },
        {
            "id": "ord_vast_9836",
            "amount_paise": 279900,
            "status": "PAID",
            "payment_method": "Credit Card (HDFC Visa)",
            "channel": "Amazon India",
            "channel_code": "AMAZON",
            "customer_name": "Arjun Mehta",
            "customer_phone": "+91 98110 55432",
            "customer_city": "Vasant Vihar, New Delhi",
            "product_name": "Vastram Italian Wool Charcoal Grey Trousers",
            "sku": "VAST-TR-02",
            "size": "34",
            "qty": 1,
            "cost_paise": 110000,
            "image": "/clothing/grey_trouser.jpg",
            "delivery_status": "Delivered Today",
            "created_at": "2026-10-17 11:05:20"
        },
        {
            "id": "ord_vast_9835",
            "amount_paise": 199900,
            "status": "COD",
            "payment_method": "Cash on Delivery (COD)",
            "channel": "WhatsApp Direct",
            "channel_code": "WHATSAPP",
            "customer_name": "Karthik Subramanian",
            "customer_phone": "+91 98400 99881",
            "customer_city": "Adyar, Chennai",
            "product_name": "Vastram Signature Royal Navy Casual Shirt",
            "sku": "VAST-SH-02",
            "size": "42 (L)",
            "qty": 1,
            "cost_paise": 72000,
            "image": "/clothing/navy_shirt.jpg",
            "delivery_status": "Out for Delivery",
            "created_at": "2026-10-17 09:30:10"
        },

        # =========================================================================
        # YESTERDAY: 16 OCT 2026
        # =========================================================================
        {
            "id": "ord_vast_9830",
            "amount_paise": 429900,
            "status": "PAID",
            "payment_method": "UPI (PhonePe)",
            "channel": "WhatsApp Direct",
            "channel_code": "WHATSAPP",
            "customer_name": "Divya Iyer",
            "customer_phone": "+91 98211 77654",
            "customer_city": "Juhu, Mumbai",
            "product_name": "Resort Duo: Olive Linen Shirt + Khaki Chinos",
            "sku": "VAST-BNDL-02",
            "size": "38 (S) / 32",
            "qty": 2,
            "cost_paise": 177000,
            "image": "/clothing/linen_shirt.jpg",
            "delivery_status": "Delivered",
            "created_at": "2026-10-16 19:15:00"
        },
        {
            "id": "ord_vast_9829",
            "amount_paise": 189900,
            "status": "PAID",
            "payment_method": "UPI (Google Pay)",
            "channel": "Website Store",
            "channel_code": "DIRECT_WEB",
            "customer_name": "Siddharth Jain",
            "customer_phone": "+91 98450 12399",
            "customer_city": "HSR Layout, Bengaluru",
            "product_name": "Vastram Classic White Oxford Cotton Shirt",
            "sku": "VAST-SH-01",
            "size": "40 (M)",
            "qty": 1,
            "cost_paise": 65000,
            "image": "/clothing/white_oxford.jpg",
            "delivery_status": "Delivered",
            "created_at": "2026-10-16 17:40:22"
        },
        {
            "id": "ord_vast_9828",
            "amount_paise": 229900,
            "status": "COD",
            "payment_method": "Cash on Delivery (COD)",
            "channel": "Amazon India",
            "channel_code": "AMAZON",
            "customer_name": "Pooja Verma",
            "customer_phone": "+91 99100 44332",
            "customer_city": "Noida, Uttar Pradesh",
            "product_name": "Vastram Tailored Khaki Chino Trousers",
            "sku": "VAST-TR-01",
            "size": "34",
            "qty": 1,
            "cost_paise": 85000,
            "image": "/clothing/khaki_chino.jpg",
            "delivery_status": "Delivered & Cash Collected",
            "created_at": "2026-10-16 14:20:00"
        },
        {
            "id": "ord_vast_9827",
            "amount_paise": 199900,
            "status": "CANCELLED",
            "payment_method": "UPI (PhonePe)",
            "channel": "Website Store",
            "channel_code": "DIRECT_WEB",
            "customer_name": "Manish Agarwal",
            "customer_phone": "+91 98300 66778",
            "customer_city": "Alipore, Kolkata",
            "product_name": "Vastram Signature Royal Navy Casual Shirt",
            "sku": "VAST-SH-02",
            "size": "44 (XL)",
            "qty": 1,
            "cost_paise": 72000,
            "image": "/clothing/navy_shirt.jpg",
            "delivery_status": "Refunded to Source UPI",
            "created_at": "2026-10-16 11:10:15"
        },
        {
            "id": "ord_vast_9826",
            "amount_paise": 219900,
            "status": "PAID",
            "payment_method": "NetBanking (ICICI)",
            "channel": "Myntra Store",
            "channel_code": "MYNTRA",
            "customer_name": "Rajesh Singhania",
            "customer_phone": "+91 94250 88990",
            "customer_city": "Arera Colony, Bhopal",
            "product_name": "Vastram Classic Jet Black Formal Trousers",
            "sku": "VAST-TR-03",
            "size": "36",
            "qty": 1,
            "cost_paise": 79000,
            "image": "/clothing/black_trouser.jpg",
            "delivery_status": "Delivered",
            "created_at": "2026-10-16 09:45:00"
        },

        # =========================================================================
        # 15 OCT 2026
        # =========================================================================
        {
            "id": "ord_vast_9820",
            "amount_paise": 189900,
            "status": "PAID",
            "payment_method": "UPI (PhonePe)",
            "channel": "WhatsApp Direct",
            "channel_code": "WHATSAPP",
            "customer_name": "Gaurav Sen",
            "customer_phone": "+91 98860 11456",
            "customer_city": "Whitefield, Bengaluru",
            "product_name": "Vastram Classic White Oxford Cotton Shirt",
            "sku": "VAST-SH-01",
            "size": "42 (L)",
            "qty": 1,
            "cost_paise": 65000,
            "image": "/clothing/white_oxford.jpg",
            "delivery_status": "Delivered",
            "created_at": "2026-10-15 18:30:00"
        },
        {
            "id": "ord_vast_9819",
            "amount_paise": 249900,
            "status": "COD",
            "payment_method": "Cash on Delivery (COD)",
            "channel": "Website Store",
            "channel_code": "DIRECT_WEB",
            "customer_name": "Naveen Reddy",
            "customer_phone": "+91 98490 22334",
            "customer_city": "Banjara Hills, Hyderabad",
            "product_name": "Vastram Pure Olive Linen Casual Shirt",
            "sku": "VAST-SH-03",
            "size": "40 (M)",
            "qty": 1,
            "cost_paise": 92000,
            "image": "/clothing/linen_shirt.jpg",
            "delivery_status": "Delivered & Cash Collected",
            "created_at": "2026-10-15 15:15:30"
        },
        {
            "id": "ord_vast_9818",
            "amount_paise": 279900,
            "status": "PAID",
            "payment_method": "Credit Card (Axis Bank)",
            "channel": "Amazon India",
            "channel_code": "AMAZON",
            "customer_name": "Sanjay Kapoor",
            "customer_phone": "+91 98101 99887",
            "customer_city": "DLF Phase 5, Gurugram",
            "product_name": "Vastram Italian Wool Charcoal Grey Trousers",
            "sku": "VAST-TR-02",
            "size": "34",
            "qty": 1,
            "cost_paise": 110000,
            "image": "/clothing/grey_trouser.jpg",
            "delivery_status": "Delivered",
            "created_at": "2026-10-15 12:45:10"
        },

        # =========================================================================
        # 14 OCT 2026
        # =========================================================================
        {
            "id": "ord_vast_9812",
            "amount_paise": 389900,
            "status": "PAID",
            "payment_method": "UPI (Google Pay)",
            "channel": "WhatsApp Direct",
            "channel_code": "WHATSAPP",
            "customer_name": "Abhishek Bose",
            "customer_phone": "+91 98310 55443",
            "customer_city": "Salt Lake, Kolkata",
            "product_name": "Executive Bundle: Oxford Shirt + Khaki Chinos",
            "sku": "VAST-BNDL-01",
            "size": "40 (M) / 32",
            "qty": 2,
            "cost_paise": 150000,
            "image": "/clothing/white_oxford.jpg",
            "delivery_status": "Delivered",
            "created_at": "2026-10-14 20:10:00"
        },
        {
            "id": "ord_vast_9811",
            "amount_paise": 199900,
            "status": "COD",
            "payment_method": "Cash on Delivery (COD)",
            "channel": "Flipkart Assured",
            "channel_code": "FLIPKART",
            "customer_name": "Tarun Saxena",
            "customer_phone": "+91 94150 77665",
            "customer_city": "Gomti Nagar, Lucknow",
            "product_name": "Vastram Signature Royal Navy Casual Shirt",
            "sku": "VAST-SH-02",
            "size": "38 (S)",
            "qty": 1,
            "cost_paise": 72000,
            "image": "/clothing/navy_shirt.jpg",
            "delivery_status": "Delivered & Cash Collected",
            "created_at": "2026-10-14 16:20:45"
        },
        {
            "id": "ord_vast_9810",
            "amount_paise": 229900,
            "status": "CANCELLED",
            "payment_method": "Cash on Delivery (COD)",
            "channel": "Website Store",
            "channel_code": "DIRECT_WEB",
            "customer_name": "Harish Menon",
            "customer_phone": "+91 98470 33221",
            "customer_city": "Panampilly Nagar, Kochi",
            "product_name": "Vastram Tailored Khaki Chino Trousers",
            "sku": "VAST-TR-01",
            "size": "36",
            "qty": 1,
            "cost_paise": 85000,
            "image": "/clothing/khaki_chino.jpg",
            "delivery_status": "Cancelled by Customer",
            "created_at": "2026-10-14 11:35:00"
        },

        # =========================================================================
        # 12 OCT 2026
        # =========================================================================
        {
            "id": "ord_vast_9805",
            "amount_paise": 189900,
            "status": "PAID",
            "payment_method": "UPI (PhonePe)",
            "channel": "WhatsApp Direct",
            "channel_code": "WHATSAPP",
            "customer_name": "Deepak Chawla",
            "customer_phone": "+91 98140 88776",
            "customer_city": "Sector 17, Chandigarh",
            "product_name": "Vastram Classic White Oxford Cotton Shirt",
            "sku": "VAST-SH-01",
            "size": "42 (L)",
            "qty": 1,
            "cost_paise": 65000,
            "image": "/clothing/white_oxford.jpg",
            "delivery_status": "Delivered",
            "created_at": "2026-10-12 17:50:00"
        },
        {
            "id": "ord_vast_9804",
            "amount_paise": 219900,
            "status": "PAID",
            "payment_method": "UPI (Google Pay)",
            "channel": "Myntra Store",
            "channel_code": "MYNTRA",
            "customer_name": "Rohit Deshmukh",
            "customer_phone": "+91 98220 44556",
            "customer_city": "Shivajinagar, Pune",
            "product_name": "Vastram Classic Jet Black Formal Trousers",
            "sku": "VAST-TR-03",
            "size": "32",
            "qty": 1,
            "cost_paise": 79000,
            "image": "/clothing/black_trouser.jpg",
            "delivery_status": "Delivered",
            "created_at": "2026-10-12 14:10:15"
        },

        # =========================================================================
        # 10 OCT 2026
        # =========================================================================
        {
            "id": "ord_vast_9798",
            "amount_paise": 249900,
            "status": "PAID",
            "payment_method": "Credit Card (SBI Card)",
            "channel": "Amazon India",
            "channel_code": "AMAZON",
            "customer_name": "Ananya Roy",
            "customer_phone": "+91 98301 22446",
            "customer_city": "Park Street, Kolkata",
            "product_name": "Vastram Pure Olive Linen Casual Shirt",
            "sku": "VAST-SH-03",
            "size": "38 (S)",
            "qty": 1,
            "cost_paise": 92000,
            "image": "/clothing/linen_shirt.jpg",
            "delivery_status": "Delivered",
            "created_at": "2026-10-10 19:25:00"
        },
        {
            "id": "ord_vast_9797",
            "amount_paise": 229900,
            "status": "COD",
            "payment_method": "Cash on Delivery (COD)",
            "channel": "Website Store",
            "channel_code": "DIRECT_WEB",
            "customer_name": "Mahesh Bhat",
            "customer_phone": "+91 94481 99001",
            "customer_city": "Mangalore, Karnataka",
            "product_name": "Vastram Tailored Khaki Chino Trousers",
            "sku": "VAST-TR-01",
            "size": "34",
            "qty": 1,
            "cost_paise": 85000,
            "image": "/clothing/khaki_chino.jpg",
            "delivery_status": "Delivered & Cash Collected",
            "created_at": "2026-10-10 13:40:00"
        }
    ]

    for o in mock_orders:
        dec_id = f"dec_{uuid.uuid4().hex[:12]}"
        receipt_id = f"rcpt_{o['id'].replace('ord_', '')}"
        
        notes = {
            "merchant_id": "merch_atlas_travel",
            "customer_name": o["customer_name"],
            "customer_phone": o["customer_phone"],
            "customer_city": o["customer_city"],
            "product_name": o["product_name"],
            "sku": o["sku"],
            "size": o["size"],
            "qty": o["qty"],
            "cost_paise": o["cost_paise"],
            "payment_method": o["payment_method"],
            "channel": o["channel"],
            "channel_code": o["channel_code"],
            "image": o["image"],
            "delivery_status": o["delivery_status"]
        }

        cur.execute("""
            INSERT INTO orders (
                id, decision_id, razorpay_order_id, amount_paise, currency, receipt,
                status, notes, is_simulated, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'INR', ?, ?, ?, 0, ?, ?)
        """, (
            o["id"],
            dec_id,
            None,
            o["amount_paise"],
            receipt_id,
            o["status"],
            json.dumps(notes),
            o["created_at"],
            o["created_at"]
        ))

        # Add payment record for paid orders
        if o["status"] == "PAID":
            pay_id = f"pay_{uuid.uuid4().hex[:14]}"
            cur.execute("""
                INSERT INTO payments (
                    id, order_id, amount_paise, currency, status, method,
                    error_code, error_description, captured_at, created_at
                ) VALUES (?, ?, ?, 'INR', 'captured', ?, NULL, NULL, ?, ?)
            """, (
                pay_id,
                o["id"],
                o["amount_paise"],
                "upi" if "UPI" in o["payment_method"] else "card",
                o["created_at"],
                o["created_at"]
            ))

    conn.commit()
    conn.close()
    print(f"Successfully seeded {len(mock_orders)} Vastram orders separated across dates with PAID, COD, and CANCELLED statuses!")

if __name__ == '__main__':
    seed_orders()
