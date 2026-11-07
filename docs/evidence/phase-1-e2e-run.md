# Real Test Mode E2E Run Evidence

**Execution Timestamp**: 2026-09-04T10:34:10.872815Z  
**Status**: **ORDER CREATED ON RAZORPAY TEST SERVERS**  
**Razorpay Order ID**: `order_TXvcUFjfbnXKtc`  
**Internal Order ID**: `ord_cc2d1fac28134baf`  
**Amount (paise)**: `10000`  
**Receipt**: `dec_ef8d4c47fb1f46f1`  
**Checkout URL**: `file:///C:\Users\DHANUSH A G\Desktop\razopay_new\scripts\test_checkout.html?key_id=rzp_test_TXLFfNuyfKpBqM&order_id=order_TXvcUFjfbnXKtc&amount=10000`  

### Provider State Verification:
- Order successfully registered on `https://api.razorpay.com/v1/orders`.
- Correlated with internal `decision_id` via `receipt`.
- Waiting for test card payment completion and provider webhook delivery.
