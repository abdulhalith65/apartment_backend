from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import mysql.connector
import os
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

app = Flask(__name__)

# Allow Flutter app to connect to Flask
CORS(app)


# =====================================================
# MYSQL CONNECTION
# =====================================================

def get_db_connection():
    host = os.getenv("MYSQLHOST", "127.0.0.1")
    port = int(os.getenv("MYSQLPORT", "3306"))
    user = os.getenv("MYSQLUSER", "root")
    password = os.getenv("MYSQLPASSWORD") or os.getenv("MYSQL_PASSWORD")
    database = os.getenv("MYSQLDATABASE", "apartment_rent_manager")

    if not password:
        raise RuntimeError(
            "MySQL password is not configured. "
            "Set MYSQLPASSWORD (Railway) or MYSQL_PASSWORD."
        )

    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        use_pure=True
    )


# =====================================================
# HOME
# =====================================================

@app.route("/")
def home():
    return "Apartment Rent Manager API is working!"


# =====================================================
# MYSQL TEST
# =====================================================

@app.route("/db-test")
def db_test():

    db = None

    try:
        db = get_db_connection()

        if db.is_connected():
            return "MySQL Connected Successfully!"

        return "MySQL Connection Failed!"

    except Exception as e:
        return f"MySQL Error: {e}"

    finally:
        if db is not None and db.is_connected():
            db.close()


# =====================================================
# GET ALL HOUSES
# =====================================================

@app.route("/houses")
def get_houses():

    db = None
    cursor = None

    try:
        db = get_db_connection()

        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                house_id,
                house_number,
                floor,
                status
            FROM houses
            ORDER BY house_number
        """)

        houses = cursor.fetchall()

        return jsonify(houses)

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

    finally:

        if cursor is not None:
            cursor.close()

        if db is not None and db.is_connected():
            db.close()


# =====================================================
# SAVE TENANT
# =====================================================

@app.route("/tenants", methods=["POST"])
def add_tenant():

    db = None
    cursor = None

    try:

        # Get data from Flutter
        data = request.get_json()

        # Check data
        if not data:
            return jsonify({
                "success": False,
                "message": "No data received"
            }), 400

        house_number = data.get("house_number")
        tenant_name = data.get("tenant_name")
        phone = data.get("phone")
        floor = data.get("floor")
        join_date = data.get("join_date")
        advance_amount = data.get("advance_amount", 0)
        monthly_rent = data.get("monthly_rent")

        # Required fields check
        if (
            house_number is None
            or not tenant_name
            or not join_date
            or monthly_rent is None
        ):
            return jsonify({
                "success": False,
                "message": "Required fields are missing"
            }), 400

        # Connect MySQL
        db = get_db_connection()

        cursor = db.cursor(dictionary=True)

        # Find house
        cursor.execute(
            """
            SELECT house_id
            FROM houses
            WHERE house_number = %s
            """,
            (house_number,)
        )

        house = cursor.fetchone()

        if house is None:
            return jsonify({
                "success": False,
                "message": "House not found"
            }), 404

        house_id = house["house_id"]

        # Insert tenant
        cursor.execute(
            """
            INSERT INTO tenants
            (
                house_id,
                tenant_name,
                phone,
                join_date,
                advance_amount,
                monthly_rent
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                house_id,
                tenant_name,
                phone,
                join_date,
                advance_amount,
                monthly_rent
            )
        )

        # Change house status
        cursor.execute(
            """
            UPDATE houses
            SET status = 'OCCUPIED'
            WHERE house_id = %s
            """,
            (house_id,)
        )

        # Save changes
        db.commit()

        return jsonify({
            "success": True,
            "message": "Tenant saved successfully!",
            "tenant_id": cursor.lastrowid,
            "house_id": house_id
        }), 201

    except Exception as e:

        if db is not None:
            db.rollback()

        return jsonify({
            "success": False,
            "message": "Failed to save tenant",
            "error": str(e)
        }), 500

    finally:

        if cursor is not None:
            cursor.close()

        if db is not None and db.is_connected():
            db.close()


# =====================================================
# GET TENANTS
# =====================================================

@app.route("/tenants")
def get_tenants():

    db = None
    cursor = None

    try:

        db = get_db_connection()

        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                t.tenant_id,
                t.house_id,
                h.house_number,
                h.floor,
                t.tenant_name,
                t.phone,
                t.join_date,
                t.advance_amount,
                t.monthly_rent
            FROM tenants t
            JOIN houses h
            ON t.house_id = h.house_id
            ORDER BY h.house_number
            """
        )

        tenants = cursor.fetchall()

        return jsonify(tenants)

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

    finally:

        if cursor is not None:
            cursor.close()

        if db is not None and db.is_connected():
            db.close()


# =====================================================
# SAVE RENT PAYMENT
# =====================================================

@app.route("/payments", methods=["POST"])
def add_payment():

    db = None
    cursor = None

    try:

        # Get data from Flutter
        data = request.get_json()

        # Check data
        if not data:
            return jsonify({
                "success": False,
                "message": "No data received"
            }), 400

        house_number = data.get("house_number")
        rent_month = data.get("rent_month")
        rent_year = data.get("rent_year")
        rent_amount = data.get("rent_amount")
        paid_amount = data.get("paid_amount")
        balance_amount = data.get("balance_amount")
        status = data.get("status")
        payment_date = data.get("payment_date")

        # Required fields check
        if (
            house_number is None
            or rent_month is None
            or rent_year is None
            or rent_amount is None
            or paid_amount is None
            or balance_amount is None
            or not status
        ):
            return jsonify({
                "success": False,
                "message": "Required payment fields are missing"
            }), 400

        # Connect MySQL
        db = get_db_connection()

        cursor = db.cursor(dictionary=True)

        # Find tenant using house number
        cursor.execute(
            """
            SELECT
                t.tenant_id
            FROM tenants t
            JOIN houses h
            ON t.house_id = h.house_id
            WHERE h.house_number = %s
            ORDER BY t.tenant_id DESC
            LIMIT 1
            """,
            (house_number,)
        )

        tenant = cursor.fetchone()

        if tenant is None:
            return jsonify({
                "success": False,
                "message": "Tenant not found for this house"
            }), 404

        tenant_id = tenant["tenant_id"]

        # Insert payment
        cursor.execute(
            """
            INSERT INTO payments
            (
                tenant_id,
                rent_month,
                rent_year,
                rent_amount,
                paid_amount,
                balance_amount,
                status,
                payment_date
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                tenant_id,
                rent_month,
                rent_year,
                rent_amount,
                paid_amount,
                balance_amount,
                status,
                payment_date
            )
        )

        # Save changes
        db.commit()

        return jsonify({
            "success": True,
            "message": "Rent payment saved successfully!",
            "payment_id": cursor.lastrowid,
            "tenant_id": tenant_id
        }), 201

    except Exception as e:

        if db is not None:
            db.rollback()

        return jsonify({
            "success": False,
            "message": "Failed to save rent payment",
            "error": str(e)
        }), 500

    finally:

        if cursor is not None:
            cursor.close()

        if db is not None and db.is_connected():
            db.close()


# =====================================================
# GET PAYMENTS
# =====================================================

@app.route("/payments")
def get_payments():

    db = None
    cursor = None

    try:

        db = get_db_connection()

        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                p.payment_id,
                p.tenant_id,
                h.house_number,
                t.tenant_name,
                p.rent_month,
                p.rent_year,
                p.rent_amount,
                p.paid_amount,
                p.balance_amount,
                p.status,
                p.payment_date
            FROM payments p
            JOIN tenants t
            ON p.tenant_id = t.tenant_id
            JOIN houses h
            ON t.house_id = h.house_id
            ORDER BY
                p.rent_year DESC,
                p.rent_month DESC,
                h.house_number
            """
        )

        payments = cursor.fetchall()

        return jsonify(payments)

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

    finally:

        if cursor is not None:
            cursor.close()

        if db is not None and db.is_connected():
            db.close()


# =====================================================
# VACATE TENANT
# =====================================================

@app.route("/vacate-tenant/<int:house_number>", methods=["POST"])
def vacate_tenant(house_number):

    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Find the house
        cursor.execute("""
            SELECT house_id, house_number, status
            FROM houses
            WHERE house_number = %s
        """, (house_number,))

        house = cursor.fetchone()

        if house is None:
            return jsonify({
                "success": False,
                "message": "House not found"
            }), 404

        # Check whether the house is occupied
        if house["status"] != "OCCUPIED":
            return jsonify({
                "success": False,
                "message": "This house is already vacant"
            }), 400

        # Find the latest tenant for this house.
        # The tenant record is NOT deleted, so old payment history is preserved.
        cursor.execute("""
            SELECT tenant_id
            FROM tenants
            WHERE house_id = %s
            ORDER BY tenant_id DESC
            LIMIT 1
        """, (house["house_id"],))

        tenant = cursor.fetchone()

        if tenant is None:
            return jsonify({
                "success": False,
                "message": "Tenant not found for this house"
            }), 404

        # Make the house available for a new tenant.
        cursor.execute("""
            UPDATE houses
            SET status = 'VACANT'
            WHERE house_id = %s
        """, (house["house_id"],))

        # If the tenants table already contains status/vacated_date columns,
        # update them too. Otherwise, the tenant record is kept unchanged.
        cursor.execute("""
            SELECT COLUMN_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'tenants'
              AND COLUMN_NAME IN ('status', 'vacated_date')
        """)
        columns = {row["COLUMN_NAME"] for row in cursor.fetchall()}

        if "status" in columns:
            cursor.execute("""
                UPDATE tenants
                SET status = 'VACATED'
                WHERE tenant_id = %s
            """, (tenant["tenant_id"],))

        if "vacated_date" in columns:
            cursor.execute("""
                UPDATE tenants
                SET vacated_date = CURDATE()
                WHERE tenant_id = %s
            """, (tenant["tenant_id"],))

        db.commit()

        return jsonify({
            "success": True,
            "message": "Tenant vacated successfully!",
            "house_number": house_number,
            "tenant_id": tenant["tenant_id"],
            "status": "VACANT"
        }), 200

    except Exception as e:

        if db is not None:
            db.rollback()

        return jsonify({
            "success": False,
            "message": "Failed to vacate tenant",
            "error": str(e)
        }), 500

    finally:

        if cursor is not None:
            cursor.close()

        if db is not None and db.is_connected():
            db.close()



# =====================================================
# DOWNLOAD INDIVIDUAL RENT BILL PDF
# =====================================================

@app.route("/download-bill/<int:payment_id>")
def download_bill(payment_id):

    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Get payment + tenant + house details
        cursor.execute("""
            SELECT
                p.payment_id,
                p.rent_month,
                p.rent_year,
                p.rent_amount,
                p.paid_amount,
                p.balance_amount,
                p.status,
                p.payment_date,
                t.tenant_name,
                t.phone,
                h.house_number,
                h.floor
            FROM payments p
            JOIN tenants t
                ON p.tenant_id = t.tenant_id
            JOIN houses h
                ON t.house_id = h.house_id
            WHERE p.payment_id = %s
            LIMIT 1
        """, (payment_id,))

        payment = cursor.fetchone()

        if payment is None:
            return jsonify({
                "success": False,
                "message": "Payment record not found"
            }), 404

        # Create PDF in memory
        pdf_buffer = BytesIO()

        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "BillTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontSize=20,
            spaceAfter=8
        )

        subtitle_style = ParagraphStyle(
            "BillSubtitle",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontSize=11,
            textColor=colors.grey,
            spaceAfter=20
        )

        normal_style = ParagraphStyle(
            "BillNormal",
            parent=styles["Normal"],
            fontSize=11,
            leading=16
        )

        story = []

        story.append(Paragraph("APARTMENT RENT MANAGER", title_style))
        story.append(Paragraph("Individual Rent Payment Bill", subtitle_style))

        month_value = payment["rent_month"]
        year_value = payment["rent_year"]

        if month_value is not None and year_value is not None:
            rent_month_display = f"{int(month_value):02d}-{year_value}"
        else:
            rent_month_display = "-"

        payment_date = payment["payment_date"]
        if payment_date is None:
            payment_date_display = "-"
        else:
            payment_date_display = str(payment_date)

        bill_data = [
            ["Payment ID", str(payment["payment_id"])],
            ["House Number", str(payment["house_number"])],
            ["Floor", str(payment["floor"] or "-")],
            ["Tenant Name", str(payment["tenant_name"] or "-")],
            ["Phone Number", str(payment["phone"] or "-")],
            ["Rent Month", rent_month_display],
            ["Rent Amount", f"₹ {float(payment['rent_amount'] or 0):,.2f}"],
            ["Paid Amount", f"₹ {float(payment['paid_amount'] or 0):,.2f}"],
            ["Balance Amount", f"₹ {float(payment['balance_amount'] or 0):,.2f}"],
            ["Status", str(payment["status"] or "-")],
            ["Payment Date", payment_date_display],
        ]

        table = Table(
            bill_data,
            colWidths=[150, 320],
            hAlign="CENTER"
        )

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF2FF")),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1F2937")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))

        story.append(table)
        story.append(Spacer(1, 25))
        story.append(
            Paragraph(
                "Thank you for your payment.",
                normal_style
            )
        )

        doc.build(story)

        pdf_buffer.seek(0)

        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"rent_bill_{payment_id}.pdf"
        )

    except Exception as e:

        return jsonify({
            "success": False,
            "message": "Failed to generate PDF bill",
            "error": str(e)
        }), 500

    finally:

        if cursor is not None:
            cursor.close()

        if db is not None and db.is_connected():
            db.close()



# =====================================================
# DOWNLOAD ALL RENT BILLS FOR ONE MONTH
# =====================================================

@app.route("/download-all-bills/<int:rent_month>/<int:rent_year>")
def download_all_bills(rent_month, rent_year):

    db = None
    cursor = None

    try:
        # Validate month
        if rent_month < 1 or rent_month > 12:
            return jsonify({
                "success": False,
                "message": "Invalid rent month"
            }), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Get all payment records for the selected month/year
        cursor.execute("""
            SELECT
                p.payment_id,
                p.rent_month,
                p.rent_year,
                p.rent_amount,
                p.paid_amount,
                p.balance_amount,
                p.status,
                p.payment_date,
                t.tenant_name,
                t.phone,
                h.house_number,
                h.floor
            FROM payments p
            JOIN tenants t
                ON p.tenant_id = t.tenant_id
            JOIN houses h
                ON t.house_id = h.house_id
            WHERE p.rent_month = %s
              AND p.rent_year = %s
            ORDER BY h.house_number, p.payment_id
        """, (rent_month, rent_year))

        payments = cursor.fetchall()

        if not payments:
            return jsonify({
                "success": False,
                "message": f"No rent records found for {rent_month:02d}-{rent_year}"
            }), 404

        # Create PDF in memory
        pdf_buffer = BytesIO()

        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=A4,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "MonthlyTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontSize=20,
            spaceAfter=8
        )

        subtitle_style = ParagraphStyle(
            "MonthlySubtitle",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontSize=12,
            textColor=colors.grey,
            spaceAfter=20
        )

        story = []

        story.append(
            Paragraph(
                "APARTMENT RENT MANAGER",
                title_style
            )
        )

        story.append(
            Paragraph(
                f"Monthly Rent Bills - {rent_month:02d}-{rent_year}",
                subtitle_style
            )
        )

        for payment in payments:

            story.append(
                Paragraph(
                    f"House {payment['house_number']}",
                    styles["Heading2"]
                )
            )

            payment_date = payment["payment_date"]
            payment_date_display = (
                "-" if payment_date is None else str(payment_date)
            )

            bill_data = [
                ["Tenant Name", str(payment["tenant_name"] or "-")],
                ["Phone Number", str(payment["phone"] or "-")],
                ["Floor", str(payment["floor"] or "-")],
                ["Rent Amount",
                 f"INR {float(payment['rent_amount'] or 0):,.2f}"],
                ["Paid Amount",
                 f"INR {float(payment['paid_amount'] or 0):,.2f}"],
                ["Balance Amount",
                 f"INR {float(payment['balance_amount'] or 0):,.2f}"],
                ["Status", str(payment["status"] or "-")],
                ["Payment Date", payment_date_display],
                ["Payment ID", str(payment["payment_id"])],
            ]

            table = Table(
                bill_data,
                colWidths=[150, 330],
                hAlign="CENTER"
            )

            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (0, -1),
                 colors.HexColor("#EAF2FF")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]))

            story.append(table)
            story.append(Spacer(1, 20))

        doc.build(story)

        pdf_buffer.seek(0)

        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=(
                f"monthly_bills_{rent_month:02d}_{rent_year}.pdf"
            )
        )

    except Exception as e:

        return jsonify({
            "success": False,
            "message": "Failed to generate monthly bills PDF",
            "error": str(e)
        }), 500

    finally:

        if cursor is not None:
            cursor.close()

        if db is not None and db.is_connected():
            db.close()


# =====================================================
# HEALTH CHECK
# =====================================================

@app.route("/health")
def health():
    return jsonify({
        "success": True,
        "message": "Apartment Rent Manager API is running"
    })


# =====================================================
# START FLASK
# =====================================================

if __name__ == "__main__":

    print("Starting Apartment Rent Manager API...")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )