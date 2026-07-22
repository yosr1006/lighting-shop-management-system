from datetime import date
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from db import get_db_connection

app = Flask(__name__)
app.secret_key = 'emara_shop_secret'

# DASHBOARD
@app.route('/')
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total FROM product")
    total_products = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) AS total FROM customer")
    total_customers = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) AS total FROM sales_invoice WHERE invoice_status = 'completed'")
    total_sales = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) AS total FROM purchase_invoice")
    total_purchases = cursor.fetchone()['total']

    cursor.close()
    conn.close()

    return render_template('dashboard.html',
        total_products=total_products,
        total_customers=total_customers,
        total_sales=total_sales,
        total_purchases=total_purchases
    )

# PRODUCTS
@app.route('/products')
def products():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    search_name = request.args.get('search_name', '')
    search_type = request.args.get('search_type', '')

    query = "SELECT * FROM product WHERE 1=1"
    params = []

    if search_name:
        query += " AND product_name LIKE %s"
        params.append(f'%{search_name}%')
    if search_type:
        query += " AND product_type = %s"
        params.append(search_type)

    query += " ORDER BY product_type, product_name"
    cursor.execute(query, params)
    all_products = cursor.fetchall()

    # Convert Decimal to float so Jinja templates work safely
    for p in all_products:
        p['purchase_price'] = float(p['purchase_price'])
        p['selling_price']  = float(p['selling_price'])

    cursor.close()
    conn.close()

    return render_template('products.html',
        products=all_products,
        search_name=search_name,
        search_type=search_type
    )


@app.route('/products/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        code     = request.form['product_code']
        name     = request.form['product_name']
        ptype    = request.form['product_type']
        price    = request.form['purchase_price']
        quantity = request.form['stock_quantity']

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO product (product_code, product_name, product_type, purchase_price, stock_quantity)
                VALUES (%s, %s, %s, %s, %s)
            """, (code, name, ptype, price, quantity))
            conn.commit()
            flash('Product added successfully!', 'success')
        except Exception as e:
            conn.rollback()
            if '1062' in str(e):
                flash('A product with this code already exists. Please use a different code.', 'danger')
            else:
                flash('Failed to add product. Please check your inputs and try again.', 'danger')
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('products'))

    return render_template('product_form.html', action='Add', product=None)


@app.route('/products/edit/<code>', methods=['GET', 'POST'])
def edit_product(code):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name     = request.form['product_name']
        ptype    = request.form['product_type']
        price    = request.form['purchase_price']
        quantity = request.form['stock_quantity']

        try:
            cursor.execute("""
                UPDATE product
                SET product_name=%s, product_type=%s, purchase_price=%s, stock_quantity=%s
                WHERE product_code=%s
            """, (name, ptype, price, quantity, code))
            conn.commit()
            flash('Product updated successfully!', 'success')
        except Exception as e:
            conn.rollback()
            flash('Failed to update product. Please check your inputs and try again.', 'danger')
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('products'))

    cursor.execute("SELECT * FROM product WHERE product_code = %s", (code,))
    product = cursor.fetchone()
    if product:
        product['purchase_price'] = float(product['purchase_price'])
        product['selling_price']  = float(product['selling_price'])
    cursor.close()
    conn.close()

    return render_template('product_form.html', action='Edit', product=product)


@app.route('/products/delete/<code>', methods=['POST'])
def delete_product(code):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM product WHERE product_code = %s", (code,))
        conn.commit()
        flash('Product deleted successfully.', 'info')
    except Exception as e:
        conn.rollback()
        if '1451' in str(e):
            flash('Cannot delete this product because it is linked to existing invoices.', 'danger')
        else:
            flash('Failed to delete product. Please try again.', 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('products'))

# CUSTOMERS
@app.route('/customers')
def customers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    search = request.args.get('search', '')

    if search:
        cursor.execute("""
            SELECT * FROM customer
            WHERE customer_name LIKE %s OR customer_phone LIKE %s
            ORDER BY customer_name
        """, (f'%{search}%', f'%{search}%'))
    else:
        cursor.execute("SELECT * FROM customer ORDER BY customer_name")

    all_customers = cursor.fetchall()

    for c in all_customers:
        cursor.execute("""
            SELECT
                COUNT(*) AS total_invoices,
                COALESCE(SUM(total_after_discount), 0) AS total_spent,
                MIN(invoice_date) AS first_invoice
            FROM sales_invoice
            WHERE customer_phone = %s AND invoice_status = 'completed'
        """, (c['customer_phone'],))
        stats = cursor.fetchone()
        c['total_invoices'] = stats['total_invoices']
        c['total_spent']    = float(stats['total_spent'])
        c['first_invoice']  = stats['first_invoice']

    cursor.close()
    conn.close()

    return render_template('customers.html', customers=all_customers, search=search, now=date.today())


@app.route('/customers/add', methods=['GET', 'POST'])
def add_customer():
    if request.method == 'POST':
        phone = request.form['customer_phone']
        name  = request.form['customer_name']

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO customer (customer_phone, customer_name) VALUES (%s, %s)", (phone, name))
            conn.commit()
            flash('Customer added successfully!', 'success')
        except Exception as e:
            conn.rollback()
            if '1062' in str(e):
                flash('A customer with this phone number already exists.', 'danger')
            else:
                flash('Failed to add customer. Please check your inputs and try again.', 'danger')
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('customers'))

    return render_template('customer_form.html', action='Add', customer=None)


@app.route('/customers/edit/<phone>', methods=['GET', 'POST'])
def edit_customer(phone):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form['customer_name'].strip()
        try:
            cursor.execute("UPDATE customer SET customer_name=%s WHERE customer_phone=%s", (name, phone))
            conn.commit()
            flash('Customer updated successfully!', 'success')
        except Exception as e:
            conn.rollback()
            flash('Failed to update customer. Please try again.', 'danger')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('customers'))

    cursor.execute("SELECT * FROM customer WHERE customer_phone = %s", (phone,))
    customer = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('customer_form.html', action='Edit', customer=customer)


@app.route('/customers/delete/<phone>')
def delete_customer(phone):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM customer WHERE customer_phone = %s", (phone,))
        conn.commit()
        flash('Customer deleted successfully.', 'info')
    except Exception as e:
        conn.rollback()
        if '1451' in str(e):
            flash('Cannot delete this customer because they have existing invoices.', 'danger')
        else:
            flash('Failed to delete customer. Please try again.', 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('customers'))

# API ENDPOINTS
# Look up customer by phone (for sale form live search)
@app.route('/api/customer/<phone>')
def api_customer(phone):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM customer WHERE customer_phone = %s", (phone,))
    customer = cursor.fetchone()
    cursor.close()
    conn.close()
    if customer:
        return jsonify({'found': True, 'name': customer['customer_name']})
    return jsonify({'found': False})


# Look up a completed, non-returned sales invoice (for return form)
@app.route('/api/invoice/<int:invoice_id>')
def api_invoice(invoice_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT si.*, c.customer_name
        FROM sales_invoice si
        JOIN customer c ON si.customer_phone = c.customer_phone
        WHERE si.s_invoice_id = %s
          AND si.invoice_status = 'completed'
          AND si.s_invoice_id NOT IN (SELECT s_invoice_id FROM product_returns)
    """, (invoice_id,))
    invoice = cursor.fetchone()
    cursor.close()
    conn.close()
    if invoice:
        return jsonify({
            'found': True,
            'customer_name': invoice['customer_name'],
            'invoice_date': str(invoice['invoice_date'])
        })
    return jsonify({'found': False})


#Return the products that belong to a specific invoice 
@app.route('/api/invoice/<int:invoice_id>/products')
def api_invoice_products(invoice_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT sid.product_code,
               sid.quantity,
               sid.unit_price,
               p.product_name,
               p.product_type
        FROM sales_invoice_details sid
        JOIN product p ON sid.product_code = p.product_code
        WHERE sid.s_invoice_id = %s
    """, (invoice_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    for r in rows:
        r['unit_price'] = float(r['unit_price'])
    return jsonify(rows)

# Look up product by code
@app.route('/api/product/<code>')
def api_product(code):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT product_name FROM product WHERE product_code = %s", (code,))
    product = cursor.fetchone()
    cursor.close()
    conn.close()
    if product:
        return jsonify({'found': True, 'name': product['product_name']})
    return jsonify({'found': False})

# JSON search APIs for live in-place table filtering
@app.route('/api/search/products')
def api_search_products():
    search_name = request.args.get('search_name', '')
    search_type = request.args.get('search_type', '')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = "SELECT * FROM product WHERE 1=1"
    params = []
    if search_name:
        query += " AND product_name LIKE %s"
        params.append(f'%{search_name}%')
    if search_type:
        query += " AND product_type = %s"
        params.append(search_type)
    query += " ORDER BY product_type, product_name"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    for r in rows:
        r['purchase_price'] = float(r['purchase_price'])
        r['selling_price']  = float(r['selling_price'])
    return jsonify(rows)

@app.route('/api/search/customers')
def api_search_customers():
    search = request.args.get('search', '')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if search:
        cursor.execute("""
            SELECT * FROM customer
            WHERE customer_name LIKE %s OR customer_phone LIKE %s
            ORDER BY customer_name
        """, (f'%{search}%', f'%{search}%'))
    else:
        cursor.execute("SELECT * FROM customer ORDER BY customer_name")
    rows = cursor.fetchall()
    today = date.today()
    for c in rows:
        cursor.execute("""
            SELECT COUNT(*) AS total_invoices,
                   COALESCE(SUM(total_after_discount), 0) AS total_spent,
                   MIN(invoice_date) AS first_invoice
            FROM sales_invoice
            WHERE customer_phone = %s AND invoice_status = 'completed'
        """, (c['customer_phone'],))
        stats = cursor.fetchone()
        c['total_invoices'] = stats['total_invoices']
        c['total_spent']    = float(stats['total_spent'])
        fi = stats['first_invoice']
        c['first_invoice']  = str(fi) if fi else None
        if fi:
            days = (today - fi).days
            c['is_loyal'] = days >= 180
            c['loyalty_days'] = days
        else:
            c['is_loyal'] = False
            c['loyalty_days'] = 0
    cursor.close()
    conn.close()
    return jsonify(rows)


@app.route('/api/search/suppliers')
def api_search_suppliers():
    search = request.args.get('search', '')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if search:
        cursor.execute("""
            SELECT * FROM supplier
            WHERE supplier_name LIKE %s OR supplier_phone LIKE %s
            ORDER BY supplier_name
        """, (f'%{search}%', f'%{search}%'))
    else:
        cursor.execute("SELECT * FROM supplier ORDER BY supplier_name")
    rows = cursor.fetchall()
    for s in rows:
        cursor.execute("""
            SELECT COUNT(*) AS total_orders, COALESCE(SUM(total_price),0) AS total_paid
            FROM purchase_invoice WHERE supplier_phone = %s
        """, (s['supplier_phone'],))
        stats = cursor.fetchone()
        s['total_orders'] = stats['total_orders']
        s['total_paid']   = float(stats['total_paid'])
    cursor.close()
    conn.close()
    return jsonify(rows)


@app.route('/api/search/sales')
def api_search_sales():
    search_customer = request.args.get('search_customer', '')
    search_status   = request.args.get('search_status', '')
    search_date     = request.args.get('search_date', '')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT si.*, c.customer_name
        FROM sales_invoice si
        JOIN customer c ON si.customer_phone = c.customer_phone
        WHERE 1=1
    """
    params = []
    if search_customer:
        query += " AND (c.customer_name LIKE %s OR si.customer_phone LIKE %s)"
        params += [f'%{search_customer}%', f'%{search_customer}%']
    if search_status:
        query += " AND si.invoice_status = %s"
        params.append(search_status)
    if search_date:
        query += " AND si.invoice_date = %s"
        params.append(search_date)
    query += " ORDER BY si.invoice_date DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    for r in rows:
        r['invoice_date']         = str(r['invoice_date'])
        r['total_price']          = float(r['total_price'])
        r['total_after_discount'] = float(r['total_after_discount'])
        r['discount_percentage']  = float(r['discount_percentage'])
    return jsonify(rows)


@app.route('/api/search/purchases')
def api_search_purchases():
    search_supplier = request.args.get('search_supplier', '')
    search_date     = request.args.get('search_date', '')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT pi.*, s.supplier_name
        FROM purchase_invoice pi
        JOIN supplier s ON pi.supplier_phone = s.supplier_phone
        WHERE 1=1
    """
    params = []
    if search_supplier:
        query += " AND s.supplier_name LIKE %s"
        params.append(f'%{search_supplier}%')
    if search_date:
        query += " AND pi.delivery_date = %s"
        params.append(search_date)
    query += " ORDER BY pi.delivery_date DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    for r in rows:
        r['delivery_date'] = str(r['delivery_date'])
        r['total_price']   = float(r['total_price'])
    return jsonify(rows)


@app.route('/api/search/returns')
def api_search_returns():
    search = request.args.get('search', '')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT pr.*, c.customer_name, p.product_name, si.invoice_date
        FROM product_returns pr
        JOIN sales_invoice si ON pr.s_invoice_id = si.s_invoice_id
        JOIN customer c ON si.customer_phone = c.customer_phone
        JOIN product p ON pr.product_code = p.product_code
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (c.customer_name LIKE %s OR p.product_name LIKE %s)"
        params += [f'%{search}%', f'%{search}%']
    query += " ORDER BY pr.return_date DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    for r in rows:
        r['invoice_date'] = str(r['invoice_date'])
        r['return_date']  = str(r['return_date'])
    return jsonify(rows)


# ══════════════════════════════════════════
# SUPPLIERS
# ══════════════════════════════════════════
@app.route('/suppliers')
def suppliers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    search = request.args.get('search', '')

    if search:
        cursor.execute("""
            SELECT * FROM supplier
            WHERE supplier_name LIKE %s OR supplier_phone LIKE %s
            ORDER BY supplier_name
        """, (f'%{search}%', f'%{search}%'))
    else:
        cursor.execute("SELECT * FROM supplier ORDER BY supplier_name")

    all_suppliers = cursor.fetchall()

    for s in all_suppliers:
        cursor.execute("""
            SELECT COUNT(*) AS total_orders, COALESCE(SUM(total_price),0) AS total_paid
            FROM purchase_invoice WHERE supplier_phone = %s
        """, (s['supplier_phone'],))
        stats = cursor.fetchone()
        s['total_orders'] = stats['total_orders']
        s['total_paid']   = float(stats['total_paid'])

    cursor.close()
    conn.close()

    return render_template('suppliers.html', suppliers=all_suppliers, search=search)


@app.route('/suppliers/add', methods=['GET', 'POST'])
def add_supplier():
    if request.method == 'POST':
        phone   = request.form['supplier_phone']
        name    = request.form['supplier_name']
        address = request.form['supplier_address']

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO supplier (supplier_phone, supplier_name, supplier_address) VALUES (%s, %s, %s)",
                (phone, name, address)
            )
            conn.commit()
            flash('Supplier added successfully!', 'success')
        except Exception as e:
            conn.rollback()
            if '1062' in str(e):
                flash('A supplier with this phone number already exists.', 'danger')
            else:
                flash('Failed to add supplier. Please check your inputs and try again.', 'danger')
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('suppliers'))

    return render_template('supplier_form.html', supplier=None, mode='add')


@app.route('/suppliers/edit/<phone>', methods=['GET', 'POST'])
def edit_supplier(phone):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        address = request.form['supplier_address'].strip()
        try:
            cursor.execute("UPDATE supplier SET supplier_address=%s WHERE supplier_phone=%s", (address, phone))
            conn.commit()
            flash('Supplier updated successfully!', 'success')
        except Exception as e:
            conn.rollback()
            flash('Failed to update supplier. Please try again.', 'danger')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('suppliers'))

    cursor.execute("SELECT * FROM supplier WHERE supplier_phone = %s", (phone,))
    supplier = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('supplier_form.html', supplier=supplier, mode='edit')


@app.route('/suppliers/delete/<phone>')
def delete_supplier(phone):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM supplier WHERE supplier_phone = %s", (phone,))
        conn.commit()
        flash('Supplier deleted successfully.', 'info')
    except Exception as e:
        conn.rollback()
        if '1451' in str(e):
            flash('Cannot delete this supplier because they have existing purchase invoices.', 'danger')
        else:
            flash('Failed to delete supplier. Please try again.', 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('suppliers'))


# ══════════════════════════════════════════
# SALES INVOICES
# ══════════════════════════════════════════
@app.route('/sales')
def sales():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    search_customer = request.args.get('search_customer', '')
    search_status   = request.args.get('search_status', '')
    search_date     = request.args.get('search_date', '')

    query = """
        SELECT si.*, c.customer_name
        FROM sales_invoice si
        JOIN customer c ON si.customer_phone = c.customer_phone
        WHERE 1=1
    """
    params = []

    if search_customer:
        query += " AND (c.customer_name LIKE %s OR si.customer_phone LIKE %s)"
        params += [f'%{search_customer}%', f'%{search_customer}%']
    if search_status:
        query += " AND si.invoice_status = %s"
        params.append(search_status)
    if search_date:
        query += " AND si.invoice_date = %s"
        params.append(search_date)

    query += " ORDER BY si.invoice_date DESC"
    cursor.execute(query, params)
    all_sales = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('sales.html',
        sales=all_sales,
        search_customer=search_customer,
        search_status=search_status,
        search_date=search_date
    )


@app.route('/sales/view/<int:invoice_id>')
def view_sale(invoice_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT si.*, c.customer_name, c.customer_phone
        FROM sales_invoice si
        JOIN customer c ON si.customer_phone = c.customer_phone
        WHERE si.s_invoice_id = %s
    """, (invoice_id,))
    invoice = cursor.fetchone()

    cursor.execute("""
        SELECT sid.*, p.product_name, p.product_type
        FROM sales_invoice_details sid
        JOIN product p ON sid.product_code = p.product_code
        WHERE sid.s_invoice_id = %s
    """, (invoice_id,))
    details = cursor.fetchall()

    # Convert Decimals for safe template rendering
    if invoice:
        invoice['total_price']          = float(invoice['total_price'])
        invoice['total_after_discount'] = float(invoice['total_after_discount'])
        invoice['discount_percentage']  = float(invoice['discount_percentage'])
    for d in details:
        d['unit_price'] = float(d['unit_price'])

    cursor.close()
    conn.close()

    return render_template('sale_view.html', invoice=invoice, details=details)


@app.route('/sales/new', methods=['GET', 'POST'])
def new_sale():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        customer_phone = request.form['customer_phone'].strip()
        payment_method = request.form['payment_method']
        invoice_date   = request.form['invoice_date']

        # Inline new-customer registration
        new_customer_name = request.form.get('new_customer_name', '').strip()
        if new_customer_name:
            try:
                cursor.execute(
                    "INSERT INTO customer (customer_phone, customer_name) VALUES (%s, %s)",
                    (customer_phone, new_customer_name)
                )
                conn.commit()
                flash(f'New customer "{new_customer_name}" added.', 'info')
            except Exception as e:
                conn.rollback()
                if '1062' in str(e):
                    flash('A customer with this phone number already exists.', 'danger')
                else:
                    flash('Could not add new customer. Please try again.', 'danger')
                cursor.close()
                conn.close()
                return redirect(url_for('new_sale'))

        # Verify customer exists
        cursor.execute("SELECT customer_name FROM customer WHERE customer_phone=%s", (customer_phone,))
        cust = cursor.fetchone()
        if not cust:
            flash('Customer phone not found. Please add the customer first.', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('new_sale'))

        product_codes = request.form.getlist('product_code[]')
        quantities    = request.form.getlist('quantity[]')

        # Server-side: require at least one product
        product_codes = [c for c in product_codes if c.strip()]
        if not product_codes:
            flash('At least one product is required.', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('new_sale'))

        total_price = 0.0
        line_items  = []

        for pcode, qty in zip(product_codes, quantities):
            qty = int(qty)
            # FIX: cast selling_price to float immediately after fetching
            cursor.execute(
                "SELECT CAST(selling_price AS DECIMAL(10,2)) AS selling_price, "
                "stock_quantity, product_name FROM product WHERE product_code=%s",
                (pcode,)
            )
            prod = cursor.fetchone()

            if not prod:
                flash(f'Product {pcode} not found.', 'danger')
                cursor.close()
                conn.close()
                return redirect(url_for('new_sale'))
            if prod['stock_quantity'] < qty:
                flash(f'Not enough stock for {prod["product_name"]}. Available: {prod["stock_quantity"]}', 'danger')
                cursor.close()
                conn.close()
                return redirect(url_for('new_sale'))

            unit_price   = float(prod['selling_price'])   # unit price per item
            line_total   = unit_price * qty
            total_price += line_total
            line_items.append((pcode, qty, unit_price))

        # Discount logic (Rules 22-24)
        cursor.execute("""
            SELECT MIN(invoice_date) AS first_invoice
            FROM sales_invoice
            WHERE customer_phone = %s AND invoice_status = 'completed'
        """, (customer_phone,))
        row = cursor.fetchone()
        first_invoice = row['first_invoice']

        is_loyal = False
        if first_invoice:
            days = (date.today() - first_invoice).days
            is_loyal = days >= 180

        is_bulk = total_price >= 4000.0

        if is_bulk:
            discount = 15
        elif is_loyal:
            discount = 10
        else:
            discount = 0

        total_after_discount = total_price * (1 - discount / 100)

        try:
            cursor.execute("""
                INSERT INTO sales_invoice
                    (customer_phone, manager_phone, shop_name, invoice_date,
                     total_price, discount_percentage, total_after_discount,
                     payment_method, invoice_status)
                VALUES (%s, '01001234567', 'Emara Shop', %s, %s, %s, %s, %s, 'completed')
            """, (customer_phone, invoice_date, total_price, discount, total_after_discount, payment_method))
            conn.commit()

            cursor.execute("SELECT LAST_INSERT_ID() AS id")
            s_invoice_id = cursor.fetchone()['id']

            for pcode, qty, unit_price in line_items:
                # unit_price stored is the per-item selling price
                cursor.execute("""
                    INSERT INTO sales_invoice_details (s_invoice_id, product_code, quantity, unit_price)
                    VALUES (%s, %s, %s, %s)
                """, (s_invoice_id, pcode, qty, unit_price))

                cursor.execute("""
                    UPDATE product SET stock_quantity = stock_quantity - %s
                    WHERE product_code = %s
                """, (qty, pcode))

            conn.commit()
            flash(f'Sale invoice #{s_invoice_id} created! Discount applied: {discount}%', 'success')
            cursor.close()
            conn.close()
            return redirect(url_for('sales'))

        except Exception as e:
            conn.rollback()
            flash('Failed to create sales invoice. Please try again.', 'danger')

    # GET — load available products (convert Decimal to float for JS safety)
    cursor.execute("SELECT * FROM product WHERE stock_quantity > 0 ORDER BY product_name")
    all_products = cursor.fetchall()
    for p in all_products:
        p['purchase_price'] = float(p['purchase_price'])
        p['selling_price']  = float(p['selling_price'])

    cursor.close()
    conn.close()

    return render_template('sale_form.html',
        products=all_products,
        today=date.today()
    )


# ══════════════════════════════════════════
# PURCHASE INVOICES
# ══════════════════════════════════════════
@app.route('/purchases')
def purchases():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    search_supplier = request.args.get('search_supplier', '')
    search_date     = request.args.get('search_date', '')

    query = """
        SELECT pi.*, s.supplier_name
        FROM purchase_invoice pi
        JOIN supplier s ON pi.supplier_phone = s.supplier_phone
        WHERE 1=1
    """
    params = []

    if search_supplier:
        query += " AND s.supplier_name LIKE %s"
        params.append(f'%{search_supplier}%')
    if search_date:
        query += " AND pi.delivery_date = %s"
        params.append(search_date)

    query += " ORDER BY pi.delivery_date DESC"
    cursor.execute(query, params)
    all_purchases = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('purchases.html',
        purchases=all_purchases,
        search_supplier=search_supplier,
        search_date=search_date
    )


@app.route('/purchases/view/<int:invoice_id>')
def view_purchase(invoice_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT pi.*, s.supplier_name, s.supplier_address
        FROM purchase_invoice pi
        JOIN supplier s ON pi.supplier_phone = s.supplier_phone
        WHERE pi.p_invoice_id = %s
    """, (invoice_id,))
    invoice = cursor.fetchone()

    cursor.execute("""
        SELECT pid.*, p.product_name, p.product_type
        FROM purchase_invoice_details pid
        JOIN product p ON pid.product_code = p.product_code
        WHERE pid.p_invoice_id = %s
    """, (invoice_id,))
    details = cursor.fetchall()

    for d in details:
        d['unit_price'] = float(d['unit_price'])

    cursor.close()
    conn.close()

    return render_template('purchase_view.html', invoice=invoice, details=details)


@app.route('/purchases/new', methods=['GET', 'POST'])
def new_purchase():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        supplier_phone = request.form['supplier_phone']
        delivery_date  = request.form['delivery_date']
        payment_method = request.form['payment_method']

        product_codes = request.form.getlist('product_code[]')
        quantities    = request.form.getlist('quantity[]')
        unit_prices   = request.form.getlist('unit_price[]')

        # Server-side: require at least one product
        product_codes = [c for c in product_codes if c.strip()]
        if not product_codes:
            flash('At least one product is required.', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('new_purchase'))

        total_price = 0.0
        line_items  = []

        for pcode, qty, uprice in zip(product_codes, quantities, unit_prices):
            qty    = int(qty)
            uprice = float(uprice)
            total_price += qty * uprice
            line_items.append((pcode, qty, uprice))

        try:
            cursor.execute("""
                INSERT INTO purchase_invoice
                    (supplier_phone, manager_phone, shop_name, delivery_date, total_price, payment_method)
                VALUES (%s, '01001234567', 'Emara Shop', %s, %s, %s)
            """, (supplier_phone, delivery_date, total_price, payment_method))
            conn.commit()

            cursor.execute("SELECT LAST_INSERT_ID() AS id")
            p_invoice_id = cursor.fetchone()['id']

            for pcode, qty, uprice in line_items:
                cursor.execute("""
                    INSERT INTO purchase_invoice_details
                        (p_invoice_id, product_code, quantity_ordered, unit_price)
                    VALUES (%s, %s, %s, %s)
                """, (p_invoice_id, pcode, qty, uprice))

                cursor.execute("""
                    UPDATE product SET stock_quantity = stock_quantity + %s
                    WHERE product_code = %s
                """, (qty, pcode))

            conn.commit()
            flash(f'Purchase invoice #{p_invoice_id} created successfully!', 'success')
            cursor.close()
            conn.close()
            return redirect(url_for('purchases'))

        except Exception as e:
            conn.rollback()
            flash('Failed to create purchase invoice. Please try again.', 'danger')

    cursor.execute("SELECT * FROM supplier ORDER BY supplier_name")
    all_suppliers = cursor.fetchall()

    cursor.execute("SELECT * FROM product ORDER BY product_name")
    all_products = cursor.fetchall()
    for p in all_products:
        p['purchase_price'] = float(p['purchase_price'])
        p['selling_price']  = float(p['selling_price'])

    cursor.close()
    conn.close()

    return render_template('purchase_form.html',
        suppliers=all_suppliers,
        products=all_products,
        today=date.today()
    )


# ══════════════════════════════════════════
# RETURNS
# ══════════════════════════════════════════
@app.route('/returns')
def returns():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    search = request.args.get('search', '')

    query = """
        SELECT pr.*, c.customer_name, p.product_name, si.invoice_date
        FROM product_returns pr
        JOIN sales_invoice si ON pr.s_invoice_id = si.s_invoice_id
        JOIN customer c ON si.customer_phone = c.customer_phone
        JOIN product p ON pr.product_code = p.product_code
        WHERE 1=1
    """
    params = []

    if search:
        query += " AND (c.customer_name LIKE %s OR p.product_name LIKE %s)"
        params += [f'%{search}%', f'%{search}%']

    query += " ORDER BY pr.return_date DESC"
    cursor.execute(query, params)
    all_returns = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('returns.html', returns=all_returns, search=search)


@app.route('/returns/new', methods=['GET', 'POST'])
def new_return():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        s_invoice_id      = int(request.form['s_invoice_id'])
        product_code      = request.form['product_code'].strip()
        quantity_returned = int(request.form['quantity_returned'])
        return_date       = request.form['return_date']

        # Validate invoice exists and is returnable
        cursor.execute("""
            SELECT invoice_date, invoice_status FROM sales_invoice
            WHERE s_invoice_id = %s
        """, (s_invoice_id,))
        invoice = cursor.fetchone()

        if not invoice:
            flash('Invoice not found.', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('new_return'))

        if invoice['invoice_status'] == 'cancelled':
            flash('This invoice is already cancelled.', 'warning')
            cursor.close()
            conn.close()
            return redirect(url_for('new_return'))

        # Check if already returned
        cursor.execute(
            "SELECT return_id FROM product_returns WHERE s_invoice_id = %s",
            (s_invoice_id,)
        )
        if cursor.fetchone():
            flash('This invoice has already been returned.', 'warning')
            cursor.close()
            conn.close()
            return redirect(url_for('new_return'))

        days_since = (date.fromisoformat(str(return_date)) - invoice['invoice_date']).days
        if days_since > 14:
            flash(f'Return rejected: {days_since} days since purchase. Returns only allowed within 14 days.', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('new_return'))

        # Validate the product was actually in this invoice
        cursor.execute("""
            SELECT quantity FROM sales_invoice_details
            WHERE s_invoice_id = %s AND product_code = %s
        """, (s_invoice_id, product_code))
        detail = cursor.fetchone()

        if not detail:
            flash('This product was not part of that invoice.', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('new_return'))

        if quantity_returned > detail['quantity']:
            flash(f'Cannot return more than purchased. Purchased quantity: {detail["quantity"]}', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('new_return'))

        try:
            cursor.execute("""
                INSERT INTO product_returns (s_invoice_id, product_code, quantity_returned, return_date)
                VALUES (%s, %s, %s, %s)
            """, (s_invoice_id, product_code, quantity_returned, return_date))

            cursor.execute("""
                UPDATE sales_invoice SET invoice_status = 'cancelled' WHERE s_invoice_id = %s
            """, (s_invoice_id,))

            cursor.execute("""
                UPDATE product SET stock_quantity = stock_quantity + %s WHERE product_code = %s
            """, (quantity_returned, product_code))

            conn.commit()
            flash('Return processed successfully!', 'success')
            cursor.close()
            conn.close()
            return redirect(url_for('returns'))

        except Exception as e:
            conn.rollback()
            flash('Failed to process return. Please try again.', 'danger')

    cursor.close()
    conn.close()

    return render_template('return_form.html', today=date.today())


app.run(debug=True)