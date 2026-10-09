from flask import Flask, request, jsonify, send_file


from dotenv import load_dotenv


from flask_cors import CORS


import mysql.connector


import os
from datetime import datetime


load_dotenv()


import glob


from io import BytesIO


from reportlab.lib.pagesizes import A4, landscape


from reportlab.lib import colors


from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


from reportlab.lib.enums import TA_CENTER


from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


app = Flask(__name__)


CORS(app)


# =====================================================


# TIDB CLOUD CONNECTION


# =====================================================


# These values work with both:


# 1. Local .env file


# 2. Render Environment Variables


TIDB_HOST = os.getenv(


    "TIDB_HOST",


    "gateway01.ap-southeast-1.prod.aws.tidbcloud.com"


)


TIDB_PORT = int(os.getenv("TIDB_PORT", "4000"))


TIDB_USER = os.getenv("TIDB_USER", "").strip()


TIDB_PASSWORD = os.getenv("TIDB_PASSWORD", "")


TIDB_DATABASE = os.getenv("TIDB_DB_NAME", "test")


TIDB_CA_PATH = os.getenv("TIDB_CA_PATH", "")


def get_db_connection():


    """


    Create a TLS connection to TiDB Cloud.


    Local:


        Values are read from .env.


    Render:


        Values are read from Render Environment Variables.


    TIDB_CA_PATH is optional. If a CA file is provided, certificate


    verification is enabled. Otherwise TLS remains enabled without


    depending on a Windows Downloads folder.


    """


    if not TIDB_USER:


        raise RuntimeError("TIDB_USER environment variable is missing")


    if not TIDB_PASSWORD:


        raise RuntimeError("TIDB_PASSWORD environment variable is missing")


    config = {


        "host": TIDB_HOST,


        "port": TIDB_PORT,


        "user": TIDB_USER,


        "password": TIDB_PASSWORD,


        "database": TIDB_DATABASE,


        "use_pure": True,


        "connection_timeout": 15,


        # TiDB Cloud connection uses TLS.


        "ssl_disabled": False,


    }


    # If a CA file is provided, verify the certificate.


    if TIDB_CA_PATH and os.path.exists(TIDB_CA_PATH):


        config["ssl_ca"] = TIDB_CA_PATH


        config["ssl_verify_cert"] = True


    else:


        # TLS is still enabled.


        # This avoids depending on a local Windows Downloads folder


        # when the Flask API is running on Render.


        config["ssl_verify_cert"] = False


    return mysql.connector.connect(**config)


# =====================================================


# HELPER FUNCTIONS


# =====================================================


def close_db(db, cursor=None):


    if cursor is not None:


        try:


            cursor.close()


        except Exception:


            pass


    if db is not None:


        try:


            if db.is_connected():


                db.close()


        except Exception:


            pass


def parse_month_value(month_value):


    """


    Accepts:


      1 / 01 / January / jan / "01-2026"


    Returns:


      (month_number, year_or_none)


    """


    if month_value is None:


        return None, None


    value = str(month_value).strip()


    if "-" in value:


        parts = value.split("-")


        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():


            return int(parts[0]), int(parts[1])


    month_names = {


        "january": 1, "jan": 1,


        "february": 2, "feb": 2,


        "march": 3, "mar": 3,


        "april": 4, "apr": 4,


        "may": 5,


        "june": 6, "jun": 6,


        "july": 7, "jul": 7,


        "august": 8, "aug": 8,


        "september": 9, "sep": 9,


        "october": 10, "oct": 10,


        "november": 11, "nov": 11,


        "december": 12, "dec": 12,


    }


    if value.lower() in month_names:


        return month_names[value.lower()], None


    if value.isdigit():


        month_number = int(value)


        if 1 <= month_number <= 12:


            return month_number, None


    return None, None


def normalize_status(status, rent_amount, paid_amount):


    status = str(status or "").strip().upper()


    if status in ("PAID", "PARTIAL", "UNPAID"):


        return status


    try:


        rent = float(rent_amount or 0)


        paid = float(paid_amount or 0)


        if paid <= 0:


            return "UNPAID"


        if paid >= rent:


            return "PAID"


        return "PARTIAL"


    except Exception:


        return "UNPAID"


# =====================================================


# HOME


# =====================================================


@app.route("/")


def home():


    return jsonify({


        "success": True,


        "message": "Apartment Rent Manager API is working!",


        "database": TIDB_DATABASE


    })


@app.route("/health", methods=["GET"])


def health():


    """Health check endpoint for deployment."""


    return jsonify({


        "success": True,


        "message": "Apartment Rent Manager API is healthy"


    })


# =====================================================


# DATABASE TEST


# =====================================================


@app.route("/db-test")


def db_test():


    db = None


    try:


        db = get_db_connection()


        if db.is_connected():


            return jsonify({


                "success": True,


                "message": "TiDB Cloud Connected Successfully!",


                "database": TIDB_DATABASE


            })


        return jsonify({


            "success": False,


            "message": "Database connection failed"


        }), 500


    except Exception as e:


        return jsonify({


            "success": False,


            "message": "Database connection error",


            "error": str(e)


        }), 500


    finally:


        close_db(db)


# =====================================================


# GET HOUSES


# Supports both /houses and /api/houses


# =====================================================


@app.route("/houses", methods=["GET"])


@app.route("/api/houses", methods=["GET"])


def get_houses():


    db = None


    cursor = None


    try:


        db = get_db_connection()


        cursor = db.cursor(dictionary=True)


        cursor.execute("""


            SELECT


                h.id,


                h.id AS house_id,


                h.house_no,


                h.house_no AS house_number,


                h.status AS house_status,


                h.status,


                t.id AS tenant_id,


                t.name AS tenant_name,


                t.name,


                t.phone,


                t.monthly_rent,


                t.advance_received,


                t.joined_date,


                t.status AS tenant_status


            FROM houses h


            LEFT JOIN tenants t


                ON h.id = t.house_id


                AND t.status = 'ACTIVE'


            ORDER BY h.id


        """)


        rows = cursor.fetchall()


        houses = []


        for row in rows:


            houses.append({


                "id": row["id"],


                "house_id": row["house_id"],


                "house_no": row["house_no"],


                "house_number": row["house_number"],


                "status": row["status"],


                "house_status": row["house_status"],


                "tenant": (


                    {


                        "id": row["tenant_id"],


                        "tenant_id": row["tenant_id"],


                        "name": row["tenant_name"],


                        "tenant_name": row["tenant_name"],


                        "phone": row["phone"],


                        "monthly_rent": row["monthly_rent"],


                        "advance_received": row["advance_received"],


                        "joined_date": str(row["joined_date"])


                        if row["joined_date"] else None,


                        "status": row["tenant_status"]


                    }


                    if row["tenant_id"] is not None else None


                )


            })


        return jsonify({


            "success": True,


            "houses": houses,


            "data": houses


        })


    except Exception as e:


        return jsonify({


            "success": False,


            "error": str(e)


        }), 500


    finally:


        close_db(db, cursor)


# =====================================================


# ADD TENANT


# Supports /tenants and /api/tenants


# =====================================================


@app.route("/tenants", methods=["POST"])


@app.route("/api/tenants", methods=["POST"])


def add_tenant():


    """Add a tenant using either house_id or house_number."""


    db = None


    cursor = None


    try:


        data = request.get_json(silent=True) or {}


        house_id = data.get("house_id")


        house_number = data.get("house_number", data.get("house_no"))


        tenant_name = data.get("tenant_name", data.get("name"))


        phone = data.get("phone")


        join_date = data.get("join_date", data.get("joined_date"))


        advance_amount = data.get("advance_amount", data.get("advance_received", 0))


        monthly_rent = data.get("monthly_rent")


        if isinstance(house_id, str) and not house_id.strip():


            house_id = None


        if isinstance(house_number, str):


            house_number = house_number.strip()


        if isinstance(tenant_name, str):


            tenant_name = tenant_name.strip()


        if isinstance(join_date, str):


            join_date = join_date.strip()


        if house_id is None and not house_number:


            return jsonify({


                "success": False,


                "message": "House ID or house number is required"


            }), 400


        if not tenant_name or not join_date or monthly_rent is None:


            return jsonify({


                "success": False,


                "message": "Tenant name, join date and monthly rent are required"


            }), 400


        db = get_db_connection()


        cursor = db.cursor(dictionary=True)


        if house_id is not None:


            try:


                house_id = int(house_id)


            except Exception:


                return jsonify({"success": False, "message": "Invalid house_id"}), 400


            cursor.execute("""


                SELECT id, house_no, status


                FROM houses


                WHERE id = %s


                LIMIT 1


            """, (house_id,))


        else:


            cursor.execute("""


                SELECT id, house_no, status


                FROM houses


                WHERE house_no = %s


                LIMIT 1


            """, (house_number,))


        house = cursor.fetchone()


        # Also accept values such as "1" or "House 1".


        if house is None and house_number:


            numeric_house_id = None


            if house_number.isdigit():


                numeric_house_id = int(house_number)


            elif house_number.lower().startswith("house "):


                possible_id = house_number[6:].strip()


                if possible_id.isdigit():


                    numeric_house_id = int(possible_id)


            if numeric_house_id is not None:


                cursor.execute("""


                    SELECT id, house_no, status


                    FROM houses


                    WHERE id = %s


                    LIMIT 1


                """, (numeric_house_id,))


                house = cursor.fetchone()


        if house is None:


            return jsonify({"success": False, "message": "House not found"}), 404


        cursor.execute("""


            SELECT id, name


            FROM tenants


            WHERE house_id = %s


              AND status = 'ACTIVE'


            LIMIT 1


        """, (house["id"],))


        active_tenant = cursor.fetchone()


        if active_tenant:


            return jsonify({


                "success": False,


                "message": "This house already has an active tenant"


            }), 400


        cursor.execute("""


            INSERT INTO tenants


            (


                house_id, name, phone, monthly_rent,


                advance_received, advance_returned, advance_deduction,


                joined_date, status


            )


            VALUES (%s, %s, %s, %s, %s, 0, 0, %s, 'ACTIVE')


        """, (


            house["id"], tenant_name, phone, monthly_rent,


            advance_amount or 0, join_date


        ))


        tenant_id = cursor.lastrowid


        cursor.execute("""


            UPDATE houses


            SET status = 'OCCUPIED'


            WHERE id = %s


        """, (house["id"],))


        db.commit()


        return jsonify({


            "success": True,


            "message": "Tenant saved successfully!",


            "tenant_id": tenant_id,


            "house_id": house["id"],


            "house_number": house["house_no"],


            "tenant_name": tenant_name


        }), 201


    except Exception as e:


        if db is not None:


            try:


                db.rollback()


            except Exception:


                pass


        return jsonify({


            "success": False,


            "message": "Failed to save tenant",


            "error": str(e)


        }), 500


    finally:


        close_db(db, cursor)


# =====================================================


# GET ALL TENANTS


# =====================================================


@app.route("/tenants", methods=["GET"])


@app.route("/api/tenants", methods=["GET"])


def get_tenants():


    db = None


    cursor = None


    try:


        db = get_db_connection()


        cursor = db.cursor(dictionary=True)


        cursor.execute("""


            SELECT


                t.id,


                t.id AS tenant_id,


                t.house_id,


                h.house_no,


                h.house_no AS house_number,


                t.name,


                t.name AS tenant_name,


                t.phone,


                t.monthly_rent,


                t.advance_received,


                t.advance_returned,


                t.advance_deduction,


                t.joined_date,


                t.vacated_date,


                t.status


            FROM tenants t


            JOIN houses h ON t.house_id = h.id


            ORDER BY h.id, t.id DESC


        """)


        tenants = cursor.fetchall()


        for tenant in tenants:


            if tenant.get("joined_date"):


                tenant["joined_date"] = str(tenant["joined_date"])


            if tenant.get("vacated_date"):


                tenant["vacated_date"] = str(tenant["vacated_date"])


        return jsonify({


            "success": True,


            "tenants": tenants,


            "data": tenants


        })


    except Exception as e:


        return jsonify({


            "success": False,


            "error": str(e)


        }), 500


    finally:


        close_db(db, cursor)


# =====================================================


# GET ONE TENANT


# =====================================================


@app.route("/tenants/<int:tenant_id>", methods=["GET"])


@app.route("/api/tenants/<int:tenant_id>", methods=["GET"])


def get_tenant(tenant_id):


    db = None


    cursor = None


    try:


        db = get_db_connection()


        cursor = db.cursor(dictionary=True)


        cursor.execute("""


            SELECT


                t.id,


                t.id AS tenant_id,


                t.house_id,


                h.house_no,


                h.house_no AS house_number,


                t.name,


                t.name AS tenant_name,


                t.phone,


                t.monthly_rent,


                t.advance_received,


                t.advance_returned,


                t.advance_deduction,


                t.joined_date,


                t.vacated_date,


                t.status


            FROM tenants t


            JOIN houses h ON t.house_id = h.id


            WHERE t.id = %s


            LIMIT 1


        """, (tenant_id,))


        tenant = cursor.fetchone()


        if tenant is None:


            return jsonify({


                "success": False,


                "message": "Tenant not found"


            }), 404


        if tenant.get("joined_date"):


            tenant["joined_date"] = str(tenant["joined_date"])


        if tenant.get("vacated_date"):


            tenant["vacated_date"] = str(tenant["vacated_date"])


        return jsonify({


            "success": True,


            "tenant": tenant,


            "data": tenant


        })


    except Exception as e:


        return jsonify({


            "success": False,


            "error": str(e)


        }), 500


    finally:


        close_db(db, cursor)


# =====================================================

# UPDATE TENANT DETAILS

# =====================================================


@app.route("/api/tenants/<int:tenant_id>", methods=["PUT"])

def update_tenant(tenant_id):


    db = None

    cursor = None


    try:

        data = request.get_json(silent=True) or {}


        name = data.get("name")

        phone = data.get("phone", "")

        monthly_rent = data.get("monthly_rent")

        advance_received = data.get("advance_received", 0)


        if name is None or not str(name).strip():

            return jsonify({

                "success": False,

                "message": "Tenant name is required."

            }), 400


        try:

            monthly_rent = float(monthly_rent)

            advance_received = float(advance_received)

        except (TypeError, ValueError):

            return jsonify({

                "success": False,

                "message": "Monthly rent and advance must be numbers."

            }), 400


        if monthly_rent < 0 or advance_received < 0:

            return jsonify({

                "success": False,

                "message": "Monthly rent and advance cannot be negative."

            }), 400


        db = get_db_connection()

        cursor = db.cursor(dictionary=True)


        cursor.execute("""

            SELECT id, status

            FROM tenants

            WHERE id = %s

            LIMIT 1

        """, (tenant_id,))


        tenant = cursor.fetchone()


        if tenant is None:

            return jsonify({

                "success": False,

                "message": "Tenant not found."

            }), 404


        if tenant.get("status") != "ACTIVE":

            return jsonify({

                "success": False,

                "message": "Only an active tenant can be updated."

            }), 400


        cursor.execute("""

            UPDATE tenants

            SET

                name = %s,

                phone = %s,

                monthly_rent = %s,

                advance_received = %s

            WHERE id = %s

        """, (

            str(name).strip(),

            str(phone).strip(),

            monthly_rent,

            advance_received,

            tenant_id

        ))


        db.commit()


        return jsonify({

            "success": True,

            "message": "Tenant details updated successfully.",

            "tenant_id": tenant_id

        }), 200


    except Exception as e:

        if db is not None:

            db.rollback()


        return jsonify({

            "success": False,

            "message": "Failed to update tenant details.",

            "error": str(e)

        }), 500


    finally:

        close_db(db, cursor)


# =====================================================


# SAVE RENT PAYMENT


# Supports /payments and /api/rents


# =====================================================


@app.route("/payments", methods=["POST"])


@app.route("/api/rents", methods=["POST"])


def add_payment():


    db = None


    cursor = None


    try:


        data = request.get_json(silent=True) or {}


        house_number = data.get("house_number", data.get("house_no"))


        tenant_id = data.get("tenant_id")


        rent_month = data.get("rent_month", data.get("month"))


        rent_year = data.get("rent_year", data.get("year"))


        # Flutter may send month_name instead.


        if rent_month is None and data.get("month_name"):


            parsed_month, parsed_year = parse_month_value(data.get("month_name"))


            rent_month = parsed_month


            if rent_year is None:


                rent_year = parsed_year


        rent_amount = data.get("rent_amount", data.get("monthly_rent"))


        paid_amount = data.get("paid_amount", data.get("paid"))


        balance_amount = data.get("balance_amount", data.get("balance"))


        payment_date = data.get("payment_date")


        if rent_month is None or rent_year is None:


            return jsonify({


                "success": False,


                "message": "Rent month and year are required"


            }), 400


        try:


            rent_month = int(rent_month)


            rent_year = int(rent_year)


        except Exception:


            return jsonify({


                "success": False,


                "message": "Invalid month or year"


            }), 400


        if rent_month < 1 or rent_month > 12:


            return jsonify({


                "success": False,


                "message": "Rent month must be between 1 and 12"


            }), 400


        if rent_amount is None:


            return jsonify({


                "success": False,


                "message": "Rent amount is required"


            }), 400


        paid_amount = float(paid_amount or 0)


        rent_amount = float(rent_amount)


        if balance_amount is None:


            balance_amount = max(rent_amount - paid_amount, 0)


        else:


            balance_amount = float(balance_amount)


        status = normalize_status(


            data.get("status"),


            rent_amount,


            paid_amount


        )


        db = get_db_connection()


        cursor = db.cursor(dictionary=True)


        # Find tenant.


        if tenant_id is not None:


            cursor.execute("""


                SELECT id, house_id, monthly_rent


                FROM tenants


                WHERE id = %s


                  AND status = 'ACTIVE'


                LIMIT 1


            """, (tenant_id,))


        elif house_number is not None:


            cursor.execute("""


                SELECT t.id, t.house_id, t.monthly_rent


                FROM tenants t


                JOIN houses h ON t.house_id = h.id


                WHERE h.house_no = %s


                  AND t.status = 'ACTIVE'


                LIMIT 1


            """, (str(house_number),))


        else:


            return jsonify({


                "success": False,


                "message": "tenant_id or house_number is required"


            }), 400


        tenant = cursor.fetchone()


        if tenant is None:


            return jsonify({


                "success": False,


                "message": "Active tenant not found"


            }), 404


        tenant_id = tenant["id"]


        month_name = f"{rent_month:02d}-{rent_year}"


        # Prevent duplicate rent record for the same tenant/month.


        cursor.execute("""


            SELECT id


            FROM monthly_rent


            WHERE tenant_id = %s


              AND month_name = %s


            LIMIT 1


        """, (tenant_id, month_name))


        existing = cursor.fetchone()


        if existing:


            return jsonify({


                "success": False,


                "message": f"Rent for {month_name} already exists",


                "rent_id": existing["id"]


            }), 400


        cursor.execute("""


            INSERT INTO monthly_rent


            (


                tenant_id,


                month_name,


                rent_amount,


                paid_amount,


                balance,


                status,


                payment_date


            )


            VALUES (%s, %s, %s, %s, %s, %s, %s)


        """, (


            tenant_id,


            month_name,


            rent_amount,


            paid_amount,


            balance_amount,


            status,


            payment_date


        ))


        rent_id = cursor.lastrowid


        db.commit()


        return jsonify({


            "success": True,


            "message": "Rent payment saved successfully!",


            "rent_id": rent_id,


            "payment_id": rent_id,


            "tenant_id": tenant_id,


            "month_name": month_name


        }), 201


    except Exception as e:


        if db is not None:


            try:


                db.rollback()


            except Exception:


                pass


        return jsonify({


            "success": False,


            "message": "Failed to save rent payment",


            "error": str(e)


        }), 500


    finally:


        close_db(db, cursor)


# =====================================================


# GET ALL RENT PAYMENTS


# Supports /payments and /api/rents


# =====================================================


@app.route("/payments", methods=["GET"])


@app.route("/api/rents", methods=["GET"])


def get_payments():


    db = None


    cursor = None


    try:


        db = get_db_connection()


        cursor = db.cursor(dictionary=True)


        cursor.execute("""


            SELECT


                r.id,


                r.id AS rent_id,


                r.id AS payment_id,


                r.tenant_id,


                h.house_no,


                h.house_no AS house_number,


                t.name,


                t.name AS tenant_name,


                t.phone,


                r.month_name,


                r.rent_amount,


                r.paid_amount,


                r.balance,


                r.balance AS balance_amount,


                r.status,


                r.payment_date


            FROM monthly_rent r


            JOIN tenants t ON r.tenant_id = t.id


            JOIN houses h ON t.house_id = h.id


            ORDER BY r.month_name DESC, h.id, r.id DESC


        """)


        rows = cursor.fetchall()


        result = []


        for row in rows:


            month_name = str(row["month_name"] or "")


            rent_month = None


            rent_year = None


            if "-" in month_name:


                parts = month_name.split("-")


                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():


                    rent_month = int(parts[0])


                    rent_year = int(parts[1])


            row["rent_month"] = rent_month


            row["rent_year"] = rent_year


            if row.get("payment_date"):


                row["payment_date"] = str(row["payment_date"])


            result.append(row)


        return jsonify({


            "success": True,


            "payments": result,


            "data": result


        })


    except Exception as e:


        return jsonify({


            "success": False,


            "error": str(e)


        }), 500


    finally:


        close_db(db, cursor)


# =====================================================


# RENT HISTORY FOR ONE TENANT


# =====================================================


@app.route("/rent-history/<int:tenant_id>", methods=["GET"])


@app.route("/api/rent-history/<int:tenant_id>", methods=["GET"])


def rent_history(tenant_id):


    db = None


    cursor = None


    try:


        db = get_db_connection()


        cursor = db.cursor(dictionary=True)


        cursor.execute("""


            SELECT


                r.id,


                r.id AS rent_id,


                r.id AS payment_id,


                r.tenant_id,


                h.house_no,


                h.house_no AS house_number,


                t.name AS tenant_name,


                t.phone,


                r.month_name,


                r.rent_amount,


                r.paid_amount,


                r.balance,


                r.balance AS balance_amount,


                r.status,


                r.payment_date


            FROM monthly_rent r


            JOIN tenants t ON r.tenant_id = t.id


            JOIN houses h ON t.house_id = h.id


            WHERE r.tenant_id = %s


            ORDER BY r.id DESC


        """, (tenant_id,))


        rows = cursor.fetchall()


        for row in rows:


            month_name = str(row["month_name"] or "")


            if "-" in month_name:


                parts = month_name.split("-")


                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():


                    row["rent_month"] = int(parts[0])


                    row["rent_year"] = int(parts[1])


            if row.get("payment_date"):


                row["payment_date"] = str(row["payment_date"])


        return jsonify({


            "success": True,


            "tenant_id": tenant_id,


            "history": rows,


            "data": rows


        })


    except Exception as e:


        return jsonify({


            "success": False,


            "error": str(e)


        }), 500


    finally:


        close_db(db, cursor)


# =====================================================


# VACATE TENANT


# Supports both:


#   /vacate-tenant/<house_number>


#   /api/tenants/<tenant_id>/vacate


# =====================================================


def perform_vacate(tenant_id=None, house_number=None):


    db = None


    cursor = None


    try:


        db = get_db_connection()


        cursor = db.cursor(dictionary=True)


        if tenant_id is not None:


            cursor.execute("""


                SELECT id, house_id, name, status


                FROM tenants


                WHERE id = %s


                LIMIT 1


            """, (tenant_id,))


        else:


            cursor.execute("""


                SELECT


                    t.id,


                    t.house_id,


                    t.name,


                    t.status


                FROM tenants t


                JOIN houses h ON t.house_id = h.id


                WHERE h.house_no = %s


                  AND t.status = 'ACTIVE'


                ORDER BY t.id DESC


                LIMIT 1


            """, (str(house_number),))


        tenant = cursor.fetchone()


        if tenant is None:


            return jsonify({


                "success": False,


                "message": "Active tenant not found"


            }), 404


        if tenant["status"] != "ACTIVE":


            return jsonify({


                "success": False,


                "message": "Tenant is already vacated"


            }), 400


        # Preserve tenant and rent history.


        cursor.execute("""


            UPDATE tenants


            SET


                status = 'VACATED',


                vacated_date = CURDATE()


            WHERE id = %s


        """, (tenant["id"],))


        # Make house available for the next tenant.


        cursor.execute("""


            UPDATE houses


            SET status = 'VACANT'


            WHERE id = %s


        """, (tenant["house_id"],))


        db.commit()


        return jsonify({


            "success": True,


            "message": "Tenant vacated successfully!",


            "tenant_id": tenant["id"],


            "house_id": tenant["house_id"],


            "status": "VACANT"


        }), 200


    except Exception as e:


        if db is not None:


            try:


                db.rollback()


            except Exception:


                pass


        return jsonify({


            "success": False,


            "message": "Failed to vacate tenant",


            "error": str(e)


        }), 500


    finally:


        close_db(db, cursor)


@app.route("/vacate-tenant/<house_number>", methods=["POST"])


def vacate_tenant_by_house(house_number):


    return perform_vacate(house_number=house_number)


@app.route("/api/tenants/<int:tenant_id>/vacate", methods=["POST"])


def vacate_tenant_by_id(tenant_id):


    return perform_vacate(tenant_id=tenant_id)


# =====================================================


# INDIVIDUAL RENT BILL PDF


# =====================================================


@app.route("/download-bill/<int:rent_id>", methods=["GET"])


@app.route("/api/download-bill/<int:rent_id>", methods=["GET"])


def download_bill(rent_id):


    db = None


    cursor = None


    try:


        db = get_db_connection()


        cursor = db.cursor(dictionary=True)


        cursor.execute("""


            SELECT


                r.id AS rent_id,


                r.month_name,


                r.rent_amount,


                r.paid_amount,


                r.balance,


                r.status,


                r.payment_date,


                t.name AS tenant_name,


                t.phone,


                h.house_no


            FROM monthly_rent r


            JOIN tenants t ON r.tenant_id = t.id


            JOIN houses h ON t.house_id = h.id


            WHERE r.id = %s


            LIMIT 1


        """, (rent_id,))


        rent = cursor.fetchone()


        if rent is None:


            return jsonify({


                "success": False,


                "message": "Rent record not found"


            }), 404


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


        story = [


            Paragraph("APARTMENT RENT MANAGER", title_style),


            Paragraph("Individual Rent Payment Bill", subtitle_style)


        ]


        payment_date = (


            "-"


            if rent["payment_date"] is None


            else str(rent["payment_date"])


        )


        bill_data = [


            ["Rent ID", str(rent["rent_id"])],


            ["House", str(rent["house_no"] or "-")],


            ["Tenant Name", str(rent["tenant_name"] or "-")],


            ["Phone Number", str(rent["phone"] or "-")],


            ["Rent Month", str(rent["month_name"] or "-")],


            ["Rent Amount", f"INR {float(rent['rent_amount'] or 0):,.2f}"],


            ["Paid Amount", f"INR {float(rent['paid_amount'] or 0):,.2f}"],


            ["Balance", f"INR {float(rent['balance'] or 0):,.2f}"],


            ["Status", str(rent["status"] or "-")],


            ["Payment Date", payment_date],


        ]


        table = Table(


            bill_data,


            colWidths=[150, 320],


            hAlign="CENTER"


        )


        table.setStyle(TableStyle([


            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF2FF")),


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


        story.append(Paragraph(


            "Thank you for your payment.",


            styles["Normal"]


        ))


        doc.build(story)


        pdf_buffer.seek(0)


        return send_file(


            pdf_buffer,


            mimetype="application/pdf",


            as_attachment=True,


            download_name=f"rent_bill_{rent_id}.pdf"


        )


    except Exception as e:


        return jsonify({


            "success": False,


            "message": "Failed to generate PDF bill",


            "error": str(e)


        }), 500


    finally:


        close_db(db, cursor)


# =====================================================


# ALL RENT BILLS FOR ONE MONTH


# =====================================================


@app.route(


    "/download-all-bills/<int:rent_month>/<int:rent_year>",


    methods=["GET"]


)


@app.route(


    "/api/download-all-bills/<int:rent_month>/<int:rent_year>",


    methods=["GET"]


)


def download_all_bills(rent_month, rent_year):


    db = None


    cursor = None


    try:


        if rent_month < 1 or rent_month > 12:


            return jsonify({


                "success": False,


                "message": "Invalid rent month"


            }), 400


        db = get_db_connection()


        cursor = db.cursor(dictionary=True)


        month_name = f"{rent_month:02d}-{rent_year}"


        cursor.execute("""


            SELECT


                r.id AS rent_id,


                r.month_name,


                r.rent_amount,


                r.paid_amount,


                r.balance,


                r.status,


                r.payment_date,


                t.name AS tenant_name,


                t.phone,


                h.house_no


            FROM (

                SELECT tenant_id, MAX(id) AS rent_id

                FROM monthly_rent

                WHERE month_name = %s

                GROUP BY tenant_id

            ) latest


            JOIN monthly_rent r ON r.id = latest.rent_id


            JOIN tenants t ON r.tenant_id = t.id


            JOIN houses h ON t.house_id = h.id


            WHERE t.status = 'ACTIVE'


            ORDER BY h.id, r.id


        """, (month_name,))


        rents = cursor.fetchall()


        if not rents:


            return jsonify({


                "success": False,


                "message": f"No rent records found for {month_name}"


            }), 404


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


        story = [


            Paragraph("APARTMENT RENT MANAGER", title_style),


            Paragraph(


                f"Monthly Rent Bills - {month_name}",


                subtitle_style


            )


        ]


        for rent in rents:


            story.append(


                Paragraph(


                    f"House {rent['house_no']}",


                    styles["Heading2"]


                )


            )


            payment_date = (


                "-"


                if rent["payment_date"] is None


                else str(rent["payment_date"])


            )


            bill_data = [


                ["Tenant Name", str(rent["tenant_name"] or "-")],


                ["Phone Number", str(rent["phone"] or "-")],


                ["Rent Amount",


                 f"INR {float(rent['rent_amount'] or 0):,.2f}"],


                ["Paid Amount",


                 f"INR {float(rent['paid_amount'] or 0):,.2f}"],


                ["Balance",


                 f"INR {float(rent['balance'] or 0):,.2f}"],


                ["Status", str(rent["status"] or "-")],


                ["Payment Date", payment_date],


                ["Rent ID", str(rent["rent_id"])],


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


            download_name=f"monthly_bills_{rent_month:02d}_{rent_year}.pdf"


        )


    except Exception as e:


        return jsonify({


            "success": False,


            "message": "Failed to generate monthly bills PDF",


            "error": str(e)


        }), 500


    finally:


        close_db(db, cursor)


# =====================================================


# =====================================================
# MONTHLY RENT COLLECTION / SUMMARY
# The current month's summary uses the tenant's latest monthly rent.
# Previously saved payments are read only; this report does not rewrite them.
# =====================================================
def _build_monthly_summary_report(cursor, rent_month, rent_year):
    month_name = f"{rent_month:02d}-{rent_year}"
    now = datetime.now()
    is_current_month = (
        rent_month == now.month and rent_year == now.year
    )

    # Select at most one rent row per tenant for this month (latest row if
    # duplicate records exist), so the summary and PDF don't duplicate houses.
    cursor.execute("""
        SELECT
            h.id AS house_id,
            h.house_no,
            h.status AS house_status,
            t.id AS tenant_id,
            t.name AS tenant_name,
            t.phone,
            t.monthly_rent,
            t.advance_received,
            t.status AS tenant_status,
            r.id AS rent_id,
            r.month_name,
            r.rent_amount AS saved_rent_amount,
            r.paid_amount,
            r.balance AS saved_balance,
            r.status AS rent_status,
            r.payment_date
        FROM houses h
        LEFT JOIN tenants t
            ON h.id = t.house_id
            AND t.status = 'ACTIVE'
        LEFT JOIN (
            SELECT tenant_id, MAX(id) AS latest_rent_id
            FROM monthly_rent
            WHERE month_name = %s
            GROUP BY tenant_id
        ) latest
            ON latest.tenant_id = t.id
        LEFT JOIN monthly_rent r
            ON r.id = latest.latest_rent_id
        ORDER BY h.id
    """, (month_name,))
    rows = cursor.fetchall()

    details = []
    for row in rows:
        tenant_id = row.get("tenant_id")
        rent_id = row.get("rent_id")
        tenant_name = row.get("tenant_name")

        if tenant_id is None:
            rent_amount = 0.0
            paid_amount = 0.0
            balance = 0.0
            display_status = "VACANT"
        else:
            live_rent = float(row.get("monthly_rent") or 0)
            saved_rent = row.get("saved_rent_amount")
            paid_amount = float(row.get("paid_amount") or 0)

            # Current month uses the newly saved tenant rent. Past months keep
            # their saved rent/payment values if a rent record already exists.
            if is_current_month or rent_id is None:
                rent_amount = live_rent
            else:
                rent_amount = float(saved_rent or 0)

            # For the current month, recalculate only the displayed balance
            # and status against the latest rent; don't modify monthly_rent.
            # Past-month saved balances/statuses remain as originally recorded.
            if is_current_month or rent_id is None:
                balance = max(rent_amount - paid_amount, 0.0)
            else:
                saved_balance = row.get("saved_balance")
                balance = (
                    float(saved_balance)
                    if saved_balance is not None
                    else max(rent_amount - paid_amount, 0.0)
                )

            if rent_id is None:
                display_status = "UNPAID"
            elif is_current_month:
                if paid_amount <= 0:
                    display_status = "UNPAID"
                elif paid_amount >= rent_amount:
                    display_status = "PAID"
                else:
                    display_status = "PARTIAL"
            else:
                display_status = normalize_status(
                    row.get("rent_status"), rent_amount, paid_amount
                )

        details.append({
            "house_id": row.get("house_id"),
            "house_no": row.get("house_no"),
            "house_status": row.get("house_status"),
            "tenant_id": tenant_id,
            "tenant_name": tenant_name,
            "phone": row.get("phone"),
            "advance_received": float(row.get("advance_received") or 0),
            "monthly_rent": float(row.get("monthly_rent") or 0),
            "rent_id": rent_id,
            "rent_month": month_name,
            "rent_amount": rent_amount,
            "paid_amount": paid_amount,
            "balance": balance,
            "status": display_status,
            "payment_date": (
                str(row["payment_date"]) if row.get("payment_date") else None
            )
        })

    # Totals match the house-by-house detail shown by the API/PDF.
    total_rent = sum(item["rent_amount"] for item in details)
    total_paid = sum(item["paid_amount"] for item in details)
    total_balance = sum(item["balance"] for item in details)
    total_tenants = sum(1 for item in details if item["rent_id"] is not None)
    active_tenants = sum(1 for item in details if item["tenant_id"] is not None)
    vacant_houses = sum(1 for item in details if item["tenant_id"] is None)

    return month_name, details, {
        "total_rent_amount": total_rent,
        "total_paid_amount": total_paid,
        "total_unpaid_amount": total_balance,
        "total_balance": total_balance,
        "total_tenants": total_tenants,
        "active_tenants": active_tenants,
        "vacant_houses": vacant_houses,
        "total_houses": len(details)
    }


@app.route(
    "/monthly-summary/<int:rent_month>/<int:rent_year>",
    methods=["GET"]
)
@app.route(
    "/api/monthly-summary/<int:rent_month>/<int:rent_year>",
    methods=["GET"]
)
def monthly_summary(rent_month, rent_year):
    db = None
    cursor = None
    try:
        if rent_month < 1 or rent_month > 12:
            return jsonify({"success": False, "message": "Invalid rent month"}), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        month_name, details, summary = _build_monthly_summary_report(
            cursor, rent_month, rent_year
        )
        return jsonify({
            "success": True,
            "message": f"Monthly summary for {month_name}",
            "month": rent_month,
            "year": rent_year,
            "month_name": month_name,
            "summary": summary,
            "details": details,
            "data": details
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Failed to get monthly rent summary",
            "error": str(e)
        }), 500
    finally:
        close_db(db, cursor)


# =====================================================
# MONTHLY RENT COLLECTION / SUMMARY PDF
# PDF uses the same live details and calculations as the summary API.
# =====================================================
@app.route(
    "/download-monthly-summary/<int:rent_month>/<int:rent_year>",
    methods=["GET"]
)
@app.route(
    "/api/download-monthly-summary/<int:rent_month>/<int:rent_year>",
    methods=["GET"]
)
def download_monthly_summary(rent_month, rent_year):
    db = None
    cursor = None
    try:
        if rent_month < 1 or rent_month > 12:
            return jsonify({"success": False, "message": "Invalid rent month"}), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        month_name, details, summary = _build_monthly_summary_report(
            cursor, rent_month, rent_year
        )

        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=landscape(A4),
            rightMargin=24,
            leftMargin=24,
            topMargin=28,
            bottomMargin=28
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "SummaryTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontSize=18,
            spaceAfter=6
        )
        subtitle_style = ParagraphStyle(
            "SummarySubtitle",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontSize=11,
            textColor=colors.grey,
            spaceAfter=16
        )
        story = [
            Paragraph("APARTMENT RENT MANAGER", title_style),
            Paragraph(f"Monthly Collection Summary - {month_name}", subtitle_style)
        ]

        detail_data = [[
            "House", "Tenant Name", "Phone", "Rent", "Advance",
            "Paid", "Balance", "Status"
        ]]
        for item in details:
            detail_data.append([
                str(item.get("house_no") or "-"),
                str(item.get("tenant_name") or "-"),
                str(item.get("phone") or "-"),
                f"INR {item['rent_amount']:,.0f}",
                f"INR {item['advance_received']:,.0f}",
                f"INR {item['paid_amount']:,.0f}",
                f"INR {item['balance']:,.0f}",
                str(item.get("status") or "-")
            ])

        detail_table = Table(
            detail_data,
            colWidths=[60, 112, 100, 75, 75, 75, 75, 65],
            repeatRows=1,
            hAlign="CENTER"
        )
        detail_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCEBFF")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6)
        ]))
        story.append(detail_table)
        story.append(Spacer(1, 16))

        totals_data = [
            ["Total Rent", "Total Paid", "Total Balance", "Active Tenants", "Vacant Houses"],
            [
                f"INR {summary['total_rent_amount']:,.0f}",
                f"INR {summary['total_paid_amount']:,.0f}",
                f"INR {summary['total_balance']:,.0f}",
                str(summary["active_tenants"]),
                str(summary["vacant_houses"])
            ]
        ]
        totals_table = Table(
            totals_data,
            colWidths=[125, 125, 125, 125, 125],
            hAlign="CENTER"
        )
        totals_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8E1F5")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7)
        ]))
        story.append(totals_table)
        story.append(Spacer(1, 16))
        story.append(Paragraph("Generated by Apartment Rent Manager", styles["Normal"]))

        doc.build(story)
        pdf_buffer.seek(0)
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"monthly_summary_{rent_month:02d}_{rent_year}.pdf"
        )
    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Failed to generate monthly summary PDF",
            "error": str(e)
        }), 500
    finally:
        close_db(db, cursor)


# START FLASK


# =====================================================


if __name__ == "__main__":


    print("==============================================")


    print("Starting Apartment Rent Manager API (Render-ready)...")


    print("Database:", TIDB_DATABASE)


    print("Host:", TIDB_HOST)


    print("Port:", TIDB_PORT)


    print("==============================================")


    port = int(os.getenv("PORT", "5000"))


    app.run(


        host="0.0.0.0",


        port=port,


        debug=False,


        threaded=True


    )
