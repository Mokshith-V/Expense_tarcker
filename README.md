# Expense Tracker API

A FastAPI + MySQL backend for tracking daily expenses. Users register, log in with a JWT, sort spending into categories with optional monthly budgets, and get monthly and yearly reports.

## Setup (Windows)

### 1. Create the MySQL database

Open MySQL Workbench or the MySQL command line and run:

```sql
CREATE DATABASE expense_tracker CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

You only create the empty database yourself. The app creates the tables (`users`, `categories`, `expenses`) when it starts.

### 2. Install the packages

```bat
cd expense_tracker
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure `.env`

```bat
copy .env.example .env
```

Open `.env` and fill in:

- `DATABASE_URL`: your MySQL user, password and database. If the password contains `@`, write it as `%40`.
- `SECRET_KEY`: generate one with `python -c "import secrets; print(secrets.token_hex(32))"`.

### 4. Run it

```bat
uvicorn app.main:app --reload
```

- **The website: http://127.0.0.1:8000/** (create an account and start adding expenses)
- Interactive docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health shows `"database": "connected"` when MySQL is reachable.

### 5. Run the tests

```bat
pytest -v
```

The tests use a temporary in-memory SQLite database, so they don't need MySQL and never touch your data.

## Try it in /docs

1. **POST /auth/register** to create an account. You get 7 starter categories.
2. Click **Authorize** (top right), enter your username and password, then click Authorize again.
3. **GET /categories** shows your category ids.
4. **POST /expenses** adds some expenses.
5. **GET /expenses?start_date=2026-10-01&end_date=2026-10-31&sort=highest** filters and sorts them.
6. **GET /reports/monthly** shows where your money went this month.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| POST | `/auth/register` | Create an account (gets default categories) |
| POST | `/auth/token` | Log in (form data), returns a JWT |
| GET | `/auth/me` | The logged-in user |
| GET | `/categories` | List your categories |
| POST | `/categories` | Create a category (optional `monthly_budget`) |
| GET | `/categories/{id}` | One category |
| PATCH | `/categories/{id}` | Change name and/or budget |
| DELETE | `/categories/{id}` | Delete; its expenses become uncategorised |
| GET | `/expenses` | List with filters, sorting and pagination (see below) |
| POST | `/expenses` | Add an expense |
| GET | `/expenses/{id}` | One expense |
| PATCH | `/expenses/{id}` | Change any fields |
| DELETE | `/expenses/{id}` | Delete |
| GET | `/reports/monthly?year=&month=` | Totals per category vs budget |
| GET | `/reports/yearly?year=` | Totals for each of the 12 months |
| GET | `/health` | Checks the database connection |

**`GET /expenses` filters:** `start_date`, `end_date`, `category_id`, `uncategorised=true`, `payment_method` (cash/card/upi/netbanking/other), `min_amount`, `max_amount`, `search` (in description), `sort` (newest/oldest/highest/lowest), `limit` (1–100, default 20), `offset`.

## Project layout

```
expense_tracker/
├── app/
│   ├── main.py          # creates the app, includes routers, creates tables at startup
│   ├── config.py        # reads settings from .env
│   ├── database.py      # engine, SessionLocal, Base, get_db
│   ├── models.py        # SQLAlchemy tables: User, Category, Expense
│   ├── schemas.py       # Pydantic request/response shapes
│   ├── security.py      # bcrypt hashing + JWT create/decode
│   ├── deps.py          # DbSession and CurrentUser dependencies
│   ├── static/          # the website, served by FastAPI at /
│   │   ├── index.html   # all screens: login, dashboard, expenses, categories, dialogs
│   │   ├── css/style.css
│   │   └── js/app.js    # calls the API with fetch() and draws the pages
│   └── routers/
│       ├── auth.py
│       ├── categories.py
│       ├── expenses.py
│       └── reports.py
├── tests/               # pytest suite (SQLite in memory)
├── .env.example
├── requirements.txt
└── pytest.ini
```

## Notes

- Money is stored as MySQL `DECIMAL(12,2)` and returned as a string such as `"249.50"`, so it never suffers float rounding errors.
- Every query is filtered by the logged-in user. Another user's expense or category returns 404, exactly as if it didn't exist.
- Tables are created by `create_all` at startup, which never changes existing tables. If you change a model later, add Alembic migrations (as in your TodoApp) or drop and recreate the tables.
